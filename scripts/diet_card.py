#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""饮食搭配 3:4 卡片图渲染（确定性，同输入必同图）。

设计原则（见 references/diet_card_spec.md）：
- 本脚本只做呈现层，不做任何营养计算；克数由调用方（Agent 按目标宏量 ±10g 算准）写入 JSON
- 纯 Pillow 绘制，不用文生图：数字绝不会被模型改写
- 无时间戳、无随机数：同一 JSON 两次运行输出逐字节一致
- 画布固定 1080x1440（3:4），单方案/多方案同一尺寸，禁止 9:16 海报

用法：
    python3 -B scripts/diet_card.py --input card.json [--out 减脂数据/diet-card.png] [--font /path/to.ttf]
输入 JSON 格式见 references/diet_card_spec.md 第 3 节。
输出：stdout JSON（与其他脚本风格一致），ok:false 时 error 为人话。
"""
import argparse
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ---------- 规格（与 references/diet_card_spec.md 一致） ----------
W, H = 1080, 1440          # 3:4
MARGIN = 64                # 画布四周留白
RADIUS = 36                # 卡片圆角
PAD = 72                   # 卡片内边距

BG = (232, 240, 235)       # #E8F0EB 浅薄荷灰绿
CARD = (255, 255, 255)     # 白卡
INK = (31, 61, 43)         # #1F3D2B 深绿主文字
SUB = (90, 114, 99)        # #5A7263 次级文字
ACCENT = (46, 125, 79)     # #2E7D4F 强调/方案标签
LINE = (213, 224, 216)     # #D5E0D8 细分割线

# 中文字体查找链（按优先级；--font 可强制指定）
FONT_CANDIDATES = [
    # Linux (Noto Sans CJK)
    ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Medium.ttc", 0),
    ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    # 文泉驿
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    # macOS
    ("/System/Library/Fonts/PingFang.ttc", 0),
    # Windows
    ("C:/Windows/Fonts/msyh.ttc", 0),
    ("C:/Windows/Fonts/simhei.ttf", 0),
]


def resolve_font(explicit=None):
    """返回可用字体路径，找不到则报人话错误。"""
    if explicit:
        if os.path.exists(explicit):
            return explicit
        raise RuntimeError("--font 指定的字体文件不存在：%s" % explicit)
    for path, _idx in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RuntimeError(
        "没找到中文字体。请安装 Noto Sans CJK（Linux: apt install fonts-noto-cjk）"
        "或用 --font 指定一个支持中文的 ttf/otf 文件"
    )


_font_cache = {}


def F(size, weight="regular"):
    """带缓存的字体加载。weight: regular / bold"""
    key = (font_path, size, weight)
    if key not in _font_cache:
        idx = font_index
        _font_cache[key] = ImageFont.truetype(font_path, size, index=idx)
        if weight == "bold":
            # 找不到真正的 Bold 文件时用同文件（视觉上靠字号区分），保证确定性
            bold_path = font_path.replace("Regular", "Bold").replace("Light", "Medium").replace("DemiLight", "Medium")
            if bold_path != font_path and os.path.exists(bold_path):
                _font_cache[key] = ImageFont.truetype(bold_path, size, index=font_index_bold(bold_path))
    return _font_cache[key]


def font_index_bold(path):
    return 0


def text_w(draw, s, font):
    return draw.textlength(s, font=font)


def fit_font(draw, s, base_size, max_w, weight="regular"):
    """文本超宽时自动缩字号，防溢出。"""
    size = base_size
    while size > 16:
        f = F(size, weight)
        if text_w(draw, s, f) <= max_w:
            return f
        size -= 2
    return F(size, weight)


def rounded_card(draw, box, fill=CARD):
    draw.rounded_rectangle(box, radius=RADIUS, fill=fill)


def footer_y():
    return H - MARGIN - 72


def draw_footer(draw, text):
    f = F(30)
    draw.text((MARGIN + PAD, footer_y()), text, font=f, fill=SUB)


def render_single(draw, data):
    """单方案卡：大标题 + 分割线 + 名称左/克数右 + 页脚。"""
    card = (MARGIN, MARGIN, W - MARGIN, H - MARGIN)
    rounded_card(draw, card)
    cx = MARGIN + PAD
    max_w = W - 2 * MARGIN - 2 * PAD

    y = MARGIN + 96
    title = data.get("title", "今日饮食")
    draw.text((cx, y), title, font=F(72, "bold"), fill=INK)
    y += 108

    subtitle = data.get("subtitle", "")
    if subtitle:
        draw.text((cx, y), subtitle, font=fit_font(draw, subtitle, 38, max_w), fill=SUB)
        y += 78

    # 细分割线
    y += 18
    draw.line((cx, y, W - MARGIN - PAD, y), fill=LINE, width=2)
    y += 56

    items = data.get("items") or []
    if not items:
        raise RuntimeError("单方案卡缺少 items（食材列表），JSON 里每项要有 name 和 grams")
    row_gap = 34
    for it in items:
        name, grams = str(it["name"]), str(it["grams"])
        f = fit_font(draw, name, 44, max_w - 220)
        draw.text((cx, y), name, font=f, fill=INK)
        gw = text_w(draw, grams, f)
        draw.text((W - MARGIN - PAD - gw, y), grams, font=f, fill=INK)
        y += 62 + row_gap

    draw_footer(draw, data.get("footer", "估算值 · 选这套即可"))


def render_multi(draw, data):
    """多方案卡：同一 3:4 画布内纵向 A/B/C 白卡，等高、留白充足。"""
    cx = MARGIN + PAD
    max_w = W - 2 * MARGIN - 2 * PAD

    y = MARGIN + 72
    title = data.get("title", "今日饮食 · 三选一")
    draw.text((cx, y), title, font=fit_font(draw, title, 58, max_w, "bold"), fill=INK)
    y += 86
    subtitle = data.get("subtitle", "")
    if subtitle:
        draw.text((cx, y), subtitle, font=fit_font(draw, subtitle, 34, max_w), fill=SUB)
        y += 64

    plans = data.get("plans") or []
    if not plans:
        raise RuntimeError("多方案卡缺少 plans（A/B/C 方案列表）")
    if len(plans) > 4:
        raise RuntimeError("方案超过 4 套会挤爆 3:4 画布，请拆成多张或让用户先筛")

    # 子卡区域：标题下到页脚上
    top = y + 24
    bottom = footer_y() - 40
    gap = 26
    card_h = (bottom - top - gap * (len(plans) - 1)) / len(plans)

    for p in plans:
        ct = top
        cb = top + card_h
        rounded_card(draw, (MARGIN, ct, W - MARGIN, cb))
        py = ct + 34

        label = str(p.get("label", "")).strip()
        name = str(p.get("name", "")).strip()
        head = ("%s · %s" % (label, name)) if label else name
        draw.text((cx, py), head, font=fit_font(draw, head, 40, max_w, "bold"), fill=ACCENT)
        py += 58

        meals = p.get("meals") or []
        if meals:
            for m in meals:
                line_txt = "%s   %s" % (str(m.get("meal", "")), str(m.get("grams", "")))
                f = fit_font(draw, line_txt, 33, max_w)
                draw.text((cx + 8, py), line_txt, font=f, fill=INK)
                py += 46
        else:
            line_txt = str(p.get("line", ""))
            if line_txt:
                draw.text((cx + 8, py), line_txt, font=fit_font(draw, line_txt, 31, max_w), fill=INK)
                py += 54

        macros = str(p.get("macros", ""))
        if macros:
            draw.text((cx + 8, py), macros, font=fit_font(draw, macros, 34, max_w), fill=SUB)

        top = cb + gap

    draw_footer(draw, data.get("footer", "估算 · 回 A/B/C 即可"))


def main():
    global font_path, font_index
    ap = argparse.ArgumentParser(description="饮食搭配 3:4 卡片图渲染")
    ap.add_argument("--input", required=True, help="输入 JSON 文件路径")
    ap.add_argument("--out", default=None, help="输出 png 路径（默认 减脂数据/diet-card[-multi].png）")
    ap.add_argument("--font", default=None, help="强制指定中文字体路径")
    args = ap.parse_args()

    result = {"ok": False}
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        mode = data.get("mode", "single")
        if mode not in ("single", "multi"):
            raise RuntimeError("mode 只支持 single / multi，收到：%s" % mode)

        font_path = resolve_font(args.font)
        font_index = 0

        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        if mode == "single":
            render_single(draw, data)
            default_name = "diet-card.png"
        else:
            render_multi(draw, data)
            default_name = "diet-card-multi.png"

        out = args.out or os.path.join("减脂数据", default_name)
        parent = os.path.dirname(os.path.abspath(out))
        if parent:
            os.makedirs(parent, exist_ok=True)
        img.save(out, format="PNG")

        with open(out, "rb") as f:
            digest = hashlib.md5(f.read()).hexdigest()
        result = {"ok": True, "path": os.path.abspath(out), "mode": mode,
                  "size": [W, H], "md5": digest}
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
