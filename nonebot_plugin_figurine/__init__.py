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
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&s=0&nk={user_id}"

        # 尝试获取用户信息，主要是为了确认用户存在，并记录日志
        # (这部分可以省略，因为主要目的是获取头像，而不是用户信息本身)
        """
        if group_id:
            try:
                await bot.get_group_member_info(group_id=group_id, user_id=user_id, no_cache=True)
                logger.debug(f"Fetched group member info for {user_id} in {group_id}, using constructed avatar URL: {avatar_url}")
            except ActionFailed as e:
                logger.debug(f"Could not get group member info for {user_id} in {group_id}: {e.message}")
                # Fallback to stranger info or just use constructed URL
        else:
            try:
                await bot.get_stranger_info(user_id=user_id, no_cache=True)
                logger.debug(f"Fetched stranger info for {user_id}, using constructed avatar URL: {avatar_url}")
            except ActionFailed as e:
                logger.debug(f"Could not get stranger info for {user_id}: {e.message}")
        """

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

    if not prompt:
        prompt = plugin_config.default_prompt

    url = f"{plugin_config.gemini_api_url}/v1/chat/completions"

    # 构造请求 payload
    content = [{"type": "text", "text": prompt}]
    for img in images:
        buf = BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        })

    payload = {
        "model": plugin_config.gemini_model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 32768,
    }

    max_total_attempts = plugin_config.max_total_attempts
    total_attempts = 0
    last_error = "尚未尝试"

    while total_attempts < max_total_attempts:
        current_key_idx = _current_api_key_idx % num_keys
        key = keys[current_key_idx]
        total_attempts += 1
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
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

        # 继续走原有的 choices 解析
        text_out = None
        img_out = None
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {}) or {}
            cont = msg.get("content")
            if isinstance(cont, str):
                text_out = cont.strip()
            elif isinstance(cont, list):
                parts = []
                for part in cont:
                    if part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        img_out = part.get("image_url", {}).get("url")
                        if img_out:
                            break
                if parts:
                    text_out = "\n".join(parts).strip()
            # 兼容老接口可能把图片放在 message["images"]
            if not img_out and isinstance(msg.get("images"), list):
                for it in msg["images"]:
                    if isinstance(it, dict) and "image_url" in it:
                        img_out = it["image_url"].get("url")
                        if img_out:
                            break

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
async def handle_figurine_cmd(bot: Bot, matcher: Matcher, event: GroupMessageEvent, rp = Depends(msg_reply)):

    SUCCESS_MESSAGE = "手办化完成！"
    NO_IMAGE_GENERATED_MESSAGE = "手办化处理完成，但未能生成图片，请稍后再试或尝试其他图片。"

    try:
        all_images: List[Image.Image] = []
        group_id = event.group_id if isinstance(event, GroupMessageEvent) else None

        # 1 获取回复消息中的图片
        if rp:
            all_images.extend(await get_images_from_reply(bot, rp))

        # 这里只收集图片，不立即获取头像，临时存储@的用户ID和"自己"的提及，以便在没有其他图片时使用
        at_user_ids_from_message: List[int] = []
        mention_self_in_message: bool = False

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
                    if word == "自己":
                        mention_self_in_message = True
                    elif word.startswith("@") and word[1:].isdigit():
                        at_user_ids_from_message.append(int(word[1:]))

        # 2 如果第一阶段没有收集到任何图片，则尝试获取头像 ---
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

        if not all_images:
            await matcher.finish('请回复包含图片的消息，或发送图片，或@用户/提及自己以获取头像。')

        await matcher.send("正在手办化处理中...")
        await asyncio.sleep(randint(1, 3))

        # 目前是直接使用 plugin_config.default_prompt
        image_result, _ = await call_openai_compatible_api(all_images, plugin_config.default_prompt)

        message_to_send = Message()
        if image_result:
            message_to_send += MessageSegment.image(file=image_result)
            message_to_send += f"\n{SUCCESS_MESSAGE}"
            await matcher.finish(message_to_send)
        else:
            await matcher.finish(NO_IMAGE_GENERATED_MESSAGE)

    except MatcherException:
        return
    except ValueError as e:
        await matcher.finish(f"配置错误: {e}")
    except ActionFailed as e:
        logger.error("手办化处理失败", exc_info=True)
        await matcher.finish("手办化处理失败，请稍后再试 (发送消息错误)")
    except Exception as e:
        logger.error("手办化处理失败", exc_info=True)
        await matcher.finish(f"手办化处理失败，请稍后再试。错误：{e}")
