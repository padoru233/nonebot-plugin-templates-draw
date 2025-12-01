import re, httpx, asyncio, base64, json
from typing import Dict, Any, List, Optional, Tuple, Union
import httpx
from PIL import Image
from io import BytesIO
from nonebot import logger, get_plugin_config

from .config import Config
from .utils import (
    download_image_from_url,
    build_pdf_from_prompt_and_images
)

plugin_config = get_plugin_config(Config).templates_draw

# 全局轮询 idx
_current_api_key_idx = 0

_BASE64_PATTERN = re.compile(r'data:image/[^;,\s]+;base64,([A-Za-z0-9+/=\s]+)')
_URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'<>]+')
_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
_MARKDOWN_CLEANUP = [
    re.compile(r'!\[.*?\]\(.*?\)'),
    re.compile(r'\[.*?\]\(\s*\)'),
    re.compile(r'\[下载\d*\]\(\s*\)'),
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
    """从 content 或 parts 中提取所有图片（base64 和 URL）以及文本"""
    images = []
    text_content = ""

    def _handle_base64_match(match):
        try:
            b64str = re.sub(r'\s+', '', match.group(1))
            img_bytes = base64.b64decode(b64str)
            images.append((img_bytes, None))
            logger.debug(f"提取清理 Base64 图片: {len(img_bytes)} bytes")
            return ""
        except Exception as e:
            logger.warning(f"Base64 提取失败: {e}")
            return match.group(0)

    def _handle_url_match(match):
        url = match.group(0)
        if any(url.lower().endswith(ext) for ext in _IMAGE_EXTS):
            images.append((None, url))
            logger.debug(f"提取并清理 URL 图片: {url}")
            return ""
        else:
            return url

    if api_type == "gemini" and parts:
        for part in parts:
            if part.get("thought", False):
                continue

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

    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue

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
                        except Exception:
                            pass
                elif url:
                    images.append((None, url))

        text_content = text_content.strip()

    elif isinstance(content, str):
        text_content = content
        text_content = _BASE64_PATTERN.sub(_handle_base64_match, text_content)
        text_content = _URL_PATTERN.sub(_handle_url_match, text_content)

        for pattern in _MARKDOWN_CLEANUP:
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
            text = text_content if idx == 0 else None
            results.append((img_bytes, None, text))
            logger.info(f"成功解码第 {idx + 1} 张图片（Base64），大小: {len(img_bytes)} bytes")
        elif img_url:
            downloaded = await download_image_from_url(img_url, client)
            if downloaded:
                text = text_content if idx == 0 and not results else None
                results.append((downloaded, img_url, text))
                logger.info(f"成功下载第 {idx + 1} 张图片（URL），大小: {len(downloaded)} bytes")
            else:
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

def build_request_config(api_key: str, model_name: str) -> Tuple[str, Dict[str, str], str]:
    """构建请求配置（URL、Headers、API类型）"""
    if is_openai_compatible():
        url = plugin_config.gemini_api_url
        if "chat/completions" not in url:
            url = url.rstrip('/') + '/v1/chat/completions'

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        return url, headers, "openai"
    else:
        base_url = plugin_config.gemini_api_url.rstrip('/')
        if base_url.endswith('/v1beta'):
            base_url = base_url[:-7]

        url = f"{base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        return url, headers, "gemini"

def build_payload(
    api_type: str,
    images: List[Image.Image],
    prompt: str,
    use_pdf: bool
) -> Dict[str, Any]:
    """
    构建请求 Payload

    Args:
        api_type: API 类型 ("openai" 或 "gemini")
        images: PIL Image 列表
        prompt: 用户提示词
        use_pdf: 是否使用 PDF 模式（仅 Gemini Native 支持）
    """
    if api_type == "openai":
        # OpenAI 模式：始终发送图片
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

    else:  # Gemini Native
        if use_pdf:
            # PDF 模式：将 prompt + 图片构建为 PDF
            logger.info("使用 PDF 模式发送（prompt + 参考图）")
            pdf_bytes = build_pdf_from_prompt_and_images(prompt, images)
            pdf_b64 = base64.b64encode(pdf_bytes).decode()

            parts = [
                {
                    "inlineData": {
                        "mimeType": "application/pdf",
                        "data": pdf_b64
                    }
                }
            ]
        else:
            # 图片模式：prompt + 逐个图片
            logger.info("使用图片模式发送（prompt + 参考图）")
            parts = [{"text": prompt}]

            for img in images:
                b64data = encode_image_to_base64(img)
                parts.append({
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": b64data
                    }
                })

        return {
            "contents": [{"role": "user", "parts": parts}],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            ]
        }

def parse_api_response(data: Dict[str, Any], api_type: str) -> Tuple[Optional[Union[str, List]], Optional[List[Dict]], Optional[str]]:
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
        content = msg.get("content")
        images_field = msg.get("images")

        if images_field and isinstance(images_field, list):
            if isinstance(content, list):
                content.extend(images_field)
            elif isinstance(content, str):
                content_parts = []
                if content:
                    content_parts.append({"type": "text", "text": content})
                content_parts.extend(images_field)
                content = content_parts
            else:
                content = images_field

            logger.debug(f"合并 message.images 到 content，共 {len(images_field)} 张图片")

        if content is None:
            return None, None, "message.content 和 message.images 都为空"

        return content, None, None

    else:  # Gemini
        prompt_feedback = data.get("promptFeedback", {})
        block_reason = prompt_feedback.get("blockReason")

        if block_reason:
            reason_map = {
                "PROHIBITED_CONTENT": "提示包含被禁止的内容",
                "BLOCKED_REASON_UNSPECIFIED": "提示被屏蔽（原未指定）",
                "SAFETY": "提示因安全原因被屏蔽",
                "OTHER": "提示因其他原因被屏蔽"
            }
            readable_reason = reason_map.get(block_reason, f"提示被屏蔽：{block_reason}")
            return None, None, f"提示被屏蔽: {readable_reason}"

        candidates = data.get("candidates")
        if candidates is None:
            return None, None, "请求被拒绝，可因为内容安全策略"

        if not candidates:
            return None, None, "返回 candidates 为空"

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")

        if finish_reason in ["SAFETY", "RECITATION", "PROHIBITED_CONTENT"]:
            finish_reason_map = {
                "SAFETY": "因安全原因被屏蔽",
                "RECITATION": "因引用原因被屏蔽",
                "PROHIBITED_CONTENT": "包含被禁止的内容"
            }
            readable_reason = finish_reason_map.get(finish_reason, f"响应被屏蔽：{finish_reason}")
            return None, None, f"响应被屏蔽: {readable_reason}"

        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])

        if not parts:
            return None, None, "返回 parts 为空"

        actual_parts = [p for p in parts if not p.get("thought", False)]
        if not actual_parts:
            return None, None, "返回 parts 中没有实际内容（都是 thought）"

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
    """
    调用 Gemini/OpenAI 接口生成图片
    根据 plugin_config.gemini_pdf_jailbreak 决定是否使用 PDF 模式（仅 Gemini Native）
    """
    global _current_api_key_idx

    keys = get_valid_api_keys()

    if not images:
        raise RuntimeError("没有传入任何图片")

    if not prompt:
        prompt = "请根据参考图生成新图片"

    last_err = ""
    api_connection_failed = False

    # 检查是否使用 PDF 模式（仅 Gemini Native 支持）
    use_pdf = plugin_config.gemini_pdf_jailbreak and not is_openai_compatible()

    for attempt in range(1, plugin_config.max_total_attempts + 1):
        idx = _current_api_key_idx % len(keys)
        key = keys[idx]
        _current_api_key_idx += 1

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                logger.info(f"[Attempt {attempt}] 发送请求 (Model: {plugin_config.gemini_model}, PDF模式: {use_pdf})")

                url, headers, api_type = build_request_config(key, plugin_config.gemini_model)
                payload = build_payload(api_type, images, prompt, use_pdf)

                try:
                    resp = await client.post(url, headers=headers, json=payload)
                except Exception as e:
                    last_err, is_connection_error = handle_network_error(e, attempt)
                    if is_connection_error:
                        api_connection_failed = True
                    await asyncio.sleep(1)
                    continue

                if resp.status_code != 200:
                    last_err = handle_http_error(resp.status_code, resp.text, attempt)
                    await asyncio.sleep(1)
                    continue

                raw_response_text = resp.text
                logger.debug(f"[Attempt {attempt}] 原始响应内容 (前1000字符): {raw_response_text[:1000]}")

                try:
                    data = resp.json()
                except Exception as e:
                    last_err = f"JSON 解析失败: {e}"
                    continue

                content, parts, error_msg = parse_api_response(data, api_type)
                if error_msg:
                    last_err = error_msg
                    continue

                image_list, text_content = extract_images_and_text(content, parts, api_type)

                logger.info(f"提取到 {len(image_list)} 张图片")
                logger.info(f"提取到的文本: {text_content[:100] if text_content else 'None'}")

                if not image_list:
                    last_err = "未找到图片数据"
                    continue

                results = await process_images_from_content(image_list, text_content, client)
                if results:
                    logger.info(f"成功解析 {len(results)} 张图片")
                    return results
                else:
                    last_err = "图片解析/下载失败"
                    continue

        except Exception as e:
            last_err, is_connection_error = handle_network_error(e, attempt)
            if is_connection_error:
                api_connection_failed = True
            await asyncio.sleep(1)
            continue

    error_message = generate_final_error_message(
        plugin_config.max_total_attempts,
        last_err,
        api_connection_failed
    )
    raise RuntimeError(error_message)
