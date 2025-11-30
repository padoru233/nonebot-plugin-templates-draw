import os, re, httpx, asyncio, base64, json
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict, Union
from PIL import Image, ImageDraw, ImageFont
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

# 加载字体路径
CURRENT_DIR = Path(__file__).parent
FONT_PATH = CURRENT_DIR / "resources" / "FZMINGSTJW.TTF"

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

_BASE64_PATTERN = re.compile(r'data:image/[^;,\s]+;base64,([A-Za-z0-9+/=\s]+)')
_URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'<>]+')
_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
_MARKDOWN_CLEANUP = [
    re.compile(r'!\[.*?\]\(.*?\)'),             # ![alt](url) 完整的 Markdown 图片
    re.compile(r'\[.*?\]\(\s*\)'),              # [text]() 空链接
    re.compile(r'\[下载\d*\]\(\s*\)'),          # 特定标记
    re.compile(r'\[图片\d*\]\(\s*\)'),
    re.compile(r'\[image\d*\]\(\s*\)', re.IGNORECASE),
]

_WHITESPACE_PATTERN = re.compile(r'\n\s*\n')
_LINE_SPACES_PATTERN = re.compile(r'^\s+|\s+$', re.MULTILINE)


def extract_images_and_text(
    content: Optional[Union[str, List]],
    parts: Optional[List[Dict]] = None,
    api_type: str = "openai"
) -> Tuple[List[Tuple[Optional[bytes], Optional[str]]], Optional[str]]:
    """
    从 content 或 parts 中提取所有图片（base64 和 URL）以及文本
    """
    images = []
    text_content = ""

    # 处理 Base64
    def _handle_base64_match(match):
        try:
            b64str = re.sub(r'\s+', '', match.group(1))
            img_bytes = base64.b64decode(b64str)
            images.append((img_bytes, None))
            logger.debug(f"提取并清理 Base64 图片: {len(img_bytes)} bytes")
            return ""  # 返回空字符串以从文本中删除
        except Exception as e:
            logger.warning(f"Base64 提取失败: {e}")
            return match.group(0) # 失败则保留原样

    # 处理 URL
    def _handle_url_match(match):
        url = match.group(0)
        # 检查是否为图片后缀
        if any(url.lower().endswith(ext) for ext in _IMAGE_EXTS):
            images.append((None, url))
            logger.debug(f"提取并清理 URL 图片: {url}")
            return ""  # 是图片，提取并从文本删除
        else:
            return url # 不是图片（如普通网页链接），保留在文本中

    # --- 1. Gemini 处理逻辑 ---
    if api_type == "gemini" and parts:
        for part in parts:
            if part.get("thought", False): continue

            if "text" in part:
                text_content += part["text"] + "\n"

            if "inlineData" in part:
                inline = part["inlineData"]
                if inline.get("mimeType", "").startswith("image/"):
                    try:
                        img_bytes = base64.b64decode(inline.get("data", ""))
                        images.append((img_bytes, None))
                    except Exception as e:
                        logger.warning(f"Gemini inline decode fail: {e}")

            if "fileData" in part:
                fdata = part["fileData"]
                if fdata.get("mimeType", "").startswith("image/") and fdata.get("fileUri"):
                    images.append((None, fdata["fileUri"]))

        text_content = text_content.strip()

    # --- 2. OpenAI 列表格式处理 ---
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict): continue

            if part.get("type") == "text":
                text_content += part.get("text", "") + "\n"

            elif part.get("type") == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:image/"):
                    match = _BASE64_PATTERN.match(url)
                    if match:
                        try:
                            b64str = re.sub(r'\s+', '', match.group(1))
                            images.append((base64.b64decode(b64str), None))
                        except Exception: pass
                elif url:
                    images.append((None, url))

        text_content = text_content.strip()

    # --- 3. 字符串混合内容处理 ---
    elif isinstance(content, str):
        text_content = content

        # 优先提取并清理 Base64 (防止 Base64 字符串太长干扰后续正则)
        text_content = _BASE64_PATTERN.sub(_handle_base64_match, text_content)

        # 提取并清理图片 URL (保留普通链接)
        text_content = _URL_PATTERN.sub(_handle_url_match, text_content)

        # 清理 Markdown 图片标记和其他残留
        for pattern in _MARKDOWN_CLEANUP:
            text_content = pattern.sub('', text_content)

        # 格式化空白
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
    # 获取解除限制提示词
    sys_prompt = getattr(plugin_config, 'jailbreak_prompt', "")

    if api_type == "openai":
        # 构建 User 内容（包含文本和图片）
        user_content_parts = [{"type": "text", "text": prompt}]
        for img in images:
            b64data = encode_image_to_base64(img)
            user_content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64data}"}
            })

        # 构建消息列表
        messages = []

        # 添加为 system 角色
        if sys_prompt:
            messages.append({
                "role": "system",
                "content": sys_prompt
            })

        # 添加 User 消息
        messages.append({
            "role": "user",
            "content": user_content_parts
        })

        return {
            "model": plugin_config.gemini_model,
            "messages": messages
        }

    else:
        # Gemini API格式
        user_parts = [{"text": prompt}]

        for img in images:
            b64data = encode_image_to_base64(img)
            user_parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": b64data
                }
            })

        # 安全设置
        payload = {
            "contents": [{
                "parts": user_parts
            }],
            # 如果有其他生成配置(temperature等)，通常放在 generationConfig 字段
            # "generationConfig": { ... },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
            ]
        }

        if sys_prompt:
            payload["systemInstruction"] = {
                "parts": [
                    {"text": sys_prompt}
                ]
            }

        return payload

def parse_api_response(data: Dict[str, Any], api_type: str) -> Tuple[Optional[Union[str, List]], Optional[List[Dict]], Optional[str]]:
    """
    解析API响应，返回(content, parts, error_message)
    兼容OR会把图片放在 message.images 里
    """
    if data.get("error"):
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return None, None, f"API 返回错误: {msg}"

    if api_type == "openai":
        choices = data.get("choices", [])
        if not choices:
            return None, None, "返回 choices 为空"

        msg = choices[0].get("message", {}) or {}
        content = msg.get("content")

        # 检查是否有单独的 images 字段
        images_field = msg.get("images")

        if images_field and isinstance(images_field, list):
            # 将 images 合并到 content 中
            if isinstance(content, list):
                # content 已经是列表，直接追加
                content.extend(images_field)
            elif isinstance(content, str):
                # content 是字符串，转换为列表
                content_parts = []
                if content:  # 如果有文本内容
                    content_parts.append({"type": "text", "text": content})
                content_parts.extend(images_field)
                content = content_parts
            else:
                # content 为空，直接使用 images
                content = images_field

            logger.debug(f"合并 message.images 到 content，共 {len(images_field)} 张图片")

        # 确保 content 存在
        if content is None:
            return None, None, "message.content 和 message.images 都为空"

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

                # 获取原始响应
                logger.debug(f"[Attempt {attempt}] 原始响应状态码: {resp.status_code}")
                logger.debug(f"[Attempt {attempt}] 原始响应头: {dict(resp.headers)}")

                raw_response_text = resp.text
                logger.debug(f"[Attempt {attempt}] 原始响应内容 (前1000字符): {raw_response_text[:1000]}")

                # 如果响应很长，也记录完整长度
                if len(raw_response_text) > 1000:
                    logger.debug(f"[Attempt {attempt}] 原始响应总长度: {len(raw_response_text)} 字符")

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
                    last_err = f"返回内容为空或者未找到图片数据"
                    logger.warning(f"[Attempt {attempt}] {last_err}（API类型: {api_type}）")
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
    # 构造虚拟发送者信息
    sender = event.sender
    sender_name = getattr(sender, "nickname", None) or getattr(sender, "card", None) or str(event.user_id)
    sender_id = str(event.user_id)

    nodes = []

    # --- 定义一个内部辅助函数，生成全兼容节点 ---
    def _create_node(content: Message):
        return {
            "type": "node",
            "data": {
                "user_id": sender_id, "nickname": sender_name, # 标准 OneBot V11
                "uin": sender_id,     "name": sender_name,     # 兼容 Lagrange / LLonebot
                "content": content
            }
        }

    # 1. 遍历结果
    for idx, (img_bytes, img_url, text) in enumerate(results, start=1):

        # --- 纯文本 ---
        if text:
            nodes.append(_create_node(Message(text)))

        # --- 纯图片 ---
        image_seg = None
        if img_bytes:
            image_seg = MessageSegment.image(file=img_bytes)
        elif img_url:
            image_seg = MessageSegment.image(url=img_url)

        if image_seg:
            nodes.append(_create_node(Message(image_seg)))

    if not nodes:
        await bot.send(event, "⚠️ 未生成任何内容")
        return

    # 2. 发送合并转发
    try:
        await bot.call_api(
            "send_group_forward_msg",
            group_id=event.group_id,
            messages=nodes
        )
        logger.debug(f"[draw] 合并转发成功")

    except Exception as e:
        logger.exception(f"[draw] 合并转发失败：{e}")
        await bot.send(event, "合并转发发送失败，请检查日志。")

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

def find_template(templates: Dict[str, str], name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    查找模板
    """
    # 精确匹配
    if name in templates:
        return name, templates[name]

    # 模糊匹配
    matches = []
    for k, v in templates.items():
        if name.lower() in k.lower():
            matches.append((k, v))

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        msg = f"🔍 找到 {len(matches)} 个匹配的模板：\n\n"
        for i, (k, v) in enumerate(matches, 1):
            preview = v[:20] + "..." if len(v) > 20 else v
            preview = preview.replace('\n', ' ')
            msg += f"{i}. {k}\n   预览: {preview}\n\n"
        msg += "💡 请使用更精确的名称"
        raise ValueError(msg)
    else:
        raise ValueError(f"❌ 未找到模板：{name}")

def format_template_list(templates: Dict[str, str]) -> str:
    """
    格式化模板列表为文本
    """
    msg = "📋 当前模板列表\n"
    msg += f"{'='*20}\n"

    for k, v in templates.items():
        msg += f"- {k} : {v[:15]}...\n"
    msg += "\n💡 使用 '查看模板 <模板标志>' 查看具体内容"

    return msg

def format_template_content(name: str, content: str) -> str:
    """
    格式化单个模板内容为文本
    """
    msg = f"📋 模板名称：{name}\n"
    msg += f"{'='*20}\n"
    msg += f"{content}"

    # 如果内容太长，截断显示
    if len(msg) > 1900:
        msg = msg[:1900] + "\n\n...(内容过长，已截断)"

    return msg

async def templates_to_image(templates_dict: Dict[str, str]) -> bytes:
    """
    将模板字典转换为图片
    """
    try:
        loop = asyncio.get_event_loop()
        image_bytes = await loop.run_in_executor(None, _create_text_image, templates_dict)
        return image_bytes
    except Exception as e:
        logger.warning(f"模板字典转图片失败: {str(e)}")
        raise

def _create_text_image(templates: Dict[str, str]) -> bytes:

    # 加载字体
    try:
        if FONT_PATH.exists():
            logger.debug(f"找到字体文件: {FONT_PATH}")
            font_header = ImageFont.truetype(str(FONT_PATH), 24)
            font_item = ImageFont.truetype(str(FONT_PATH), 18)
            font_tip = ImageFont.truetype(str(FONT_PATH), 16)
        else:
            raise FileNotFoundError(f"字体文件不存在: {FONT_PATH}")
    except Exception as e:
        logger.debug(f"加载包内字体失败: {e}")
        font_header = ImageFont.load_default()
        font_item = ImageFont.load_default()
        font_tip = ImageFont.load_default()

    def calculate_text_length(text: str) -> float:
        """计算文本长度，以中文为基准"""
        length = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                length += 1
            else:  # 英文字符
                length += 0.4
        return length

    def wrap_text(text: str, max_chars: int = 20) -> list:
        """文本换行，按字符长度分割"""
        lines = []
        current_line = ""
        current_length = 0

        for char in text:
            char_length = 1 if '\u4e00' <= char <= '\u9fff' else 0.4  # 统一使用0.4

            if current_length + char_length > max_chars:
                if current_line:
                    lines.append(current_line)
                    current_line = char
                    current_length = char_length
                else:
                    lines.append(char)
                    current_line = ""
                    current_length = 0
            else:
                current_line += char
                current_length += char_length

        if current_line:
            lines.append(current_line)

        return lines

    def calculate_item_height(name: str, content: str) -> int:
        """计算单个模板项需要的高度"""
        base_height = 35  # 基础高度（模板名称行）
        line_height = 20  # 每行高度

        # 计算内容预览需要的行数
        preview = content.strip().replace("\n", " ")
        preview_lines = wrap_text(preview, 20)  # 统一使用20

        # 最多显示3行预览
        preview_lines = preview_lines[:3]
        if len(wrap_text(preview, 20)) > 3:  # 统一使用20
            if len(preview_lines) == 3:
                # 重新计算第3行的截断位置，确保加上"..."后不超出限制
                line3_length = 0
                truncated_line3 = ""
                for char in preview_lines[2]:
                    char_length = 1 if '\u4e00' <= char <= '\u9fff' else 0.4  # 统一使用0.4
                    if line3_length + char_length + 1.5 > 20:  # 预留"..."的空间，统一使用20
                        break
                    truncated_line3 += char
                    line3_length += char_length
                preview_lines[2] = truncated_line3 + "..."

        return base_height + len(preview_lines) * line_height + 10  # 额外10px边距

    # 配置
    width = 400
    padding = 20
    header_height = 60
    footer_height = 50
    item_spacing = 15

    # 计算每个模板项的高度
    item_heights = []
    if templates:
        for name, content in templates.items():
            item_heights.append(calculate_item_height(name, content))
    else:
        item_heights = [60]  # 空模板提示的高度

    # 总高度（底部多加一个padding作为白边）
    total_item_height = sum(item_heights)
    total_spacing = (len(item_heights) - 1) * item_spacing if len(item_heights) > 1 else 0
    height = padding + header_height + total_item_height + total_spacing + footer_height + padding * 3  # 底部增加更多padding

    # 新建画布
    img = Image.new('RGB', (width, height), '#ffffff')
    draw = ImageDraw.Draw(img)

    y = padding

    # 1. 画标题区的背景框和文字
    header_box = [padding, y, width - padding, y + header_height]
    draw.rectangle(header_box, fill='#e8eaf6', outline='#3f51b5', width=2)
    title = "当前模板列表"

    # 使用 textbbox 替代 textsize
    bbox = draw.textbbox((0, 0), title, font=font_header)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    draw.text(((width-w)//2, y + (header_height-h)//2),
              title, fill='#1a237e', font=font_header)
    y += header_height + item_spacing

    # 2. 画每一条模板项的区域并填文字
    if templates:
        for i, (name, content) in enumerate(templates.items()):
            item_height = item_heights[i]
            box = [padding, y, width - padding, y + item_height]
            draw.rectangle(box, fill='#f1f8e9', outline='#4caf50', width=1)

            # 模板名称
            name_x = padding + 8
            name_y = y + 8
            draw.text((name_x, name_y), f"• {name}", fill='#2e7d32', font=font_item)

            # 描述 preview（支持换行）
            preview = content.strip().replace("\n", " ")
            preview_lines = wrap_text(preview, 20)  # 统一使用20
            preview_lines = preview_lines[:3]  # 最多3行

            if len(wrap_text(preview, 20)) > 3:  # 统一使用20
                if len(preview_lines) == 3:
                    # 重新计算第3行的截断位置
                    line3_length = 0
                    truncated_line3 = ""
                    for char in preview_lines[2]:
                        char_length = 1 if '\u4e00' <= char <= '\u9fff' else 0.4  # 统一使用0.4
                        if line3_length + char_length + 1.5 > 20:  # 预留"..."的空间，统一使用20
                            break
                        truncated_line3 += char
                        line3_length += char_length
                    preview_lines[2] = truncated_line3 + "..."

            # 绘制每一行预览文本
            for j, line in enumerate(preview_lines):
                draw.text((name_x, name_y + 25 + j * 20),
                          line, fill='#616161', font=font_tip)

            y += item_height + item_spacing
    else:
        # 空字典时显示提示
        item_height = item_heights[0]
        box = [padding, y, width - padding, y + item_height]
        draw.rectangle(box, fill='#f5f5f5', outline='#9e9e9e', width=1)
        draw.text((padding + 8, y + item_height//2 - 10),
                  "暂无模板", fill='#757575', font=font_item)
        y += item_height + item_spacing

    # 3. 底部提示
    y += 10  # 多留点空隙
    tip = "使用 '查看模板 <模板标志>' 查看具体内容"
    tip_box = [padding, y, width - padding, y + footer_height]
    draw.rectangle(tip_box, fill='#fff8e1', outline='#ff9800', width=1)

    # 提示文字换行处理
    tip_lines = wrap_text(tip, 28)  # 底部提示可以稍微长一点
    for i, line in enumerate(tip_lines):
        draw.text((padding + 8, y + 10 + i * 22),
                  line, fill='#f57c00', font=font_tip)

    # 转为 bytes
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
