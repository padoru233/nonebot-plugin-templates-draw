import json
import base64
import asyncio
import httpx
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Union
from PIL import Image
from pydantic import ValidationError

from nonebot import logger, require, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment, GroupMessageEvent
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_config_file

from .config import Config

# 用户自定义的模板文件
USER_PROMPT_FILE: Path    = Path(get_plugin_config_file("prompt.json"))
# 存放默认模板的文件，每次启动都重写
DEFAULT_PROMPT_FILE: Path = Path(get_plugin_config_file("default_prompt.json"))

plugin_config = get_plugin_config(Config).templates_draw

# 全局轮询 idx
_current_api_key_idx = 0

def get_reply_id(event: GroupMessageEvent) -> Optional[int]:
    return event.reply.message_id if event.reply else None

def _ensure_files():
    USER_PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USER_PROMPT_FILE.exists():
        # 用户文件默认留空 dict
        USER_PROMPT_FILE.write_text("{}", "utf-8")
    DEFAULT_PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)

def _generate_default_prompts():
    # 1）拿到插件真正生效的 Config（包括默认值和面板/ TOML 里的覆盖值）
    plugin_cfg = get_plugin_config(Config)  # 这是一个 Namespace
    cfg = plugin_cfg.templates_draw if hasattr(plugin_cfg, "templates_draw") else plugin_cfg
    # 2）把它转 dict，摘出所有 prompt_ 前缀
    data = cfg.dict()
    result: Dict[str, str] = {}
    for k, v in data.items():
        if k.startswith("prompt_") and isinstance(v, str) and v.strip():
            result[k[len("prompt_"):]] = v
    # 3）写到 default_prompt.json
    DEFAULT_PROMPT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=4),
        "utf-8"
    )
    logger.debug(f"[templates-draw] 生成默认模板到 {DEFAULT_PROMPT_FILE}, 内容：{result}")

# 启动时保证有目录/文件，然后 rewrite 默认模板
_ensure_files()
_generate_default_prompts()

def _load_default_prompts() -> Dict[str, str]:
    try:
        raw = DEFAULT_PROMPT_FILE.read_text("utf-8")
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[templates-draw] 读取 default_prompt.json 失败，返回空：{e}")
        return {}

def _load_user_prompts() -> Dict[str, str]:
    try:
        raw = USER_PROMPT_FILE.read_text("utf-8")
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[templates-draw] 读取 prompt.json 失败，返回空：{e}")
        return {}

def _save_user_prompts(data: Dict[str, str]):
    USER_PROMPT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )

def list_templates() -> Dict[str, str]:
    """
    返回"默认 + 用户"合并后的模板表，用户同名会覆盖默认。
    """
    defaults = _load_default_prompts()
    users = _load_user_prompts()
    merged = {**defaults, **{k: v.strip() for k, v in users.items() if v.strip()}}
    return merged

def get_prompt(identifier: str) -> Union[str, bool]:
    """获取模板内容，直接使用合并后的模板表"""
    templates = list_templates()
    return templates.get(identifier, False)

def add_template(identifier: str, prompt_text: str):
    """
    在用户模板里新增或覆盖一个 {identifier: prompt_text}，
    不影响 default_prompt.json。
    """
    users = _load_user_prompts()
    users[identifier] = prompt_text.strip()
    _save_user_prompts(users)

def remove_template(identifier: str) -> bool:
    """
    在用户模板里删除 identifier（只是删除用户覆盖，
    默认模板仍然保留，不会从 default_prompt.json 删）。
    返回 True 表示操作成功（文件发生过写入），False 表示 identifier 在用户里本来就不存在。
    """
    users = _load_user_prompts()
    if identifier in users:
        users.pop(identifier)
        _save_user_prompts(users)
        return True
    return False

async def download_image_from_url(url: str, client: httpx.AsyncClient) -> Optional[bytes]:
    """
    辅助函数：从 URL 下载图片
    """
    try:
        resp = await client.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.content
        else:
            logger.warning(f"下载图片失败 {url}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"下载图片异常 {url}: {e}")
        return None


def extract_images_and_text(content: str) -> Tuple[List[Tuple[Optional[bytes], Optional[str]]], Optional[str]]:
    """
    辅助函数：从 content 中提取所有图片（base64 和 URL）以及文本
    返回：([(image_bytes, image_url)], text_content)
    """
    images = []

    # 1. 提取 base64 图片
    base64_pattern = r'data:image/[^;,\s]+;base64,([A-Za-z0-9+/=]+)'
    base64_matches = re.findall(base64_pattern, content)

    for b64str in base64_matches:
        try:
            img_bytes = base64.b64decode(b64str)
            images.append((img_bytes, None))
        except Exception as e:
            logger.warning(f"Base64 解码失败: {e}")

    # 2. 提取 HTTP/HTTPS URL 图片
    # 匹配 http:// 或 https:// 开头的图片链接
    url_pattern = r'https?://[^\s\)\]"\'<>]+'
    url_matches = re.findall(url_pattern, content)

    for url in url_matches:
        # 简单判断是否为图片链接
        if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
            images.append((None, url))

    # 3. 提取纯文本（移除所有图片数据和各种 markdown 标记）
    text_content = content

    # 移除 base64 图片数据
    text_content = re.sub(r'data:image/[^;,\s]+;base64,[A-Za-z0-9+/=]+', '', text_content)

    # 移除 HTTP/HTTPS 链接
    text_content = re.sub(r'https?://[^\s\)\]"\'<>]+', '', text_content)

    # 移除各种 markdown 图片/链接标记
    text_content = re.sub(r'!\[.*?\]\(.*?\)', '', text_content)  # ![alt](url)
    text_content = re.sub(r'\[.*?\]\(\s*\)', '', text_content)   # [text]() 空链接
    text_content = re.sub(r'\[下载\d*\]\(\s*\)', '', text_content)  # [下载]() 下载标记
    text_content = re.sub(r'\[图片\d*\]\(\s*\)', '', text_content)  # [图片]() 图片标记
    text_content = re.sub(r'\[image\d*\]\(\s*\)', '', text_content, flags=re.IGNORECASE)  # [image]() 图片标记

    # 清理多余的空白字符和换行
    text_content = re.sub(r'\n\s*\n', '\n', text_content)  # 多个连续换行变成单个
    text_content = re.sub(r'^\s+|\s+$', '', text_content, flags=re.MULTILINE)  # 去除行首行尾空格
    text_content = text_content.strip()

    # 如果只剩下空白字符，则返回 None
    text_content = text_content if text_content else None

    return images, text_content


async def generate_template_images(
    images: List[Image.Image],
    prompt: Optional[str] = None
) -> List[Tuple[Optional[bytes], Optional[str], Optional[str]]]:
    """
    调用 Gemini/OpenAI 接口生成图片（支持多图输入和多图输出）
    返回 List[(image_bytes, image_url, text_content)]
    """
    global _current_api_key_idx

    keys = plugin_config.gemini_api_keys
    if not keys or (len(keys) == 1 and keys[0] == "xxxxxx"):
        raise RuntimeError("请先在 env 中配置有效的 Gemini API Key")

    if not prompt:
        prompt = plugin_config.prompt_0

    if not images:
        raise RuntimeError("没有传入任何图片")

    # 把所有输入图片转成 base64
    content_parts = [{"type": "text", "text": prompt}]
    for img in images:
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64data = base64.b64encode(buf.getvalue()).decode()
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64data}"}
        })

    url = f"{plugin_config.gemini_api_url}/v1/chat/completions"
    payload = {
        "model": plugin_config.gemini_model,
        "messages": [{"role": "user", "content": content_parts}],
        "safety_settings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
    }

    # 添加 Gemini 3 配置
    if "banana-2" in plugin_config.gemini_model.lower() or "gemini-3" in plugin_config.gemini_model.lower():
        payload["generation_config"] = {
            # 允许生成包含成人和儿童的图片
            "personGeneration": "allow_all"
        }

    last_err = ""
    # 标记是否为连接失败
    api_connection_failed = False

    for attempt in range(1, plugin_config.max_total_attempts + 1):
        idx = _current_api_key_idx % len(keys)
        key = keys[idx]
        _current_api_key_idx += 1

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(url, headers=headers, json=payload)

                # 成功连接，重置标记
                api_connection_failed = False

                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning(f"[Attempt {attempt}] HTTP 错误，切换 Key：{resp.status_code}")
                    await asyncio.sleep(1)
                    continue

                try:
                    data = resp.json()
                except Exception as e:
                    last_err = f"JSON 解析失败: {e}"
                    logger.warning(f"[Attempt {attempt}] JSON 解析失败：{e}")
                    continue

                if data.get("error"):
                    err = data["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    last_err = f"API 返回错误: {msg}"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    continue

                choices = data.get("choices", [])
                if not choices:
                    last_err = "返回 choices 为空"
                    continue

                msg = choices[0].get("message", {}) or {}
                content = msg.get("content", "")

                if not content or not isinstance(content, str):
                    last_err = "message.content 为空或非字符串"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    continue

                # 提取所有图片（base64 和 URL）以及文本
                image_list, text_content = extract_images_and_text(content)

                if not image_list:
                    last_err = "content 中未找到图片数据（base64 或 URL）"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    logger.debug(f"Content 内容: {content[:500]}")
                    continue

                # 处理所有图片（下载 URL 图片）
                results = []
                for idx, (img_bytes, img_url) in enumerate(image_list):
                    if img_bytes:
                        # Base64 图片已解码
                        text = text_content if idx == 0 else None
                        results.append((img_bytes, None, text))
                        logger.info(f"成功解码第 {idx + 1} 张图片（Base64），大小: {len(img_bytes)} bytes")
                    elif img_url:
                        # URL 图片需要下载
                        downloaded = await download_image_from_url(img_url, client)
                        if downloaded:
                            text = text_content if idx == 0 and not results else None
                            results.append((downloaded, img_url, text))
                            logger.info(f"成功下载第 {idx + 1} 张图片（URL），大小: {len(downloaded)} bytes")
                        else:
                            # 下载失败，但保留 URL
                            text = text_content if idx == 0 and not results else None
                            results.append((None, img_url, text))
                            logger.warning(f"第 {idx + 1} 张图片下载失败，保留 URL: {img_url}")

                if results:
                    logger.info(f"成功解析 {len(results)} 张图片")
                    return results
                else:
                    last_err = "所有图片解析均失败"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    continue

        except httpx.TimeoutException as e:
            # 超时异常单独处理
            api_connection_failed = True
            last_err = f"请求超时（90秒无响应）: {e}"
            logger.warning(f"[Attempt {attempt}] 请求超时，切换 Key：{e}")
            await asyncio.sleep(1)
            continue
        except (httpx.ConnectError, httpx.NetworkError) as e:
            # 连接失败
            api_connection_failed = True
            last_err = f"网络连接失败: {e}"
            logger.warning(f"[Attempt {attempt}] 无法连接到 API，切换 Key：{e}")
            await asyncio.sleep(1)
            continue
        except Exception as e:
            last_err = f"未知异常: {e}"
            logger.warning(f"[Attempt {attempt}] 发生异常，切换 Key：{e}")
            await asyncio.sleep(1)
            continue

    # 所有尝试失败后的错误提示
    if api_connection_failed:
        if "超时" in last_err:
            raise RuntimeError(
                f"已尝试 {plugin_config.max_total_attempts} 次，均请求超时。\n"
                f"API 服务可能繁忙，请稍后再试。\n"
                f"最后错误：{last_err}"
            )
        else:
            raise RuntimeError(
                f"已尝试 {plugin_config.max_total_attempts} 次，均无法连接到 API。\n"
                f"请检查网络连接或 API 地址配置。\n"
                f"最后错误：{last_err}"
            )
    else:
        raise RuntimeError(
            f"已尝试 {plugin_config.max_total_attempts} 次，仍未成功。\n"
            f"最后错误：{last_err}"
        )

async def forward_images(
    bot: Bot,
    event: GroupMessageEvent,
    results: List[Tuple[Optional[bytes], Optional[str], Optional[str]]]
) -> None:
    """
    把 results 里的多条(图片bytes, 图片url, 文本) 打包成合并转发发出。
    """
    # 取发送者信息，给 node_custom 用
    sender = event.sender
    sender_name = getattr(sender, "card", None) or getattr(sender, "nickname", None) or str(event.user_id)
    sender_id = str(event.user_id)

    # 1. 构造每一个 node
    nodes = []
    for idx, (img_bytes, img_url, text) in enumerate(results, start=1):
        content = Message()
        # 如果有 text，先加文字
        if text:
            content.append(text)
        # 再加图
        if img_bytes:
            content.append(MessageSegment.image(file=img_bytes))
        elif img_url:
            content.append(MessageSegment.image(url=img_url))
        else:
            # 既没文字也没图，就跳过
            continue

        node = MessageSegment.node_custom(
            user_id=sender_id,
            nickname=sender_name,
            content=content
        )
        nodes.append(node)

    if not nodes:
        # 没东西就返回一条普通信息
        await bot.send(event, "⚠️ 未生成任何内容")
        return

    # 2. 一次性发送合并转发
    forward_msg = Message(nodes)
    try:
        result = await bot.send(event=event, message=forward_msg)
        logger.debug(f"[draw] 合并转发成功，forward_id: {result.get('forward_id')}")
    except Exception as e:
        logger.exception(f"[draw] 合并转发失败：{e}")
        # 如果失败，就退回普通发送
        for node in nodes:
            await bot.send(event, Message(node))

# —— 收图逻辑 —— #
async def get_images_from_event(
    bot,
    event,
    reply_msg_id: Optional[int],
    at_uids: List[str] = None,
    raw_text: str = "",
    message_image_urls: List[str] = None,
) -> List[Image.Image]:
    at_uids = at_uids or []
    message_image_urls = message_image_urls or []
    images: List[Image.Image] = []

    async with httpx.AsyncClient() as client:
        # 1. 处理 Alconna 解析到的消息图片
        for url in message_image_urls:
            try:
                img_bytes = await download_image_from_url(url, client)
                if img_bytes:
                    images.append(Image.open(BytesIO(img_bytes)))
            except Exception as e:
                logger.warning(f"处理 Alconna 图片失败 {url}: {e}")

        # 2. 从回复消息拉图
        if reply_msg_id:
            try:
                msg = await bot.get_msg(message_id=reply_msg_id)
                for seg in msg["message"]:
                    if seg["type"] == "image":
                        img_url = seg["data"]["url"]
                        img_bytes = await download_image_from_url(img_url, client)
                        if img_bytes:
                            images.append(Image.open(BytesIO(img_bytes)))
            except Exception as e:
                logger.warning(f"从回复消息获取图片失败: {e}")

        # 3. 如果已经有图片了，直接返回（不需要头像）
        if images:
            return images

        # 4. 没有图片时，才去获取头像
        async def _fetch_avatar(uid: str) -> Optional[Image.Image]:
            url = f"https://q1.qlogo.cn/g?b=qq&s=640&nk={uid}"
            try:
                img_bytes = await download_image_from_url(url, client)
                if img_bytes:
                    return Image.open(BytesIO(img_bytes))
                return None
            except Exception as e:
                logger.warning(f"获取头像失败 {uid}: {e}")
                return None

        # 依次拉 at_uids 头像
        for uid in at_uids:
            avatar = await _fetch_avatar(uid)
            if avatar:
                images.append(avatar)

    return images
