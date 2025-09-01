import httpx, base64, asyncio
from io import BytesIO
from typing import List, Optional, Tuple
from random import randint
from nonebot import logger, on_command, get_driver, get_plugin_config
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.params import Depends
from nonebot.plugin import PluginMetadata
from PIL import Image
from .config import Config


usage = """
    @我+手办化查看详细指令
"""

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="图片手办化",
    description="一个图片手办化插件",
    usage=usage,
    type="application",
    homepage="https://github.com/padoru233/nonebot-plugin-figurine",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

plugin_config: Config = get_plugin_config(Config).figurine

# 记录当前应该使用的API Key的索引
_current_api_key_idx: int = 0


@get_driver().on_startup
async def _():
    # 更新启动日志信息
    logger.info(f"Gemini API URL: {plugin_config.gemini_api_url}, Gemini MODEL: {plugin_config.gemini_model}.\nLoaded {len(plugin_config.gemini_api_keys)} API Keys, Max attempts per key: {plugin_config.max_api_key_attempts}.")

# 结束匹配器并发送消息
async def fi(matcher: Matcher, message: str) -> None:
    await matcher.finish(message)

# 记录日志并结束匹配器
async def log_and_send(matcher: Matcher, title: str, details: str = "") -> None:
    full_message = f"{title}\n{details}" if details else title
    logger.info(f"{title}: {details}")
    await matcher.send(full_message)

# 获取message
async def msg_reply(event: GroupMessageEvent):
    return event.reply.message_id if event.reply else None

# 获取 event 内所有的图片，返回 list
async def get_images(event: GroupMessageEvent) -> List[Image.Image]:
    msg_images = event.message["image"]
    images: List[Image.Image] = []
    for seg in msg_images:
        url = seg.data["url"]
        async with httpx.AsyncClient() as client:
            r = await client.get(url, follow_redirects=True)
        if r.is_success:
            images.append(Image.open(BytesIO(r.content)))
        else:
            logger.error(f"Cannot fetch image from {url} msg#{event.message_id}")
    return images

# 从回复的消息中获取图片
async def get_images_from_reply(bot: Bot, reply_msg_id: int) -> List[Image.Image]:
    try:
        # 获取回复的消息详情
        msg_data = await bot.get_msg(message_id=reply_msg_id)
        message = msg_data["message"]

        images: List[Image.Image] = []
        # 解析消息中的图片
        for seg in message:
            if seg["type"] == "image":
                url = seg["data"]["url"]
                async with httpx.AsyncClient() as client:
                    r = await client.get(url, follow_redirects=True)
                if r.is_success:
                    images.append(Image.open(BytesIO(r.content)))
                else:
                    logger.error(f"Cannot fetch image from {url}")
        return images
    except Exception as e:
        logger.error(f"Error getting images from reply {reply_msg_id}: {e}")
        return []

# 调用 Gemini API
async def call_openai_compatible_api(images: List[Image.Image], prompt: str = None) -> Tuple[Optional[str], Optional[str]]:
    global _current_api_key_idx

    # 检查API Key配置
    num_keys = len(plugin_config.gemini_api_keys)
    if num_keys == 0 or (num_keys == 1 and plugin_config.gemini_api_keys[0] == 'xxxxxx'):
        raise ValueError("API Keys 未配置或配置错误")

    if not prompt:
        prompt = plugin_config.default_prompt

    # 构建API请求的固定部分
    url = f"{plugin_config.gemini_api_url}/v1/chat/completions"

    # 准备消息内容
    content = [{"type": "text", "text": prompt}]
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_str}"
            }
        })

    payload = {
        "model": plugin_config.gemini_model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1000,
    }

    last_error = "所有API Key尝试失败"

    # 从配置中获取每个Key的最大尝试次数
    max_attempts_per_key = plugin_config.max_api_key_attempts

    # 循环尝试所有Key，从当前索引开始
    for _ in range(num_keys):
        # 获取当前要使用的Key及其原始索引
        current_key_original_idx = _current_api_key_idx
        current_key = plugin_config.gemini_api_keys[current_key_original_idx]

        logger.info(f"尝试使用 API Key (原始序号: {current_key_original_idx + 1}/{num_keys})")

        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_attempts_per_key):
            if attempt > 0:
                await asyncio.sleep(2 * attempt) # 指数退避

            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(url, headers=headers, json=payload)

                    if not response.is_success:
                        error_detail = f"HTTP {response.status_code}, 响应: {response.text}"
                        last_error = f"API请求失败: {error_detail}"
                        logger.warning(f"API Key (原始序号: {current_key_original_idx + 1}) (尝试 {attempt + 1}/{max_attempts_per_key}) 失败: {last_error}")
                        continue # 尝试当前Key的下一次重试

                    result = response.json()

                    image_output = None
                    text_output = None

                    if 'choices' in result and result['choices']:
                        choice = result['choices'][0]
                        message = choice.get('message', {})

                        if 'content' in message:
                            content_data = message['content']
                            if isinstance(content_data, str):
                                text_output = content_data.strip()
                            elif isinstance(content_data, list):
                                text_parts = []
                                for part in content_data:
                                    if part.get('type') == 'text' and 'text' in part:
                                        text_parts.append(part['text'])
                                if text_parts:
                                    text_output = '\n'.join(text_parts).strip()

                        if 'images' in message and isinstance(message['images'], list) and len(message['images']) > 0:
                            for img_item in message['images']:
                                if isinstance(img_item, dict) and 'image_url' in img_item:
                                    image_output = img_item['image_url']['url']
                                    break

                    if 'error' in result:
                        error_msg = result['error'].get('message', '未知API错误')
                        last_error = f"API返回错误信息: {error_msg}"
                        logger.warning(f"API Key (原始序号: {current_key_original_idx + 1}) (尝试 {attempt + 1}/{max_attempts_per_key}) 失败: {last_error}")
                        continue

                    # 如果成功获取到图片或文本，则返回
                    if image_output or text_output:
                        logger.info(f"API Key (原始序号: {current_key_original_idx + 1}) 成功 (尝试 {attempt + 1}/{max_attempts_per_key})。下次将从 Key {((_current_api_key_idx + 1) % num_keys) + 1} 开始尝试。")
                        _current_api_key_idx = (current_key_original_idx + 1) % num_keys # 成功后更新索引
                        return image_output, text_output

                    last_error = "API调用成功但未返回图片或文本内容"
                    logger.warning(f"API Key (原始序号: {current_key_original_idx + 1}) (尝试 {attempt + 1}/{max_attempts_per_key}) 失败: {last_error}")
                    continue

            except httpx.RequestError as e:
                last_error = f"网络请求失败: {e}"
                logger.warning(f"API Key (原始序号: {current_key_original_idx + 1}) (尝试 {attempt + 1}/{max_attempts_per_key}) 网络错误: {last_error}")
            except Exception as e:
                last_error = f"处理响应时发生错误: {e}"
                logger.warning(f"API Key (原始序号: {current_key_original_idx + 1}) (尝试 {attempt + 1}/{max_attempts_per_key}) 异常: {last_error}")

        # 如果当前Key的所有尝试都失败了，则更新索引，继续下一个Key
        logger.error(f"API Key (原始序号: {current_key_original_idx + 1}, Key: {current_key[:5]}...) 所有 {max_attempts_per_key} 次尝试均失败。切换到下一个Key...")
        _current_api_key_idx = (current_key_original_idx + 1) % num_keys # 失败后更新索引

    # 如果所有Key的所有尝试都失败了
    raise Exception(f"所有API Key尝试失败，请检查配置或稍后再试。最后错误: {last_error}")


# 命令处理器
figurine_cmd = on_command(
    '手办化',
    aliases={'figurine', 'makefigurine'},
    priority=5,
    block=True,
)

@figurine_cmd.handle()
async def handle_figurine_cmd(bot: Bot, matcher: Matcher, event: GroupMessageEvent, rp = Depends(msg_reply)):

    SUCCESS_MESSAGE = "手办化完成！"
    NO_IMAGE_GENERATED_MESSAGE = "手办化处理完成，但未能生成图片，请稍后再试或尝试其他图片。"

    try:
        images: List[Image.Image] = []

        if rp:
            images.extend(await get_images_from_reply(bot, rp))

        if not images:
            images.extend(await get_images(event))

        if not images:
            await matcher.finish('请回复包含图片的消息或发送图片')

        await matcher.send("正在手办化处理中...")

        await asyncio.sleep(randint(1, 3))

        image_result, _ = await call_openai_compatible_api(images)

        message_to_send = Message()

        if image_result:
            message_to_send += MessageSegment.image(file=image_result)
            message_to_send += f"\n{SUCCESS_MESSAGE}"
            await matcher.finish(message_to_send)
        else:
            await matcher.finish(NO_IMAGE_GENERATED_MESSAGE)

    except MatcherException:
        return  # 正常结束，不需要处理
    except ValueError as e:
        await matcher.finish(f"配置错误: {str(e)}")
    except ActionFailed as e:
        logger.error(f"手办化处理失败 (发送消息错误): retcode={e.retcode}, message={e.message}", exc_info=True)
        await matcher.finish("手办化处理失败，请稍后再试 (发送消息错误)")
    except Exception as e:
        logger.error(f"手办化处理失败: {e}", exc_info=True)
        await matcher.finish(f"手办化处理失败，请稍后再试。错误信息: {e}")
