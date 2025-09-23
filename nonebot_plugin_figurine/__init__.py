import httpx, base64, asyncio
import re
from io import BytesIO
from typing import List, Optional, Tuple
from random import randint
from nonebot import logger, on_command, get_driver, get_plugin_config
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.exception import FinishedException
from nonebot.params import Depends, CommandArg
from nonebot.plugin import PluginMetadata
from PIL import Image
from .config import Config


usage = """
    @我+手办化查看详细指令
    使用 '手办化 <关键词>' 来选择特定预设
- 手办化0 :自定义预设，不带参数触发。
- 手办化1 :生成带包装盒、电脑桌背景的写实手办。
- 手办化2 :生成带包装盒、电脑桌背景的写实手办（风格更加固定）。
- 手办化3 :生成带包装盒的写实手办，更注重面部还原。
- 手办化4 :与 变手办1 类似，细节更加丰富，风格略有差异。
- 手办化5 :基于游戏截图风格，微距摄影效果，带木质电脑桌背景。
- 手办化6 :生成可爱的Q版/粘土人风格手办。
- 手办化ntr :生成一张快餐店构图，手机上展示着上传的图片，背景中一对情侣坐在一起接吻。
- 手办化cos :生成一张主题房间构图，房间中有Cosplayer、抱枕、PVC人物等。
- 手办化jio :生成一张人物将脚伸出，夸大展示脚部的透视图。
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
    logger.info(
        f"Gemini API URL: {plugin_config.gemini_api_url}, "
        f"Gemini MODEL: {plugin_config.gemini_model}.\n"
        f"Loaded {len(plugin_config.gemini_api_keys)} API Keys, "
        f"Max total attempts per image: {plugin_config.max_total_attempts}."
    )

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

# 获取用户头像
async def _get_avatar_image(bot: Bot, user_id: int, group_id: Optional[int] = None) -> Optional[Image.Image]:

    avatar_url = None

    try:

        # 构造常用的QQ头像URL。s=0表示原始大小。
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&s=0&nk={user_id}&s=640"

        if avatar_url:
            async with httpx.AsyncClient() as client:
                r = await client.get(avatar_url, follow_redirects=True, timeout=10)
            if r.is_success:
                logger.info(f"Successfully fetched avatar for user {user_id} from {avatar_url}")
                return Image.open(BytesIO(r.content))
            else:
                logger.warning(f"Failed to fetch avatar for user {user_id} from {avatar_url}: HTTP {r.status_code}")
        else:
            logger.warning(f"Could not determine avatar URL for user {user_id}")

    except httpx.RequestError as e:
        logger.warning(f"Network error fetching avatar for user {user_id} from {avatar_url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting avatar for user {user_id}: {e}", exc_info=True)
    return None

async def call_openai_compatible_api(images: List[Image.Image], prompt: str = None) -> Tuple[Optional[str], Optional[str]]:

    global _current_api_key_idx

    # 校验 Keys
    keys = plugin_config.gemini_api_keys
    num_keys = len(keys)

    if num_keys == 0 or (num_keys == 1 and keys[0] == "xxxxxx"):
        raise ValueError("API Keys 未配置或配置错误")

    # 如果传入的 prompt 为空，则使用配置中的 prompt_0
    # 注意：这里的 prompt 参数是由 handle_figurine_cmd 传入的 selected_prompt
    # selected_prompt 已经包含了 fallback 逻辑，所以这里直接使用即可
    if not prompt:
        prompt = plugin_config.prompt_0

    url = f"{plugin_config.gemini_api_url}/v1/chat/completions"

    if not images:
        raise ValueError("没有传入任何图片")

    buf = BytesIO()
    images[0].save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    # 构造请求 payload
    content_parts = [
        {
            "type": "text",
            "text": prompt
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_b64}"
            }
        }
    ]

    payload = {
        "model": plugin_config.gemini_model,
        "messages": [
            {
                "role": "user",
                "content": content_parts
            }
        ]
    }

    max_total_attempts = plugin_config.max_total_attempts
    total_attempts = 0
    last_error = "❎ 未能生成图片，可能图片被判定违规。"

    while total_attempts < max_total_attempts:
        current_key_idx = _current_api_key_idx % num_keys
        key = keys[current_key_idx]
        total_attempts += 1
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        logger.info(f"第 {total_attempts}/{max_total_attempts} 次尝试，使用 Key #{current_key_idx+1}/{num_keys}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            last_error = f"网络错误: {e}"
            logger.warning(f"网络异常 (Key #{current_key_idx+1}, 尝试 {total_attempts}): {last_error}")
            # 切下一个 Key，退避后继续
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            await asyncio.sleep(1)
            continue

        # HTTP 非 2xx
        if not resp.is_success:
            last_error = f"HTTP {resp.status_code}: {resp.text}"
            logger.warning(f"API Key #{current_key_idx+1} 调用失败 (尝试 {total_attempts}): {last_error}")
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            await asyncio.sleep(1)
            continue

        # 保护性 JSON 解析
        try:
            result = resp.json()
        except Exception as e:
            last_error = f"JSON 解析失败: {e}"
            logger.warning(f"Key #{current_key_idx+1} 返回非 JSON 文本 (尝试 {total_attempts})：{resp.text[:200]}")
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            await asyncio.sleep(1)
            continue

        # 确保拿到的是 dict
        if not isinstance(result, dict):
            last_error = f"返回类型非 dict: {type(result)}"
            logger.warning(f"Key #{current_key_idx+1} 返回数据结构异常 (尝试 {total_attempts})：{result}")
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            await asyncio.sleep(1)
            continue

        # 兼容 error 字段（用 get 避免 KeyError）
        err = result.get("error")

        if err:

            # err 可能是 dict，也可能是 str
            if isinstance(err, dict):
                error_msg = err.get("message", "未知错误")
            else:
                error_msg = str(err)
            last_error = f"API 返回 error: {error_msg}"
            logger.warning(f"API Key #{current_key_idx+1} 返回错误 (尝试 {total_attempts}): {last_error}")
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            await asyncio.sleep(1)
            continue

        text_out = None
        img_out = None
        choices = result.get("choices")

        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {}) or {}

            # 返回的图片在 message.images[0].image_url.url
            # 文本在 message.content

            # 获取文本内容
            text_out = msg.get("content")
            if isinstance(text_out, str):
                text_out = text_out.strip()
            else:
                text_out = None

            # 获取图片内容
            images_list = msg.get("images")
            if isinstance(images_list, list) and images_list:
                first_image = images_list[0]
                if isinstance(first_image, dict):
                    image_url_data = first_image.get("image_url")
                    if isinstance(image_url_data, dict):
                        img_out = image_url_data.get("url")

        # 判断是否拿到图片
        if img_out:
            _current_api_key_idx = (current_key_idx + 1) % num_keys
            logger.info(f"成功拿到图片 (Key #{current_key_idx+1}, 尝试 {total_attempts})。下次从 Key #{_current_api_key_idx+1} 开始。")
            return img_out, text_out
        else:
            last_error = last_error or "API 调用成功但未返回图片"
            logger.warning(f"尝试 {total_attempts} 未拿到图片 (Key #{current_key_idx+1}): {last_error}")

        # 本次尝试失败，切换 Key 并退避
        _current_api_key_idx = (current_key_idx + 1) % num_keys
        await asyncio.sleep(1)

    # 用尽所有尝试次数仍未成功
    raise RuntimeError(f"已达最大调用次数 {max_total_attempts}，仍未成功获取图片。最后错误：{last_error}")


figurine_cmd = on_command(
    '手办化',
    aliases={'figurine', 'makefigurine'},
    priority=5,
    block=True,
)

@figurine_cmd.handle()
async def handle_figurine_cmd(bot: Bot,
    matcher: Matcher,
    event: GroupMessageEvent,
    args: Message = CommandArg(),
    rp = Depends(msg_reply)
):

    SUCCESS_MESSAGE = "✅️ 手办化完成！"
    NO_IMAGE_GENERATED_MESSAGE = "❎ 未能生成图片，可能图片被判定违规。"

    try:
        all_images: List[Image.Image] = []
        group_id = event.group_id if isinstance(event, GroupMessageEvent) else None

        # 1. 获取回复消息中的图片
        if rp:
            all_images.extend(await get_images_from_reply(bot, rp))

        # 2. 获取当前消息中的图片，并识别 @ 用户/提及自己
        at_user_ids_from_message: List[int] = []
        mention_self_in_message: bool = False

        # 提取 CommandArg 的纯文本内容，用于后续解析预设关键词
        raw_command_args_text = args.extract_plain_text().strip().lower()
        words_in_args = raw_command_args_text.split()

        for seg in event.message:
            if seg.type == "image":
                url = seg.data["url"]
                async with httpx.AsyncClient() as client:
                    r = await client.get(url, follow_redirects=True)

                if r.is_success:
                    all_images.append(Image.open(BytesIO(r.content)))
                else:
                    logger.error(f"Cannot fetch image from {url} msg#{event.message_id}")
            elif seg.type == "at":
                at_user_ids_from_message.append(int(seg.data["qq"]))
            elif seg.type == "text":
                text_content = str(seg).strip()
                words = re.split(r'\s+', text_content)

                for word in words:
                    if word.lower() == "自己":
                        mention_self_in_message = True
                    elif word.startswith("@") and word[1:].isdigit():
                        at_user_ids_from_message.append(int(word[1:]))

        # 3. 如果前两步没有收集到任何图片，则尝试获取头像
        if not all_images:
            if mention_self_in_message:
                sender_id = event.sender.user_id
                avatar = await _get_avatar_image(bot, sender_id, group_id)
                if avatar:
                    all_images.append(avatar)
                else:
                    logger.warning(f"Could not get avatar for '自己' ({sender_id})")
            for at_user_id in at_user_ids_from_message:
                avatar = await _get_avatar_image(bot, at_user_id, group_id)
                if avatar:
                    all_images.append(avatar)
                else:
                    logger.warning(f"Could not get avatar for @{at_user_id}")

        # 如果没有找到任何图片，则直接结束并发送“请回复图片”的提示
        if not all_images:
            await matcher.finish(
                "💡 请回复包含图片的消息，或发送图片，或@用户/提及自己以获取头像。\n"
                "使用 '手办化 <关键词>' 来选择特定预设：\n"
                "- 手办化0 :自定义预设，不带参数触发。\n"
                "- 手办化1 :生成带包装盒、电脑桌背景的写实手办。\n"
                "- 手办化2 :生成带包装盒、电脑桌背景的写实手办（风格更加固定）。\n"
                "- 手办化3 :生成带包装盒的写实手办，更注重面部还原。\n"
                "- 手办化4 :与 手办化1 类似，细节更加丰富，风格略有差异。\n"
                "- 手办化5 :基于游戏截图风格，微距摄影效果，带木质电脑桌背景。\n"
                "- 手办化6 :生成可爱的Q版/粘土人风格手办。\n"
                "- 手办化ntr :生成一张快餐店构图，手机上展示着上传的图片，背景中一对情侣坐在一起接吻。\n"
                "- 手办化cos :生成一张主题房间构图，房间中有Cosplayer、抱枕、PVC人物等。\n"
                "- 手办化jio :生成一张人物将脚伸出，夸大展示脚部的透视图。"
            )

        # 解析命令参数并选择 Prompt
        prompt_identifier = ""
        # 定义所有有效的手办化预设关键词
        valid_style_keywords = {"0", "1", "2", "3", "4", "5", "6", "ntr", "cos", "jio", "test"}

        # 从 CommandArg 中提取的词语中查找第一个匹配的预设关键词
        for word in words_in_args:
            if word in valid_style_keywords:
                prompt_identifier = word
                break

        # 如果 CommandArg 中没有找到任何有效的预设关键词，则默认使用 "0"
        if not prompt_identifier:
            prompt_identifier = "0" # 强制设置为 "0"
            logger.info("未指定手办化预设关键词，将默认使用自定义预设。")
            await matcher.send(
                "⚠️ 未指定手办化预设，将使用自定义预设。\n"
                "使用 '手办化 <关键词>' 来选择特定预设：\n"
                "- 手办化0 :自定义预设，不带参数触发。\n"
                "- 手办化1 :生成带包装盒、电脑桌背景的写实手办。\n"
                "- 手办化2 :生成带包装盒、电脑桌背景的写实手办（风格更加固定）。\n"
                "- 手办化3 :生成带包装盒的写实手办，更注重面部还原。\n"
                "- 手办化4 :与 手办化1 类似，细节更加丰富，风格略有差异。\n"
                "- 手办化5 :基于游戏截图风格，微距摄影效果，带木质电脑桌背景。\n"
                "- 手办化6 :生成可爱的Q版/粘土人风格手办。\n"
                "- 手办化ntr :生成一张快餐店构图，手机上展示着上传的图片，背景中一对情侣坐在一起接吻。\n"
                "- 手办化cos :生成一张主题房间构图，房间中有Cosplayer、抱枕、PVC人物等。\n"
                "- 手办化jio :生成一张人物将脚伸出，夸大展示脚部的透视图。"
            )

        target_attr_name = f"prompt_{prompt_identifier}"
        potential_prompt = getattr(plugin_config, target_attr_name, None)

        selected_prompt = "" # 初始化 selected_prompt

        if potential_prompt is not None and isinstance(potential_prompt, str) and potential_prompt != "":
            selected_prompt = potential_prompt
            logger.info(f"使用 prompt: {target_attr_name}")
        else:
            # 如果指定的 prompt 为空或未找到，则回退到 prompt_0
            selected_prompt = plugin_config.prompt_0
            logger.warning(f"配置中 '{target_attr_name}' 预设的提示词为空或未找到，将回退使用 prompt_0。")
            await matcher.send(f"⚠️ '{target_attr_name}' 预设的提示词为空或未找到，将回退使用默认预设。")

        # 最终检查，确保 selected_prompt 不为空
        if not selected_prompt:
            selected_prompt = "Generate a figurine based on the input image." # 极端情况下的通用回退
            logger.warning("所有提示词均为空，使用通用 fallback 提示词。")


        await matcher.send("⏳ 正在生成图片中，请稍候...")

        # 将选择的 prompt 传递给 API 调用函数
        image_result, _ = await call_openai_compatible_api(all_images, selected_prompt)

        message_to_send = Message()

        if image_result:
            try:
                if image_result.startswith("data:image/"):
                    # 分割前缀和实际的 base64 数据
                    _, base64_data = image_result.split(",", 1)
                    decoded_image_bytes = base64.b64decode(base64_data)

                    # 直接发送解码后的字节数据，适配NCQQ，
                    # 这比发送完整的 data:image/base64 字符串更稳定。
                    message_to_send += MessageSegment.image(file=decoded_image_bytes)
                    message_to_send += f"\n{SUCCESS_MESSAGE}"
                else:
                    # 意外格式的备用方案（例如，如果 API 返回的是直接的 URL）
                    logger.warning(f"意外的 image_result 格式: {image_result[:100]}... 尝试作为 URL 发送。")
                    message_to_send += MessageSegment.image(url=image_result)
                    message_to_send += f"\n{SUCCESS_MESSAGE}"

            except Exception as e:
                # 获图片数据处理（如 base64 解码）时的错误
                logger.error(f"处理图片数据时发生错误: {e}", exc_info=True)
                await matcher.finish(f"手办化处理完成，但图片数据处理失败 (内部处理错误): {e}")

            # 如果图片数据处理成功，则尝试发送消息并结束匹配器
            await matcher.finish(message_to_send)
        else:
            # 如果没有生成图片，则发送提示消息并结束匹配器
            await matcher.finish(NO_IMAGE_GENERATED_MESSAGE)

    except FinishedException:
        return
    except ValueError as e:
        await matcher.finish(f"❎ 配置错误: {e}")
    except ActionFailed as e:
        logger.error("手办化处理失败", exc_info=True)
        await matcher.finish("❎ 手办化处理失败，请稍后再试 (发送消息错误)。")
    except Exception as e:
        logger.error("手办化处理失败", exc_info=True)
        await matcher.finish(f"❎ 手办化处理失败，请稍后再试。错误：{e}")
