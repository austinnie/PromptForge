"""
关注引导卡合成器 v4

改进（只动结构，文案保持用户设置）：
1. 去掉二维码下方重复标签（二维码图里已带）
2. 二维码加白色圆角卡片，与淡紫底统一
3. 顶部留白加大
4. emoji 用 Segoe UI Emoji 彩色渲染
5. 高度自适应，底部不留空白
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ==================== 配置区 ====================
QR_WECHAT = "公众号.png"
QR_VIDEO  = "视频号.png"
OUTPUT    = "公众号结束处.png"

NAME    = "爱行天下行者无疆"
TAGLINE = "懂健康和IT的智慧追求者"
MOTTO   = "康健植其根  精技拓其路  文心耀其灯"
TIPS = [
    "📌 关注我 → 少走弯路",
    "💡 点个在看 → 分享给朋友",
    "📱 长按识别下方二维码",
]

# 尺寸
W              = 800
QR_SIZE        = 240
GAP            = 80
CARD_PAD       = 14
CARD_RADIUS    = 12
PADDING_TOP    = 80
PADDING_BOTTOM = 70
LINE_PADDING   = 100

# 颜色
BG          = "#f4f1fa"
BG_CARD     = "#ffffff"
BORDER_CARD = "#e0dce8"
C_NAME      = "#1e1e3c"
C_TAG       = "#5c5c80"
C_MOTTO     = "#666688"
C_TIP       = "#2a2a4a"
C_LABEL     = "#8888a0"
C_LINE      = "#c8c8dd"

# 字体
FONT_NAME  = "C:/Windows/Fonts/simsun.ttc"
FONT_BOLD  = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG   = "C:/Windows/Fonts/msyh.ttc"
FONT_EMOJI = "C:/Windows/Fonts/seguiemj.ttf"
# ================================================


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        print(f"⚠️ 字体加载失败 {path}，回退默认")
        return ImageFont.load_default()


def is_emoji(ch):
    cp = ord(ch)
    return (
        0x1F300 <= cp <= 0x1FAFF or
        0x1F000 <= cp <= 0x1F2FF or
        0x2600  <= cp <= 0x26FF  or
        0x2700  <= cp <= 0x27BF
    )


def measure_text(draw, text, cjk_font, emoji_font):
    items = []
    total_w = 0
    max_h = 0
    for ch in text:
        use_emoji = is_emoji(ch) and emoji_font is not None
        font = emoji_font if use_emoji else cjk_font
        try:
            bbox = draw.textbbox((0, 0), ch, font=font)
        except Exception:
            bbox = (0, 0, 0, 0)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w == 0 and use_emoji:
            font = cjk_font
            use_emoji = False
            bbox = draw.textbbox((0, 0), ch, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        if w == 0:
            w = 6
        items.append((ch, font, use_emoji, w))
        total_w += w
        max_h = max(max_h, h)
    return items, total_w, max_h


def draw_mixed_line(draw, canvas, text, y, cjk_font, emoji_font, fill):
    items, total_w, line_h = measure_text(draw, text, cjk_font, emoji_font)
    x = (canvas.width - total_w) // 2
    for ch, font, use_emoji, w in items:
        if use_emoji:
            try:
                draw.text((x, y), ch, font=font, embedded_color=True)
            except TypeError:
                draw.text((x, y), ch, font=font, fill=fill)
        else:
            draw.text((x, y), ch, font=font, fill=fill)
        x += w
    return line_h


def main():
    # ---- 载入二维码 ----
    qr_w = Image.open(QR_WECHAT).convert("RGB").resize(
        (QR_SIZE, QR_SIZE), Image.LANCZOS)
    qr_v = Image.open(QR_VIDEO).convert("RGB").resize(
        (QR_SIZE, QR_SIZE), Image.LANCZOS)

    # ---- 加载字体 ----
    f_name  = load_font(FONT_NAME, 52)
    f_ovo   = load_font(FONT_BOLD, 14)
    f_tag   = load_font(FONT_REG, 22)
    f_motto = load_font(FONT_NAME, 22)
    f_tip   = load_font(FONT_REG, 22)
    f_emoji = load_font(FONT_EMOJI, 24)

    # ---- 量高度 ----
    tmp = Image.new("RGB", (1, 1))
    td = ImageDraw.Draw(tmp)

    _, _, h_name  = measure_text(td, NAME, f_name, f_emoji)
    _, _, h_tag   = measure_text(td, TAGLINE, f_tag, f_emoji)
    _, _, h_motto = measure_text(td, MOTTO, f_motto, f_emoji)
    h_ovo = 18
    tip_hs = [measure_text(td, t, f_tip, f_emoji)[2] for t in TIPS]

    card_h = QR_SIZE + CARD_PAD * 2

    H = PADDING_TOP
    H += 30
    H += h_name + 10
    H += h_ovo + 18
    H += h_tag + 28
    H += 1 + 28
    H += h_motto + 32
    for th in tip_hs:
        H += th + 14
    H += 40
    H += card_h
    H += PADDING_BOTTOM

    # ---- 正式画布 ----
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    y = PADDING_TOP

    # 顶部装饰线
    draw.line([(LINE_PADDING, y - 30), (W - LINE_PADDING, y - 30)],
              fill=C_LINE, width=1)

    # 名字
    draw_mixed_line(draw, canvas, NAME, y, f_name, f_emoji, C_NAME)
    y += h_name + 10

    # OVO 装饰
    ovo_text = "— OVO —"
    bbox = td.textbbox((0, 0), ovo_text, font=f_ovo)
    ow = bbox[2] - bbox[0]
    draw.text(((W - ow) // 2, y), ovo_text, font=f_ovo, fill=C_LABEL)
    y += h_ovo + 18

    # 副标题
    draw_mixed_line(draw, canvas, TAGLINE, y, f_tag, f_emoji, C_TAG)
    y += h_tag + 28

    # 分隔线
    draw.line([(LINE_PADDING, y), (W - LINE_PADDING, y)],
              fill=C_LINE, width=1)
    y += 1 + 28

    # 箴言
    draw_mixed_line(draw, canvas, MOTTO, y, f_motto, f_emoji, C_MOTTO)
    y += h_motto + 32

    # 引导文案
    for i, tip in enumerate(TIPS):
        draw_mixed_line(draw, canvas, tip, y, f_tip, f_emoji, C_TIP)
        y += tip_hs[i] + 14

    # ---- 两个二维码 + 白色圆角卡片 ----
    y += 40
    total_qr_w = QR_SIZE * 2 + GAP
    x_start = (W - total_qr_w) // 2

    # 左卡片（公众号）
    draw.rounded_rectangle(
        [x_start - CARD_PAD, y - CARD_PAD,
         x_start + QR_SIZE + CARD_PAD, y + QR_SIZE + CARD_PAD],
        radius=CARD_RADIUS, fill=BG_CARD, outline=BORDER_CARD, width=1,
    )
    canvas.paste(qr_w, (x_start, y))

    # 右卡片（视频号）
    x2_start = x_start + QR_SIZE + GAP
    draw.rounded_rectangle(
        [x2_start - CARD_PAD, y - CARD_PAD,
         x2_start + QR_SIZE + CARD_PAD, y + QR_SIZE + CARD_PAD],
        radius=CARD_RADIUS, fill=BG_CARD, outline=BORDER_CARD, width=1,
    )
    canvas.paste(qr_v, (x2_start, y))

    # ---- 保存 ----
    canvas.save(OUTPUT, quality=95)
    print(f"✅ 生成: {Path(OUTPUT).resolve()}")
    print(f"   尺寸: {canvas.size}")


if __name__ == "__main__":
    main()