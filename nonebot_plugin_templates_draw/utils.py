import json
import base64
import asyncio
import httpx
import re
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict, Union
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


# 预编译正则表达式，避免重复编译
_BASE64_PATTERN = re.compile(r'data:image/[^;,\s]+;base64,([A-Za-z0-9+/=\s]+)')  # 允许空白字符
_URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'<>]+')
_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# 预编译清理文本的正则表达式
_CLEANUP_PATTERNS = [
    re.compile(r'data:image/[^;,\s]+;base64,[A-Za-z0-9+/=\s]+'),  # base64 图片（允许空白）
    re.compile(r'https?://[^\s\)\]"\'<>]+'),                      # HTTP/HTTPS 链接
    re.compile(r'!\[.*?\]\(.*?\)'),                               # ![alt](url)
    re.compile(r'\[.*?\]\(\s*\)'),                                # [text]() 空链接
    re.compile(r'\[下载\d*\]\(\s*\)'),                            # [下载]() 下载标记
    re.compile(r'\[图片\d*\]\(\s*\)'),                            # [图片]() 图片标记
    re.compile(r'\[image\d*\]\(\s*\)', re.IGNORECASE),            # [image]() 图片标记
]

_WHITESPACE_PATTERN = re.compile(r'\n\s*\n')
_LINE_SPACES_PATTERN = re.compile(r'^\s+|\s+$', re.MULTILINE)


def extract_images_and_text(content: str, parts: Optional[List[Dict]] = None, api_type: str = "openai") -> Tuple[List[Tuple[Optional[bytes], Optional[str]]], Optional[str]]:
    """
    从 content 或 parts 中提取所有图片（base64 和 URL）以及文本
    支持 OpenAI 和 Gemini 两种格式
    返回：([(image_bytes, image_url)], text_content)
    """
    images = []
    text_content = ""

    if api_type == "gemini" and parts:
        # Gemini 原生格式：从 parts 中提取
        for part in parts:
            if part.get("thought", False):
                continue  # 跳过思考部分

            # 处理文本
            if "text" in part:
                text_content += part["text"] + "\n"

            # 处理内联数据（base64 图片）
            if "inlineData" in part:
                inline_data = part["inlineData"]
                mime_type = inline_data.get("mimeType", "")
                data = inline_data.get("data", "")

                if mime_type.startswith("image/") and data:
                    try:
                        img_bytes = base64.b64decode(data)
                        images.append((img_bytes, None))
                        logger.debug(f"解码 Gemini 内联图片: {len(img_bytes)} bytes, type: {mime_type}")
                    except Exception as e:
                        logger.warning(f"Gemini 内联图片解码失败: {e}")

            # 处理文件数据（如果有）
            if "fileData" in part:
                file_data = part["fileData"]
                mime_type = file_data.get("mimeType", "")
                file_uri = file_data.get("fileUri", "")

                if mime_type.startswith("image/") and file_uri:
                    images.append((None, file_uri))
                    logger.debug(f"找到 Gemini 文件图片: {file_uri}, type: {mime_type}")

        text_content = text_content.strip()

    else:
        # OpenAI 格式：从文本中提取 base64 和 URL
        if not content:
            return [], None

        # 1. 先找到所有 base64 位置，但不立即解码
        base64_positions = []
        for match in _BASE64_PATTERN.finditer(content):
            base64_positions.append((match.start(), match.end(), match.group(1)))

        # 2. 逐个处理 base64（避免同时在内存中保存多个大图片）
        for start, end, b64str in base64_positions:
            try:
                b64str = re.sub(r'\s+', '', b64str)
                img_bytes = base64.b64decode(b64str)
                images.append((img_bytes, None))
                logger.debug(f"解码 base64 图片: {len(img_bytes)} bytes")
            except Exception as e:
                logger.warning(f"Base64 解码失败: {e}")

        # 3. URL 图片处理
        for match in _URL_PATTERN.finditer(content):
            url = match.group(0)
            if any(url.lower().endswith(ext) for ext in _IMAGE_EXTS):
                images.append((None, url))

        # 4. 文本清理
        text_content = content
        for pattern in _CLEANUP_PATTERNS:
            text_content = pattern.sub('', text_content)

        text_content = _WHITESPACE_PATTERN.sub('\n', text_content)
        text_content = _LINE_SPACES_PATTERN.sub('', text_content)
        text_content = text_content.strip()

    return images, text_content if text_content else None

async def process_images_from_content(
    image_list: List[Tuple[Optional[bytes], Optional[str]]],
    text_content: Optional[str],
    client: httpx.AsyncClient
) -> List[Tuple[Optional[bytes], Optional[str], Optional[str]]]:
    """处理从内容中提取的图片"""
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

    return results

def is_openai_compatible() -> bool:
    """检测是否使用 OpenAI 兼容模式"""
    url = plugin_config.gemini_api_url.lower()
    return "openai" in url or "/v1/chat/completions" in url

def get_valid_api_keys() -> list:
    """获取有效的 API Keys"""
    keys = plugin_config.gemini_api_keys
    if not keys or (len(keys) == 1 and keys[0] == "xxxxxx"):
        raise RuntimeError("请先在 env 中配置有效的 Gemini API Key")
    return keys

def encode_image_to_base64(image: Image.Image) -> str:
    """将 PIL Image 编码为 base64 字符串"""
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def build_request_config(api_key: str) -> Tuple[str, Dict[str, str], str]:
    """构建请求配置（URL、Headers、API类型）"""
    if is_openai_compatible():
        url = plugin_config.gemini_api_url
        if not url.endswith('v1/chat/completions'):
            url = url.rstrip('/') + 'v1/chat/completions'

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        return url, headers, "openai"
    else:
        # 处理 Gemini API URL，避免重复路径
        base_url = plugin_config.gemini_api_url.rstrip('/')

        # 移除可能存在的 /v1beta 后缀，然后统一添加完整路径
        if base_url.endswith('/v1beta'):
            base_url = base_url[:-7]

        url = f"{base_url}/v1beta/models/{plugin_config.gemini_model}:generateContent?key={api_key}"

        headers = {"Content-Type": "application/json"}

        return url, headers, "gemini"

def build_payload(api_type: str, images: list, prompt: str) -> Dict[str, Any]:
    """根据API类型构建请求载荷"""
    if api_type == "openai":
        content_parts = [{"type": "text", "text": prompt}]

        for img in images:
            b64data = encode_image_to_base64(img)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64data}"}
            })

        return {
            "model": plugin_config.gemini_model,
            "messages": [{"role": "user", "content": content_parts}]
        }
    else:
        # Gemini API格式
        parts = [{"text": prompt}]

        for img in images:
            b64data = encode_image_to_base64(img)
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": b64data
                }
            })

        # 安全设置
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
        ]

        return {
            "safetySettings": safety_settings,
            "contents": [{
                "parts": parts
            }]
        }

def parse_api_response(data: Dict[str, Any], api_type: str) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str]]:
    """解析API响应，返回(content, parts, error_message)"""
    if data.get("error"):
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return None, None, f"API 返回错误: {msg}"

    if api_type == "openai":
        choices = data.get("choices", [])
        if not choices:
            return None, None, "返回 choices 为空"

        msg = choices[0].get("message", {}) or {}
        content = msg.get("content", "")
        return content, None, None
    else:
        # Gemini API 处理

        # 1. 检查 promptFeedback 是否被屏蔽
        prompt_feedback = data.get("promptFeedback", {})

        block_reason = prompt_feedback.get("blockReason")
        if block_reason:
            reason_map = {
                "PROHIBITED_CONTENT": "提示包含被禁止的内容",
                "BLOCKED_REASON_UNSPECIFIED": "提示被屏蔽（原因未指定）",
                "SAFETY": "提示因安全原因被屏蔽",
                "OTHER": "提示因其他原因被屏蔽"
            }
            readable_reason = reason_map.get(block_reason, f"提示被屏蔽：{block_reason}")
            return None, None, f"提示被屏蔽: {readable_reason}"

        if prompt_feedback.get("safetyRatings") is None and "safetyRatings" in prompt_feedback:
            return None, None, "提示被安全过滤器屏蔽"

        # 2. 检查是否有 candidates
        candidates = data.get("candidates")

        # 情况3: candidates 为 None 或空列表，且没有明确的屏蔽原因
        if candidates is None:
            return None, None, "请求被拒绝，可能因为内容安全策略"

        if not candidates:  # 空列表
            return None, None, "返回 candidates 为空"

        candidate = candidates[0]

        # 3. 检查 candidate 的 finishReason 是否表示被屏蔽
        finish_reason = candidate.get("finishReason")
        if finish_reason in ["SAFETY", "RECITATION", "PROHIBITED_CONTENT"]:
            finish_reason_map = {
                "SAFETY": "响应因安全原因被屏蔽",
                "RECITATION": "响应因引用原因被屏蔽",
                "PROHIBITED_CONTENT": "响应包含被禁止的内容"
            }
            readable_reason = finish_reason_map.get(finish_reason, f"响应被屏蔽：{finish_reason}")
            return None, None, f"响应被屏蔽: {readable_reason}"

        # 4. 正常解析内容
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])
        if not parts:
            return None, None, "返回 parts 为空"

        # 过滤掉 thought=true 的部分，只保留实际内容
        actual_parts = [p for p in parts if not p.get("thought", False)]

        if not actual_parts:
            return None, None, "返回 parts 中没有实际内容（都是 thought）"

        # 拼接所有文本内容
        content = ""
        for part in actual_parts:
            text = part.get("text", "")
            if text:
                content += text + "\n"

        content = content.strip()

        return content, actual_parts, None

def handle_http_error(status_code: int, response_text: str, attempt: int) -> str:
    """处理HTTP错误"""
    error_msg = f"HTTP {status_code}: {response_text[:200]}"
    logger.warning(f"[Attempt {attempt}] HTTP 错误，切换 Key：{status_code}")
    return error_msg

def handle_network_error(error: Exception, attempt: int) -> Tuple[str, bool]:
    """处理网络错误，返回(error_message, is_connection_error)"""
    if isinstance(error, httpx.TimeoutException):
        error_msg = f"请求超时（90秒无响应）: {error}"
        logger.warning(f"[Attempt {attempt}] 请求超时，切换 Key：{error}")
        return error_msg, True
    elif isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
        error_msg = f"网络连接失败: {error}"
        logger.warning(f"[Attempt {attempt}] 无法连接到 API，切换 Key：{error}")
        return error_msg, True
    else:
        error_msg = f"未知异常: {error}"
        logger.warning(f"[Attempt {attempt}] 发生异常，切换 Key：{error}")
        return error_msg, False

def generate_final_error_message(max_attempts: int, last_error: str, api_connection_failed: bool) -> str:
    """生成最终的错误消息"""
    if api_connection_failed:
        if "超时" in last_error:
            return (
                f"已尝试 {max_attempts} 次，均请求超时。\n"
                f"API 服务可能繁忙，请稍后再试。\n"
                f"最后错误：{last_error}"
            )
        else:
            return (
                f"已尝试 {max_attempts} 次，均无法连接到 API。\n"
                f"请检查网络连接或 API 地址配置。\n"
                f"最后错误：{last_error}"
            )
    else:
        return (
            f"已尝试 {max_attempts} 次，仍未成功。\n"
            f"最后错误：{last_error}"
        )

async def generate_template_images(
    images: List[Image.Image],
    prompt: Optional[str] = None
) -> List[Tuple[Optional[bytes], Optional[str], Optional[str]]]:
    """调用 Gemini/OpenAI 接口生成图片"""
    global _current_api_key_idx

    # 获取API Keys
    keys = get_valid_api_keys()

    if not images:
        raise RuntimeError("没有传入任何图片")

    last_err = ""
    api_connection_failed = False

    for attempt in range(1, plugin_config.max_total_attempts + 1):
        # 选择 API Key
        idx = _current_api_key_idx % len(keys)
        key = keys[idx]
        _current_api_key_idx += 1

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                # 构建请求配置
                url, headers, api_type = build_request_config(key)

                # 构建请求载荷
                payload = build_payload(api_type, images, prompt)

                # 发送请求
                resp = await client.post(url, headers=headers, json=payload)

                # 成功连接，重置标记
                api_connection_failed = False

                # 检查 HTTP 状态码
                if resp.status_code != 200:
                    last_err = handle_http_error(resp.status_code, resp.text, attempt)
                    await asyncio.sleep(1)
                    continue

                # 解析 JSON 响应
                try:
                    data = resp.json()
                except Exception as e:
                    last_err = f"JSON 解析失败: {e}"
                    logger.warning(f"[Attempt {attempt}] JSON 解析失败：{e}")
                    continue

                # 解析 API 响应内容
                content, parts, error_msg = parse_api_response(data, api_type)
                if error_msg:
                    last_err = error_msg
                    logger.warning(f"[Attempt {attempt}] {error_msg}")
                    continue

                # 提取图片和文本
                image_list, text_content = extract_images_and_text(content, parts, api_type)

                logger.info(f"提取到 {len(image_list)} 张图片")
                logger.info(f"提取到的文本: {text_content[:100] if text_content else 'None'}")

                if not image_list:
                    last_err = f"content 中未找到图片数据（API类型: {api_type}）"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    if api_type == "gemini":
                        logger.debug(f"Gemini parts: {json.dumps(parts, ensure_ascii=False, indent=2)}")
                    else:
                        logger.debug(f"OpenAI content: {content[:500]}")
                    continue

                # 处理所有图片
                results = await process_images_from_content(image_list, text_content, client)

                if results:
                    logger.info(f"成功解析 {len(results)} 张图片")
                    return results
                else:
                    last_err = "所有图片解析均失败"
                    logger.warning(f"[Attempt {attempt}] {last_err}")
                    continue

        except Exception as e:
            last_err, is_connection_error = handle_network_error(e, attempt)
            if is_connection_error:
                api_connection_failed = True
            await asyncio.sleep(1)
            continue

    # 生成最终错误消息
    error_message = generate_final_error_message(
        plugin_config.max_total_attempts,
        last_err,
        api_connection_failed
    )
    raise RuntimeError(error_message)

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
