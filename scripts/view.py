#!/usr/bin/env python3
"""本地 HTML 看板生成器：把 xlsx 里的档案/计划/记录渲染成一个可点开看的静态页面。
数据每次录入后由各脚本自动调用 refresh_dashboard 重建；也可手动重跑：
  python3 view.py
看板路径 = 数据文件同目录的 减脂追踪看板.html，用户随时点开都是最新状态。
"""
import html
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(Path(__file__).absolute().parent))  # 调用目录优先（软链不解析，fitlib 靠它识别安装形态）
import fitlib as fl  # noqa: E402

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

_CSS = """
:root{--ink:#1f2430;--mut:#7a8299;--line:#e8eaf1;--bg:#f5f6fa;--card:#fff;--acc:#e8613c;--ok:#2e9e6b}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
main{max-width:760px;margin:0 auto;padding:16px}
header{background:linear-gradient(135deg,#e8613c,#f08a4b);color:#fff;padding:28px 16px 22px}
header .in{max-width:760px;margin:0 auto}
h1{font-size:22px;font-weight:700}
.sub{opacity:.85;font-size:13px;margin-top:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:-16px 0 14px}
.card{background:var(--card);border-radius:12px;padding:14px;box-shadow:0 1px 4px rgba(20,30,60,.06)}
.card .k{font-size:12px;color:var(--mut)}
.card .v{font-size:22px;font-weight:700;margin:2px 0}
.card .v small{font-size:13px;font-weight:400;color:var(--mut)}
.card .s{font-size:12px;color:var(--mut)}
.macros{display:flex;gap:14px}
.macros b{font-size:18px}
section{background:var(--card);border-radius:12px;padding:14px;margin-bottom:12px;box-shadow:0 1px 4px rgba(20,30,60,.06)}
section h2{font-size:14px;color:var(--mut);font-weight:600;margin-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:var(--mut);font-weight:500;text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}
td{padding:5px 6px;border-bottom:1px solid var(--line)}
td a{color:var(--acc);text-decoration:none;border-bottom:1px dotted var(--acc)}
tr:last-child td{border-bottom:none}
.tag{display:inline-block;background:#fdeee9;color:var(--acc);border-radius:6px;padding:0 8px;font-size:12px;margin-right:6px}
.empty{color:var(--mut);font-size:13px;padding:6px 0}
.path{font-size:12px;color:var(--mut);margin-top:10px;word-break:break-all}
.steps{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.step{font-size:12px;padding:2px 10px;border-radius:999px;background:#f0f2f8;color:var(--mut)}
.step.done{background:#e3f4ec;color:var(--ok);font-weight:600}
.step.cur{background:#fdeee9;color:var(--acc);font-weight:700}
"""

_SHELL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>居家减脂看板</title><style>{css}</style></head>
<body>
<header><div class="in"><h1>居家减脂看板 · {nickname}</h1>
<div class="sub">更新于 {ts} · 数据文件 {xlsx}</div></div></header>
<main>
{body}
</main></body></html>"""


def _esc(v):
    return html.escape(str(v)) if v not in (None, "") else "—"


def _table(headers, rows, raw_cols=()):
    """渲染表格。raw_cols 里的列的值视为已转义的 HTML（如动作名+教学链接），不再转义。"""
    if not rows:
        return '<p class="empty">暂无记录</p>'
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(
        f"<td>{r.get(h) if h in raw_cols else _esc(r.get(h))}</td>" for h in headers) + "</tr>"
        for r in rows)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def _ex_cell(name):
    """动作名单元格：映射表里有教学链接就带 🎬 链接，没有就纯名字（不编 URL）。"""
    url = fl.video_for(name)
    if not url:
        return _esc(name)
    return f'<a href="{html.escape(str(url), quote=True)}" target="_blank">🎬 {_esc(name)}</a>'


def _with_links(rows):
    """把「动作名称」列替换为带教学链接的 HTML 单元格。"""
    out = []
    for r in rows:
        r = dict(r)
        r["动作名称"] = _ex_cell(r.get("动作名称"))
        out.append(r)
    return out


def _steps(path_str, cur_weight):
    """减重路径渲染为步骤条：体重 ≤ 档位 = 已达成(done)；第一个未达成的档位 = 当前档(cur)。"""
    tiers = [t for t in str(path_str or "").replace("kg", "").split("→") if t.strip()]
    if not tiers:
        return '<p class="empty">未设置减重路径</p>'
    try:
        cur = float(cur_weight) if cur_weight is not None else None
    except (TypeError, ValueError):
        cur = None
    out, cur_marked = [], False
    for t in tiers:
        try:
            w = float(t)
        except ValueError:
            continue
        cls = "step"
        if cur is not None and cur <= w + 1e-9:
            cls += " done"
        elif cur is not None and not cur_marked:
            cls += " cur"
            cur_marked = True
        out.append(f'<span class="{cls}">{_esc(t)}kg</span>')
    return f'<div class="steps">{"".join(out)}</div>'


def _trend_svg(weight_rows):
    """体重趋势折线（最近 14 条，按日期升序）。纯内联 SVG，无外部依赖。"""
    rows = sorted([r for r in weight_rows if r.get("体重kg") is not None],
                  key=lambda r: str(r.get("日期") or ""))
    rows = rows[-14:]
    if len(rows) < 2:
        return '<p class="empty">体重记录攒到 2 次以上就会画出趋势线</p>'
    vals = [float(r["体重kg"]) for r in rows]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.15, 0.3)
    lo_p, hi_p = lo - pad, hi + pad
    W, H, X0, X1, Y0, Y1 = 700, 150, 34, 680, 16, 118
    pts = []
    for i, v in enumerate(vals):
        x = X0 + (X1 - X0) * i / (len(vals) - 1)
        y = Y1 - (Y1 - Y0) * (v - lo_p) / (hi_p - lo_p)
        pts.append((x, y, v))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#e8613c"/>'
                   for x, y, _ in pts)
    labels = (f'<text x="{X0}" y="{H - 6}" font-size="11" fill="#7a8299">{_esc(rows[0].get("日期"))}</text>'
              f'<text x="{X1}" y="{H - 6}" font-size="11" fill="#7a8299" text-anchor="end">{_esc(rows[-1].get("日期"))}</text>'
              f'<text x="6" y="{Y0 + 8}" font-size="11" fill="#7a8299">{hi:.1f}</text>'
              f'<text x="6" y="{Y1}" font-size="11" fill="#7a8299">{lo:.1f}</text>')
    last = pts[-1]
    last_lbl = (f'<text x="{min(last[0], X1 - 4):.1f}" y="{last[1] - 9:.1f}" font-size="12" '
                f'font-weight="700" fill="#e8613c" text-anchor="middle">{last[2]:.1f}kg</text>')
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto">'
            f'<polyline points="{poly}" fill="none" stroke="#e8613c" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dots}{labels}{last_lbl}</svg>')


def build_dashboard(config):
    """读取全部数据，渲染看板 HTML，返回看板文件路径。"""
    prof = fl.get_profile(config) or {}

    def p(k):
        return prof.get(k)

    _, train = fl.read_sheet(config, "训练记录", "H")
    _, weight = fl.read_sheet(config, "体重记录", "D")
    _, diet = fl.read_sheet(config, "饮食记录", "D")
    train = train if isinstance(train, list) else []
    weight = weight if isinstance(weight, list) else []
    diet = diet if isinstance(diet, list) else []

    today = datetime.now().date()
    t_key = today.strftime("%Y-%m-%d")
    days = fl.parse_training_days(p("训练日安排"))
    is_training = today.isoweekday() in days if days else None
    today_plan = [r for r in train
                  if str(r.get("日期") or "") == t_key
                  and str(r.get("状态") or "").strip() == "待完成"]
    today_done = [r for r in train
                  if str(r.get("日期") or "") == t_key
                  and str(r.get("状态") or "").strip() == "已完成"]
    day_label = {True: "训练日", False: "休息日", None: "未配置训练日"}[is_training]

    if today_plan or today_done:
        rows = today_plan + today_done
        state = f"{day_label}（待完成 {len(today_plan)} 项 / 已完成 {len(today_done)} 项）"
    elif is_training:
        rows, state = [], "训练日 · 暂无排期，练完把动作报给 AI"
    else:
        rows, state = [], f"{day_label} · 恢复也是训练的一部分"
    today_html = (f"<section><h2>今天 · 周{WEEKDAY_CN[today.weekday()]} · {state}</h2>"
                  + (_table(["训练主题", "动作名称", "组数", "次数", "重量kg", "状态"], _with_links(rows), raw_cols=("动作名称",))
                     or '<p class="empty">今天没有安排训练，好好休息</p>')
                  + "</section>")

    done_rows = [r for r in train if str(r.get("状态") or "").strip() == "已完成"][-10:]
    macros = (f'<div class="card"><div class="k">每日营养目标</div><div class="macros">'
              f'<span>碳水 <b>{_esc(p("碳水g"))}</b>g</span>'
              f'<span>蛋白 <b>{_esc(p("蛋白g"))}</b>g</span>'
              f'<span>脂肪 <b>{_esc(p("脂肪g"))}</b>g</span></div>'
              f'<div class="s">按当前档位 {_esc(p("当前档位kg"))}kg 计算，达标自动换档</div></div>')

    body = f"""
<div class="cards">
  <div class="card"><div class="k">当前体重</div><div class="v">{_esc(p("当前体重kg"))}<small> kg</small></div>
    <div class="s">初始 {_esc(p("初始体重kg"))}kg → 目标 {_esc(p("目标体重kg"))}kg</div></div>
  <div class="card"><div class="k">当前档位</div><div class="v">{_esc(p("当前档位kg"))}<small> kg</small></div>
    <div class="s">每 5kg 一档，达标自动进档</div></div>
  {macros}
</div>
<section><h2>减重路径</h2>{_steps(p("减重路径"), p("当前体重kg"))}</section>
{today_html}
<section><h2>体重趋势</h2>{_trend_svg(weight)}</section>
<section><h2>最近训练（已完成）</h2>{_table(["日期", "训练主题", "动作名称", "组数", "次数", "重量kg"], _with_links(done_rows), raw_cols=("动作名称",))}</section>
<section><h2>最近体重</h2>{_table(["日期", "体重kg", "体脂率%", "备注"], weight[-10:])}</section>
<section><h2>最近饮食</h2>{_table(["日期", "餐次", "食物内容", "备注"], diet[-10:])}</section>
<p class="path">这个页面每次录入数据后自动刷新；原始数据在同目录 减脂追踪数据.xlsx。</p>"""

    out_html = _SHELL.format(css=_CSS, nickname=_esc(p("用户昵称") or "还未建档"),
                             ts=datetime.now().strftime("%Y-%m-%d %H:%M"),
                             xlsx=fl._local_path(config).name, body=body)
    path = fl.dashboard_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".html.tmp")
    tmp.write_text(out_html, encoding="utf-8")
    tmp.replace(path)
    return path


def main():
    config = fl.load_config()
    path = build_dashboard(config)
    fl.out({"ok": True, "dashboard_path": str(path)})


if __name__ == "__main__":
    main()
