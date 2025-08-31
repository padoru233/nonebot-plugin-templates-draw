import httpx, base64, asyncio
from io import BytesIO
from typing import List, Optional, Tuple
from random import randint
from nonebot import logger, on_command
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.params import Depends
from nonebot.plugin import PluginMetadata
from PIL import Image
from .config import PluginConfig, config


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
    config=PluginConfig,
    supported_adapters={"~onebot.v11"},
)


print('Gemini API Key:', config.GEMINI_API_KEY, 'GEMINI_API_URL:',config.GEMINI_API_URL)

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

    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == 'xxxxxx':
        raise ValueError("API Key 未配置")

    if not prompt:
        prompt = config.DEFAULT_PROMPT

    # 构建API请求
    url = f"{config.GEMINI_API_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }

    # 准备消息内容
    content = [{"type": "text", "text": prompt}]

    for img in images:
        # 将图片转换为base64
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
        "model": config.GEMINI_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1000,
    }

    # 简化重试逻辑
    for attempt in range(3):
        if attempt > 0:
            await asyncio.sleep(2 * attempt)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)

                if not response.is_success:
                    raise Exception(f"API请求失败: HTTP {response.status_code}, 响应: {response.text}")

                result = response.json()

                # 解析响应
                image_output = None
                text_output = None # 保持text_output的解析，但我们会在bot逻辑中忽略它

                if 'choices' in result and result['choices']:
                    choice = result['choices'][0]
                    message = choice.get('message', {})

                    # 解析文本内容 (虽然会忽略，但保留解析逻辑以防未来需要)
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
                                image_url_obj = img_item['image_url']
                                if isinstance(image_url_obj, dict) and 'url' in image_url_obj:
                                    image_output = image_url_obj['url']  # 正确的路径
                                    break

                # 检查API错误
                if 'error' in result:
                    error_msg = result['error'].get('message', '未知API错误')
                    raise Exception(error_msg)

                return image_output, text_output

        except Exception as e:
            last_error = str(e)
            logger.error(f"API调用失败 (尝试 {attempt + 1}/3): {last_error}")

            # 最后一次尝试失败时抛出异常
            if attempt == 2:
                raise Exception(f"API调用失败: {last_error}")

    return None, None



# 命令处理器
figurine_cmd = on_command(
    '手办化',
    aliases={'figurine', 'makefigurine'},
    priority=5,
    block=True,
)

@figurine_cmd.handle()
async def handle_figurine_cmd(bot: Bot, matcher: Matcher, event: GroupMessageEvent, rp = Depends(msg_reply)):
    """处理手办化命令 - 简化版错误处理，并使用固定回复语"""

    # 固定回复语
    SUCCESS_MESSAGE = "手办化完成！"
    NO_IMAGE_GENERATED_MESSAGE = "手办化处理完成，但未能生成图片，请稍后再试或尝试其他图片。"

    try:
        images: List[Image.Image] = []

        # 获取图片
        if rp:
            images.extend(await get_images_from_reply(bot, rp))

        if not images:
            images.extend(await get_images(event))

        if not images:
            await matcher.finish('请回复包含图片的消息或发送图片')

        # 发送处理中消息
        await matcher.send("正在手办化处理中...")

        # 添加随机延迟
        await asyncio.sleep(randint(1, 3))

        # 调用API
        image_result, _ = await call_openai_compatible_api(images) # 忽略text_result

        # 构建响应消息
        message_to_send = Message()

        if image_result:
            message_to_send += MessageSegment.image(file=image_result)
            message_to_send += f"\n{SUCCESS_MESSAGE}" # 添加固定的成功消息
            await matcher.finish(message_to_send)
        else:
            # 如果没有图片返回，则发送未生成图片的提示
            await matcher.finish(NO_IMAGE_GENERATED_MESSAGE)

    except MatcherException:
        return  # 正常结束，不需要处理
    except ValueError as e:
        await matcher.finish(f"配置错误: {str(e)}")
    except Exception as e:
        logger.error(f"手办化处理失败: {e}", exc_info=True)
        await matcher.finish("手办化处理失败，请稍后再试")
