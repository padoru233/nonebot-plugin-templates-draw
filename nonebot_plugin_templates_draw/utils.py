import json
import base64
import asyncio
import httpx
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple, Dict
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
    返回“默认 + 用户”合并后的模板表，用户同名会覆盖默认。
    """
    defaults = _load_default_prompts()
    users = _load_user_prompts()
    # 合并：先默认，再用户覆盖
    merged = {**defaults, **{k: v for k, v in users.items() if v.strip()}}
    return merged

def get_prompt(identifier: str) -> str:
    """
    先从用户模板找 {identifier}，如果不存在或为空则回退到默认模板，
    再不行就拿第一个默认模板（key 最小的那个）。
    """
    users = _load_user_prompts()
    if identifier in users and users[identifier].strip():
        return users[identifier].strip()

    defaults = _load_default_prompts()
    if identifier in defaults:
        return defaults[identifier]

    # 回退到第一个默认
    if defaults:
        first_key = sorted(defaults.keys())[0]
        return defaults[first_key]

    return ""

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
        "messages": [{"role": "user", "content": content_parts}]
    }

    last_err = ""
    for attempt in range(1, plugin_config.max_total_attempts + 1):
        idx = _current_api_key_idx % len(keys)
        key = keys[idx]
        _current_api_key_idx += 1

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            last_err = f"网络异常: {e}"
            logger.warning(f"[Attempt {attempt}] 网络异常，切换 Key：{e}")
            await asyncio.sleep(1)
            continue

        if resp.status_code != 200:
            last_err = f"HTTP {resp.status_code}: {resp.text}"
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

        # 直接搜索所有 base64 图片数据（data:image/xxx;base64,xxxxx）
        # 匹配 data:image 开头的 base64 数据
        base64_pattern = r'data:image/[^;,\s]+;base64,([A-Za-z0-9+/=]+)'
        base64_matches = re.findall(base64_pattern, content)

        if not base64_matches:
            last_err = "content 中未找到 base64 图片数据"
            logger.warning(f"[Attempt {attempt}] {last_err}")
            logger.debug(f"Content 内容: {content[:500]}")  # 打印前500字符用于调试
            continue

        # 移除所有 base64 数据，保留纯文本
        text_content = re.sub(r'data:image/[^;,\s]+;base64,[A-Za-z0-9+/=]+', '', content)
        # 清理多余的标记符号（如 ![image]() 等）
        text_content = re.sub(r'!\[image\]\(\s*\)', '', text_content)
        text_content = text_content.strip()
        text_content = text_content if text_content else None

        # 解码所有 base64 图片
        results = []
        for idx, b64str in enumerate(base64_matches):
            try:
                img_bytes = base64.b64decode(b64str)
                # 只在第一张图时附带文本
                text = text_content if idx == 0 else None
                results.append((img_bytes, None, text))
                logger.info(f"成功解码第 {idx + 1} 张图片，大小: {len(img_bytes)} bytes")
            except Exception as e:
                logger.warning(f"图片 {idx + 1} Base64 解码失败: {e}")
                continue

        if results:
            logger.info(f"成功解析 {len(results)} 张图片")
            return results
        else:
            last_err = "所有图片解析均失败"
            logger.warning(f"[Attempt {attempt}] {last_err}")
            continue

    raise RuntimeError(f"已尝试 {plugin_config.max_total_attempts} 次，仍未成功，最后错误：{last_err}")

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
    reply_msg_id: Optional[int]
) -> List[Image.Image]:
    """
    支持场景：
    1. 回复一条带图消息：拉取回复消息里的图
    2. 当前消息直接发图
    3. @用户 或 文本 “自己”：拉取对应头像
    返回 PIL Image 列表，空列表表示未拉到任何图
    """
    images: List[Image.Image] = []
    import re
    from nonebot.adapters.onebot.v11.message import MessageSegment

    # 1. 回复消息里拉图
    if reply_msg_id:
        try:
            msg_data = await bot.get_msg(message_id=reply_msg_id)
            for seg in msg_data["message"]:
                if seg["type"] == "image":
                    r = await httpx.AsyncClient().get(seg["data"]["url"], follow_redirects=True)
                    if r.is_success:
                        images.append(Image.open(BytesIO(r.content)))
        except Exception:
            pass

    # 2. 当前消息里直接发图 / @ / 文本
    at_ids = []
    mention_self = False
    for seg in event.message:
        if seg.type == "image":
            r = await httpx.AsyncClient().get(seg.data["url"], follow_redirects=True)
            if r.is_success:
                images.append(Image.open(BytesIO(r.content)))
        elif seg.type == "at":
            at_ids.append(int(seg.data["qq"]))
        elif seg.type == "text":
            text = seg.data["text"].strip()
            # 支持关键字“自己”
            if "自己" in text:
                mention_self = True
            # 支持直接 @123456
            for token in re.split(r"\s+", text):
                if token.startswith("@") and token[1:].isdigit():
                    at_ids.append(int(token[1:]))

    # 3. 如果还没图，则拉头像
    async def _fetch_avatar(uid: int) -> Optional[Image.Image]:
        url = f"https://q1.qlogo.cn/g?b=qq&s=0&nk={uid}"
        try:
            r = await httpx.AsyncClient().get(url, follow_redirects=True, timeout=10)
            if r.is_success:
                return Image.open(BytesIO(r.content))
        except Exception:
            pass
        return None

    if not images:
        if mention_self:
            avatar = await _fetch_avatar(event.sender.user_id)
            if avatar:
                images.append(avatar)
        for uid in at_ids:
            avatar = await _fetch_avatar(uid)
            if avatar:
                images.append(avatar)

    return images
