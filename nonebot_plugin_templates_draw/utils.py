import os, re, httpx, asyncio, base64, json, html, uuid
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict, Union
from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.utils import ImageReader

from nonebot import logger, require, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment, GroupMessageEvent
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_config_file, get_plugin_cache_dir

from .config import Config


# 用户自定义的模板文件
USER_PROMPT_FILE: Path = Path(get_plugin_config_file("prompt.json"))
# 存放默认模板的文件，每次启动都重写
DEFAULT_PROMPT_FILE: Path = Path(get_plugin_config_file("default_prompt.json"))
# 生成 PDF 的缓存路径
PDF_CACHE_DIR: Path = Path(get_plugin_cache_dir())

plugin_config = get_plugin_config(Config).templates_draw

# 加载字体路径
CURRENT_DIR = Path(__file__).parent
IMG_FONT_PATH = CURRENT_DIR / "resources" / "FZMINGSTJW.TTF"
PDF_FONT_PATH = CURRENT_DIR / "resources" / "fangsong_GB2312.ttf"


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
    msg += """
💡 使用 '查看模板 <模板标志>' 查看具体内容
========命令列表========
- 画图 <模板标识> [图片]/@xxx
- 添加/删除模板 <模板标识> <提示词>
- 查看模板 或者 查看模板 <模板标识>"""

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
        if IMG_FONT_PATH.exists():
            logger.debug(f"找到字体文件: {IMG_FONT_PATH}")
            font_header = ImageFont.truetype(str(IMG_FONT_PATH), 24)
            font_item = ImageFont.truetype(str(IMG_FONT_PATH), 18)
            font_tip = ImageFont.truetype(str(IMG_FONT_PATH), 16)
        else:
            raise FileNotFoundError(f"字体文件不存在: {IMG_FONT_PATH}")
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
    tip = """使用 '查看模板 <模板标志>' 查看具体内容
命令列表:
- 画图 <模板标识> [图片]/@xxx
- 添加/删除模板 <模板标识> <提示词>
- 查看模板 或者 查看模板 <模板标识>"""
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

def build_pdf_from_prompt_and_images(prompt: str, images: List[Image.Image]) -> bytes:
    """
    将提示词和多个 PIL Image 对象合并为一个 PDF 文件。
    """
    if not prompt and not images:
        raise ValueError("提示词和图片不能都为空")

    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4

    # --- 字体配置 ---
    font_name = 'Helvetica'  # 默认字体，防止加载失败时变量未定义
    try:
        # 检测 PDF_FONT_PATH 是否存在
        if hasattr(globals().get('PDF_FONT_PATH'), 'exists') and PDF_FONT_PATH.exists():
            # 注册中文字体
            font_key = 'CustomChinese'
            # 避免重复注册报错
            if font_key not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_key, str(PDF_FONT_PATH)))
            font_name = font_key
            logger.debug(f"PDF构建: 成功加载字体 {PDF_FONT_PATH}")
        else:
            logger.debug("PDF构建: 字体路径无效或未定义，使用默认字体 (中文可能乱码)")
    except Exception as e:
        logger.error(f"PDF构建: 加载字体失败: {e}，使用默认字体")

    # --- 第一页：Prompt ---
    if prompt:
        # 1. 标题
        c.setFont(font_name, 16)
        c.drawString(40, page_height - 50, "Prompt:")

        # 2. 内容样式
        style = ParagraphStyle(
            'CustomStyle',
            fontName=font_name,
            fontSize=12,
            leading=18, # 行间距稍微加大，更易阅读
            alignment=TA_LEFT,
            wordWrap='CJK' # 支持中文换行
        )

        # 3. 修复转义逻辑：先转义特殊字符，再转换换行符
        # 使用 html.escape 自动处理 & < > 等符号，避免手动 replace 出错
        safe_prompt = html.escape(prompt).replace('\n', '<br/>')

        para = Paragraph(safe_prompt, style)

        # 4. 创建 Frame (扩大显示区域)
        margin = 40
        frame = Frame(
            margin, margin,                  # x, y (从底部开始)
            page_width - 2 * margin,         # 宽
            page_height - 100,               # 高 (顶部留出标题空间)
            showBoundary=0
        )

        # 5. 绘制
        # 注意：如果内容超过一页，Frame 不会自动分页。
        # 这里假设 Prompt 不会超级长，如果很长需要用 SimpleDocTemplate
        frame.addFromList([para], c)
        c.showPage()

    # --- 后续页面：Images ---
    # 配置参数
    margin = 20           # 左右边距 (像素)
    bottom_text_area = 50 # 底部留给文字的高度
    top_margin = 20       # 顶部边距

    for idx, img in enumerate(images):
        # 1. 计算图片最大可用区域
        available_width = page_width - (margin * 2)
        available_height = page_height - top_margin - bottom_text_area

        img_width, img_height = img.size

        # 2. 计算缩放比例 (保持纵横比，contain 模式)
        scale_w = available_width / img_width
        scale_h = available_height / img_height
        scale = min(scale_w, scale_h) # 取最小值，确保完整放入

        new_width = img_width * scale
        new_height = img_height * scale

        # 3. 计算居中位置
        # x: 页面中心 - 图片一半宽
        x = (page_width - new_width) / 2

        # y: 底部文字区域上方 + (可用垂直空间中心 - 图片一半高)
        # 这样确保了图片永远位于 bottom_text_area 之上
        y = bottom_text_area + (available_height - new_height) / 2

        # 4. 绘制图片
        img_reader = ImageReader(img)
        c.drawImage(img_reader, x, y, width=new_width, height=new_height)

        # 5. 绘制底部文字
        c.setFont(font_name, 10)
        page_number_text = f"Reference Image {idx + 1} / {len(images)}"

        # 使用 drawCentredString 简化居中计算
        # 文字位置固定在底部区域的中间 (例如高度30的位置)
        text_y_position = 30
        c.drawCentredString(page_width / 2, text_y_position, page_number_text)

        c.showPage()

    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    # 保存到文件
    try:
        if not PDF_CACHE_DIR.exists():
            PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = PDF_CACHE_DIR / filename

        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        logger.info(f"PDF构建成功并保存: {file_path} ({len(pdf_bytes)} bytes)")

    except Exception as e:
        logger.error(f"PDF保存失败: {e}")
        raise e

    return pdf_bytes
