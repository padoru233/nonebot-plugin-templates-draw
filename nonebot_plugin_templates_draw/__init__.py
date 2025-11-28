from typing import Tuple, Optional, List

from nonebot import logger, get_driver, get_plugin_config, require
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    on_alconna,
    AlconnaMatch,
    Match,
    Option,
    At,
    Image,
    MultiVar,
    CommandMeta,
)
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.plugin import PluginMetadata
from .config import Config
from .utils import (
    get_reply_id, add_template, remove_template, list_templates, get_prompt,
    get_images_from_event, generate_template_images, forward_images,
    format_template_list, format_template_content, templates_to_image, find_template
)


usage = """========命令列表========
- 画图 <模板标识> [图片]/@xxx
- 添加/删除模板 <模板标识> <提示词>
- 查看模板 或者 查看模板 <模板标识>"""

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="模板绘图",
    description="一个模板绘图插件",
    usage=usage,
    type="application",
    homepage="https://github.com/padoru233/nonebot-plugin-templates-draw",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

plugin_config = get_plugin_config(Config).templates_draw

# 插件启动日志
@get_driver().on_startup
async def _on_startup():
    keys = plugin_config.gemini_api_keys
    logger.info(f"[templates-draw] Loaded {len(keys)} Keys, max_attempts={plugin_config.max_total_attempts}")

# 添加模板
cmd_add = on_alconna(
    Alconna(
        "添加模板",
        Args["ident", str]["prompt", MultiVar(str)],
        meta=CommandMeta(compact=True),
    ),
    aliases=["add_template"],
    priority=5,
    block=True,
)

@cmd_add.handle()
async def _(matcher: Matcher, ident: str, prompt: tuple[str, ...]):
    # MultiVar 会返回 tuple，合并成字符串
    prompt_text = " ".join(prompt)

    if not prompt_text.strip():
        await matcher.finish("格式：添加模板 <模板标识> <提示词>")

    add_template(ident, prompt_text)
    await matcher.finish(f'✅ 已添加/更新 模板 "{ident}"')

# 删除模板
cmd_del = on_alconna(
    Alconna(
        "删除模板",
        Args["ident", str],
    ),
    aliases=["del_template"],
    priority=5,
    block=True,
)

@cmd_del.handle()
async def _(matcher: Matcher, ident: Match[str]):
    if not ident.available:
        await matcher.finish("格式：删除模板 <模板标识>")

    ok = remove_template(ident.result)
    if ok:
        await matcher.finish(f'✅ 已删除 模板 "{ident.result}"')
    else:
        await matcher.finish(f'❌ 模板 "{ident.result}" 不存在')

# 查看模板列表
cmd_view = on_alconna(
    Alconna(
        "查看模板",
        Args["name", str, None],
    ),
    aliases={"view_template", "模板列表"},
    priority=5,
    block=True,
)

cmd_view.shortcut(
    r"查看模板\s+(?P<name>\S+)",
    command="查看模板",
    arguments=["{name}"],
    prefix=True,
)

# 添加别名的 shortcut
cmd_view.shortcut(
    r"模板列表\s+(?P<name>\S+)",
    command="查看模板",
    arguments=["{name}"],
    prefix=True,
)

@cmd_view.handle()
async def _(matcher: Matcher, name: Optional[str]):
    tpl = list_templates()
    if not tpl:
        await matcher.finish("当前没有任何模板")

    # 如果 name 为空，生成模板列表图片
    if name is None:
        formatted_text = format_template_list(tpl)

        # 先尝试生成图片
        img_bytes = None
        try:
            img_bytes = await templates_to_image(tpl)
        except Exception:
            pass

        # 图片生成失败发送文本
        if img_bytes:
            await matcher.finish(MessageSegment.image(img_bytes))
        else:
            await matcher.finish(formatted_text)

    else:
        # 查找具体模板
        try:
            target_name, target_content = find_template(tpl, name)
            formatted_text = format_template_content(target_name, target_content)
        except ValueError as e:
            # 异常情况，发送错误信息
            await matcher.finish(str(e))

        # 正常情况，发送模板内容
        await matcher.finish(formatted_text)

# 画图命令
cmd_draw = on_alconna(
    Alconna(
        "画图",
        Args["template", str, None]
            ["target", MultiVar(At), None]
            ["images", MultiVar(Image), None],
    ),
    aliases={"draw"},
    priority=5,
    block=True,
)

cmd_draw.shortcut(
    r"画图\s+(?P<template>\S+)",
    command="画图",
    arguments=["{template}"],
    prefix=True,
)

@cmd_draw.handle()
async def _(
    matcher: Matcher,
    bot: Bot,
    event: GroupMessageEvent,
    template: Optional[str],
    target: tuple[At, ...] = (),
    images: tuple[Image, ...] = (),
    reply_id: Optional[int] = Depends(get_reply_id),
):
    # 1. 模板校验
    if template is None:
        await matcher.finish(f"💡 请提供模板名称\n{usage}")

    raw = template.strip().lower()
    identifier = raw.split()[0] if raw else ""
    if not identifier:
        await matcher.finish(f"💡 模板名称不能为空\n{usage}")

    # 2. 从 target 抽出所有被 at 用户的 uid
    at_uids: List[str] = []
    if target:
        at_uids = [item.target for item in target]

    # 3. 从 images 参数获取图片 URL
    image_urls: List[str] = []
    if images:
        image_urls = [img.data["url"] for img in images]

    # 4. 获取图片（包含消息图片、回复图片、头像等）
    final_images = await get_images_from_event(
        bot,
        event,
        reply_id,
        at_uids=at_uids,
        raw_text=template,
        message_image_urls=image_urls,
    )

    if not final_images:
        await matcher.finish(f"💡 请提供图片或@用户获取头像\n{usage}")

    # 5. 获取提示词并生成
    prompt = get_prompt(identifier)
    if not prompt:
        await matcher.finish(f"❌ 未找到模板 '{identifier}'\n{usage}")

    await matcher.send("⏳ 正在生成图片，请稍候…")
    try:
        results = await generate_template_images(final_images, prompt)
    except Exception as e:
        await matcher.finish(f"❎ 生成失败：{e}")

    await forward_images(bot, event, results)
