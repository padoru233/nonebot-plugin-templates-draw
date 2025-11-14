from typing import Optional
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    on_alconna,
    AlconnaMatch,
    Match
)
from nonebot import get_driver, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.plugin import PluginMetadata
from .config import Config
from .utils import (
    get_reply_id, add_template, remove_template, list_templates, get_prompt,
    get_images_from_event, generate_template_images, forward_images
)


usage = """模板列表
添加/删除模板 <标识> <提示词>
画图 <模板> [图片]/@xxx/自己"""

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
    print(f"[templates-draw] Loaded {len(keys)} Keys, max_attempts={plugin_config.max_total_attempts}")

# 添加模板
cmd_add = on_alconna(
    Alconna(
        "添加模板",
        Args["ident", str]["prompt", str, ...],  # ... 表示剩余所有文本
        aliases={"add_template"}
    ),
    priority=5,
    block=True,
)

@cmd_add.handle()
async def _(matcher: Matcher, ident: Match[str], prompt: Match[str]):
    if not ident.available or not prompt.available:
        await matcher.finish("格式：添加模板 <标识> <提示词>")

    add_template(ident.result, prompt.result)
    await matcher.finish(f'✅ 已添加/更新 模板 "{ident.result}"')

# 删除模板
cmd_del = on_alconna(
    Alconna(
        "删除模板",
        Args["ident", str],
        aliases={"del_template"}
    ),
    priority=5,
    block=True,
)

@cmd_del.handle()
async def _(matcher: Matcher, ident: Match[str]):
    if not ident.available:
        await matcher.finish("格式：删除模板 <标识>")

    ok = remove_template(ident.result)
    if ok:
        await matcher.finish(f'✅ 已删除 模板 "{ident.result}"')
    else:
        await matcher.finish(f'❌ 模板 "{ident.result}" 不存在')

# 列表模板
cmd_list = on_alconna(
    Alconna(
        "模板列表",
        aliases={"list_templates"}
    ),
    priority=5,
    block=True,
)

@cmd_list.handle()
async def _(matcher: Matcher):
    tpl = list_templates()
    if not tpl:
        await matcher.finish("当前没有任何模板")
    msg = "当前模板：\n"
    for k, v in tpl.items():
        msg += f"- {k} : {v[:30]}...\n"
    await matcher.finish(msg)

# 画图命令
cmd_draw = on_alconna(
    Alconna(
        "画图",
        Args["template", str],
        aliases={"draw"}
    ),
    priority=5,
    block=True,
)

@cmd_draw.handle()
async def _(matcher: Matcher,
            bot: Bot,
            event: GroupMessageEvent,
            template: Match[str],
            reply_id: Optional[int] = Depends(get_reply_id),
           ):

    images = await get_images_from_event(bot, event, reply_id)

    if not template.available:
        await matcher.finish(f"💡 请加上模板并回复或发送图片，或@用户/提及自己以获取头像\n    *命令列表*\n{usage}")

    if not images:
        await matcher.finish(f"💡 请回复或发送图片，或@用户/提及自己以获取头像\n    *命令列表*\n{usage}")

    identifier = template.result.lower()
    prompt = get_prompt(identifier)

    await matcher.send("⏳ 正在生成图片，请稍候…")

    try:
        results = await generate_template_images(images, prompt)
    except Exception as e:
        await matcher.finish(f"❎ 生成失败：{e}")

    await forward_images(bot, event, results)
