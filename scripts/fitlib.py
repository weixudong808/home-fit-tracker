#!/usr/bin/env python3
"""home-fit-tracker 公共库：配置、本地 xlsx 存储、档案、阶梯减重、渐进超负荷、看板刷新。
被 record.py / profile.py / plan.py / storage.py / view.py / brief.py 复用，不单独执行业务。

存储：本地 xlsx 工作簿（openpyxl），零安装零授权，首次运行自动建表。
数据目录按安装形态自动定位（见 _local_data_dirs），用户可在 config.json 用 local_path 显式指定。
"""
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

# 全新环境的空配置：local_path 留空 → 自动定位数据目录
DEFAULT_CONFIG = {
    "local_path": "",
    "cron_job_ids": {},
}

# ---------------------------------------------------------------- 常量
# 用户档案表列顺序（单行配置：第1行表头，第2行数据）
PROFILE_COLS = [
    "创建日期", "性别", "年龄", "身高cm",
    "初始体重kg", "当前体重kg", "目标体重kg", "体脂率%",
    "活动量", "每周训练天数", "训练日安排", "训练偏好",
    "当前档位kg", "减重路径",
    "碳水g", "蛋白g", "脂肪g",
    "AI称呼", "回复风格", "记忆备注", "用户昵称",
]
# 训练记录单表承载实际记录与滚动计划：状态=已完成（实际）/待完成（自动生成的下次计划）/已跳过（被新记录替代）
TRAIN_COLS = ["日期", "训练主题", "动作名称", "组数", "次数", "重量kg", "备注", "状态"]
WEIGHT_COLS = ["日期", "体重kg", "体脂率%", "备注"]
DIET_COLS = ["日期", "餐次", "食物内容", "备注"]
PLAN_STATUSES = ["待完成", "已完成", "已跳过"]
REP_LADDER = [10, 12, 15]  # 渐进超负荷次数阶梯
WEIGHT_STEP_KG = 5         # 阶梯式减重：每 5kg 一档
# 首周默认计划（居家版，自重+哑铃，1-6 练全覆盖；首周=校准周：4×15、重量留 0 由用户实测校准）。
# 自重动作重量 0=自重；哑铃动作校准周同样留 0，用户报实际重量后渐进超负荷接管。
# 主题沿用单部位词（腿/胸/背/肩/手臂/核心/全身/上肢/下肢），与 infer_theme 的整堂课模板匹配联动兼容。
DEFAULT_PLAN_TEMPLATES = {
    1: {"全身": ["深蹲", "俯卧撑", "臀桥", "平板支撑"]},
    2: {"上肢": ["俯卧撑", "哑铃划船", "哑铃肩推", "哑铃弯举"],
        "下肢": ["深蹲", "箭步蹲", "臀桥", "提踵"]},
    3: {"腿": ["深蹲", "箭步蹲", "臀桥", "提踵"],
        "胸": ["俯卧撑", "哑铃肩推", "哑铃飞鸟"],
        "背": ["哑铃划船", "超人式", "哑铃弯举"]},
    4: {"腿": ["深蹲", "箭步蹲", "臀桥"],
        "胸": ["俯卧撑", "哑铃飞鸟", "上斜俯卧撑"],
        "背": ["哑铃划船", "超人式", "哑铃弯举"],
        "肩": ["哑铃肩推", "侧平举", "俯身飞鸟"]},
    5: {"腿": ["深蹲", "箭步蹲", "臀桥"],
        "胸": ["俯卧撑", "哑铃飞鸟", "上斜俯卧撑"],
        "背": ["哑铃划船", "超人式", "直臂下拉"],
        "肩": ["哑铃肩推", "侧平举", "俯身飞鸟"],
        "手臂": ["哑铃弯举", "哑铃臂屈伸", "椅上臂屈伸"]},
    6: {"腿": ["深蹲", "箭步蹲", "臀桥"],
        "胸": ["俯卧撑", "哑铃飞鸟", "上斜俯卧撑"],
        "背": ["哑铃划船", "超人式", "直臂下拉"],
        "肩": ["哑铃肩推", "侧平举", "俯身飞鸟"],
        "手臂": ["哑铃弯举", "哑铃臂屈伸", "椅上臂屈伸"],
        "核心": ["平板支撑", "卷腹", "俄罗斯转体", "登山跑"]},
}
DEFAULT_PLAN_NOTE = "首周默认计划·校准周"
# 教学视频映射（动作名 → B站教程链接）。每条均为人工核实过的有效链接（HTTP 可访问 + 页面标题与动作匹配，核实日期 2026-09-06）。
# 红线：新增/替换链接必须先逐条人工核实；匹配不到的动作一律不带链接，绝不现编 URL。
EXERCISE_VIDEOS = {
    "深蹲": "https://www.bilibili.com/video/BV1ZdzLBqEjz/",
    "俯卧撑": "https://www.bilibili.com/video/BV1oX5X6mEKL/",
    "臀桥": "https://www.bilibili.com/video/BV1Yf4y197op/",
    "平板支撑": "https://www.bilibili.com/video/BV1Q34y1j79r/",
    "箭步蹲": "https://www.bilibili.com/video/BV1gRbDzSER1/",
    "提踵": "https://www.bilibili.com/video/BV1Vs421M7gV/",
    "哑铃划船": "https://www.bilibili.com/video/BV1RM4m1S77p/",
    "哑铃肩推": "https://www.bilibili.com/video/BV1LR7uzEEDL/",
    "哑铃飞鸟": "https://www.bilibili.com/video/BV1jY4y1G7h7/",
    "哑铃弯举": "https://www.bilibili.com/video/BV1anmCYNEbK/",
    "侧平举": "https://www.bilibili.com/video/BV1YR4y1v7ZY/",
    "俯身飞鸟": "https://www.bilibili.com/video/BV1gcmXBJEgV/",
    "超人式": "https://www.bilibili.com/video/BV1yt411Z75Y/",
    "直臂下拉": "https://www.bilibili.com/video/BV1RT41157oz/",
    "上斜俯卧撑": "https://www.bilibili.com/video/BV1cH4y1V7sy/",
    "哑铃臂屈伸": "https://www.bilibili.com/video/BV1c541187Wg/",
    "椅上臂屈伸": "https://www.bilibili.com/video/BV1Ft4y197JS/",
    "卷腹": "https://www.bilibili.com/video/BV1x1376RE8D/",
    "俄罗斯转体": "https://www.bilibili.com/video/BV1R2421M7oi/",
    "登山跑": "https://www.bilibili.com/video/BV1Vb411Y7Mc/",
}


def video_for(name):
    """动作教学链接；映射表没有的返回 None（调用方不带你别编）。"""
    return EXERCISE_VIDEOS.get(str(name or "").strip())
# 本地工作簿四张工作表的表头
SHEET_HEADERS = {
    "训练记录": TRAIN_COLS,
    "体重记录": WEIGHT_COLS,
    "饮食记录": DIET_COLS,
    "用户档案": PROFILE_COLS,
}
DASHBOARD_NAME = "减脂追踪看板.html"

# ---------------------------------------------------------------- 配置 / 数据目录
def save_config(config):
    """原子写回 config.json。"""
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def load_config():
    """读配置并确保本地存储可用（未配置时自动定位并建表，结果写回 config.json）。"""
    if not CONFIG_PATH.exists():
        # 全新环境：自动落空模板再走自动定位，首次运行零配置初始化
        config = json.loads(json.dumps(DEFAULT_CONFIG))
        save_config(config)
    else:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    return ensure_backend(config)


def ensure_backend(config):
    """本地后端：xlsx 不存在就自动建表（已显式指定的 local_path 优先）。"""
    if not _openpyxl_available():
        die("本地表格需要 openpyxl：请先执行 pip install openpyxl")
    path = _local_path(config)
    if not path.exists():
        _build_local_workbook(path)
    return config


def _openpyxl_available():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def _dir_writable(d):
    try:
        Path(d).mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(d), delete=True):
            pass
        return True
    except Exception:
        return False


def _install_containers():
    """安装容器候选（保序去重）：调用路径（软链不解析）+ 真实路径（软链解析后）。
    容器 = 文件上溯四级：<容器>/[skills/]<技能>/scripts/x.py。"""
    seen, out = set(), []
    for f in (os.path.abspath(__file__), str(Path(__file__).resolve())):
        c = Path(f).parent.parent.parent.parent
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _is_home_level_install():
    """任一安装形态落在用户家目录的 skills 下（~/.zcode/skills、~/.claude/skills 等）：
    数据放 ~/减脂数据，不跟着某个项目工作区走。"""
    home = Path.home()
    return any(c in (home, home / ".zcode", home / ".agents", home / ".claude")
               for c in _install_containers())


def _local_data_dirs():
    """数据目录候选（优先级序）：
    项目级安装（<ws>/skills/<skill>/scripts）→ 工作区根的 减脂数据/；
    家目录级安装（~/.zcode/skills 等）→ ~/减脂数据；
    兜底当前目录、家目录。"""
    if _is_home_level_install():
        return [Path.home() / "减脂数据", Path.cwd() / "减脂数据"]
    return [c / "减脂数据" for c in _install_containers()] + \
        [Path.cwd() / "减脂数据", Path.home() / "减脂数据"]


def default_local_xlsx():
    """自动定位默认数据文件：候选目录里第一个可写的；全不可写返回首选（由调用方报错）。"""
    for d in _local_data_dirs():
        if _dir_writable(d):
            return d / "减脂追踪数据.xlsx"
    return _local_data_dirs()[0] / "减脂追踪数据.xlsx"


def _local_path(config):
    p = config.get("local_path") or str(default_local_xlsx())
    p = Path(p)
    return p if p.is_absolute() else (SCRIPT_DIR / p).resolve()


def storage_info(config):
    """当前数据位置（录入回执/SKILL 回复用）。"""
    return {"backend": "local", "file_path": str(_local_path(config)),
            "dashboard_path": str(dashboard_path(config))}


def dashboard_path(config):
    return _local_path(config).parent / DASHBOARD_NAME


def refresh_dashboard(config):
    """每次数据写入后重建本地 HTML 看板（失败只报错不阻断主流程）。"""
    try:
        from view import build_dashboard
        return {"ok": True, "dashboard_path": str(build_dashboard(config))}
    except Exception as e:
        return {"ok": False, "error": f"看板刷新失败: {e}"}


# ---------------------------------------------------------------- 本地 xlsx 后端
def _build_local_workbook(path):
    """创建本地工作簿：四张工作表 + 表头行。已存在则不覆盖。"""
    import openpyxl
    path = Path(path)
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, cols in SHEET_HEADERS.items():
        ws = wb.create_sheet(name)
        ws.append(cols)
    _atomic_save(wb, path)


def _local_load_wb(path):
    import openpyxl
    return openpyxl.load_workbook(path)


def _atomic_save(wb, path):
    """先写临时文件再原子替换，避免写一半中断损坏数据。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=str(path.parent))
    os.close(fd)
    try:
        wb.save(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _col_index(letter):
    from openpyxl.utils import column_index_from_string
    return column_index_from_string(str(letter).strip().replace("$", ""))


def _norm_cell(v):
    """读出值归一：datetime→YYYY-MM-DD 字符串；整数浮点→int；字符串 strip。"""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        return v.strip()
    return v


def _local_read(config, sheet_name, last_col, max_row=500):
    path = _local_path(config)
    if not path.exists():
        return None, {"ok": False, "error": f"本地数据文件不存在: {path}"}
    wb = _local_load_wb(path)
    if sheet_name not in wb.sheetnames:
        names = wb.sheetnames
        wb.close()
        return None, {"ok": False, "error": f"工作簿缺少工作表「{sheet_name}」，现有: {names}"}
    ws = wb[sheet_name]
    max_c = _col_index(last_col)
    header, records = [], []
    last_r = min(ws.max_row or 1, max_row)
    for r in range(1, last_r + 1):
        vals = [_norm_cell(ws.cell(row=r, column=c).value) for c in range(1, max_c + 1)]
        if not any(v not in (None, "") for v in vals):
            continue
        if r == 1:
            header = [("" if v is None else str(v)).strip() for v in vals]
            continue
        rec = {h: vals[i] for i, h in enumerate(header) if h}
        rec["_row"] = r
        records.append(rec)
    wb.close()
    return header, records


def _local_append(config, sheet_name, columns, dtypes=None, formats=None, rows=None):
    path = _local_path(config)
    if not path.exists():
        _build_local_workbook(path)
    wb = _local_load_wb(path)
    if sheet_name not in wb.sheetnames:
        wb.close()
        return {"ok": False, "error": f"工作簿缺少工作表「{sheet_name}」"}
    ws = wb[sheet_name]
    # 最后一个非空行（表头必占第 1 行），从其后追加，不重复写表头
    last = 1
    for r in range(1, ws.max_row + 1):
        if any(ws.cell(row=r, column=c).value not in (None, "")
               for c in range(1, ws.max_column + 1)):
            last = r
    header_map = {str(ws.cell(row=1, column=c).value or "").strip(): c
                  for c in range(1, ws.max_column + 1)}
    col_idx = []
    for name in columns:
        c = header_map.get(name)
        if c is None:
            wb.close()
            return {"ok": False, "error": f"工作表「{sheet_name}」无此列: {name}"}
        col_idx.append(c)
    for i, row in enumerate(rows):
        for c, val in zip(col_idx, row):
            ws.cell(row=last + 1 + i, column=c, value=val)
    _atomic_save(wb, path)
    wb.close()
    return {"ok": True, "appended": len(rows)}


def _local_set_cells(config, sheet_name, a1_range, values_2d):
    from openpyxl.utils import range_boundaries
    path = _local_path(config)
    if not path.exists():
        return {"ok": False, "error": f"本地数据文件不存在: {path}"}
    wb = _local_load_wb(path)
    if sheet_name not in wb.sheetnames:
        wb.close()
        return {"ok": False, "error": f"工作簿缺少工作表「{sheet_name}」"}
    ws = wb[sheet_name]
    min_col, min_row, max_col, max_row = range_boundaries(a1_range)
    for i, row in enumerate(values_2d):
        for j, v in enumerate(row):
            # openpyxl 的 cell(value=None) 是"不设置"，必须显式赋值 None 才能清空旧值
            ws.cell(row=min_row + i, column=min_col + j).value = v
    _atomic_save(wb, path)
    wb.close()
    return {"ok": True, "updated_range": a1_range}


# ---------------------------------------------------------------- 存储接口（签名兼容上层调用）
def append_rows(config, sheet_name, columns, dtypes=None, formats=None, rows=None):
    return _local_append(config, sheet_name, columns, dtypes, formats, rows)


def read_sheet(config, sheet_name, last_col, max_row=500):
    """读子表 → (表头list, 记录list[dict]，每条带 _row 1-based)。出错时 records 为错误 dict。"""
    return _local_read(config, sheet_name, last_col, max_row)


def set_cells(config, sheet_name, a1_range, values_2d):
    return _local_set_cells(config, sheet_name, a1_range, values_2d)


def die(msg):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


def out(obj, code=None):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code if code is not None else (0 if obj.get("ok", True) else 1))

# ---------------------------------------------------------------- 用户档案
def get_profile(config):
    """读取档案（第2行）。无档案返回 None。"""
    _, records = read_sheet(config, "用户档案", "U")
    if isinstance(records, dict):  # 出错
        return records
    if not records:
        return None
    rec = records[0]
    rec.pop("_row", None)
    return rec


def upsert_profile(config, fields):
    """合并写回档案单行（第2行）。显式传入的键即写入（含 None/"" = 清空），未传入的保持原值。
    目标体重kg 被写入且未显式给 减重路径 时，自动按 初始→目标 每 5kg 重算路径
    （防只改目标不改路径：路径停在旧目标，到档会被 advance_tier 误判为已到最终目标）。"""
    _, existing_rows = read_sheet(config, "用户档案", "U")
    if isinstance(existing_rows, dict) and not existing_rows.get("ok", True):
        return existing_rows
    current = {k: None for k in PROFILE_COLS}
    if existing_rows:
        for k in PROFILE_COLS:
            current[k] = existing_rows[0].get(k)
    for k, v in fields.items():
        if k not in PROFILE_COLS:
            return {"ok": False, "error": f"档案无此字段: {k}，合法字段：{PROFILE_COLS}"}
        current[k] = v  # 显式传入即写入（含 None/"" = 清空）；未传入的键保持原值
    auto = {}
    if "目标体重kg" in fields and "减重路径" not in fields:
        try:
            start, target = float(current.get("初始体重kg")), float(current.get("目标体重kg"))
        except (TypeError, ValueError):
            start = target = None
        if start is not None and start > target:
            tiers = build_tiers(start, target)
            if tiers:
                current["减重路径"] = "→".join(str(_fmt_weight(w)) for w in [start] + tiers)
                auto["减重路径"] = current["减重路径"]
                cur = current.get("当前档位kg")
                try:
                    in_path = cur is not None and any(
                        abs(float(cur) - t) < 1e-9 for t in tiers)
                except (TypeError, ValueError):
                    in_path = False
                if "当前档位kg" not in fields and not in_path:
                    current["当前档位kg"] = tiers[0]
                    auto["当前档位kg"] = tiers[0]
    values = [[current.get(k) for k in PROFILE_COLS]]
    r = set_cells(config, "用户档案", "A2:U2", values)
    if not r.get("ok"):
        return r
    resp = {"ok": True, "profile": current}
    if auto:
        resp["auto_recomputed"] = auto
    return resp

# ---------------------------------------------------------------- 阶梯减重 / 营养素
def build_tiers(start_weight, target_weight, step=WEIGHT_STEP_KG):
    """初始体重 → 目标体重，每 step kg 一档（含首尾）。"""
    if start_weight is None or target_weight is None or start_weight <= target_weight:
        return []
    tiers = []
    w = start_weight
    while w > target_weight:
        w -= step
        tiers.append(round(max(w, target_weight), 1))
    if not tiers or tiers[-1] != target_weight:
        tiers.append(round(target_weight, 1))
    return tiers


def protein_multiplier(days_per_week):
    """按每周训练天数定蛋白倍数：1-2练×1 / 3-4练×1.2 / 5-6练×1.5。"""
    try:
        d = int(days_per_week)
    except (TypeError, ValueError):
        return 1.2
    if d <= 2:
        return 1.0
    if d <= 4:
        return 1.2
    return 1.5


def calc_macros(tier_weight, days_per_week, carb_mult=3.0):
    """按当前档位体重算营养素（克）。碳水×2~3（新手3起步，适应后2）；蛋白按天数；脂肪×1。"""
    if tier_weight is None:
        return {"carb_g": None, "protein_g": None, "fat_g": None}
    return {
        "carb_g": round(tier_weight * carb_mult),
        "protein_g": round(tier_weight * protein_multiplier(days_per_week)),
        "fat_g": round(tier_weight * 1.0),
    }


def advance_tier(profile, today_weight):
    """阶段联动：体重达标则进下一档。返回 (新档案fields, 进阶信息dict 或 None)。"""
    cur_tier = profile.get("当前档位kg")
    path = (profile.get("减重路径") or "")
    tiers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(path))]
    if cur_tier is None or today_weight is None:
        return {}, None
    try:
        cur_tier = float(cur_tier)
    except (TypeError, ValueError):
        return {}, None
    if today_weight > cur_tier:
        return {}, None
    # 达标：找下一档
    next_tier = None
    for t in tiers:
        if t < cur_tier - 1e-9:
            next_tier = t
            break
    if next_tier is None:
        # 已到最终档
        return {}, {"reached_final": True, "tier": cur_tier}
    macros = calc_macros(next_tier, profile.get("每周训练天数"))
    fields = {"当前档位kg": next_tier, "碳水g": macros["carb_g"],
              "蛋白g": macros["protein_g"], "脂肪g": macros["fat_g"]}
    return fields, {"advanced": True, "from_kg": cur_tier, "to_kg": next_tier, "macros": macros}

# ---------------------------------------------------------------- 渐进超负荷
def next_progression(weight, reps):
    """次数 10→12→15；到15后重量+5%、次数回10。返回 (新重量, 新次数)。"""
    try:
        w = float(weight or 0)
        r = int(float(reps))
    except (TypeError, ValueError):
        return weight, reps
    nxt = next((x for x in REP_LADDER if x > r), None)
    if nxt is not None:
        return _fmt_weight(w), nxt
    new_w = round(w * 1.05, 1)
    return _fmt_weight(new_w), 10


def _fmt_weight(w):
    if w is None:
        return 0
    if abs(w - round(w)) < 0.01:
        return int(round(w))
    return round(w, 1)

# ---------------------------------------------------------------- 训练日
def parse_training_days(text):
    """'1,3,5' / '一三五' / '周一周三' → [1,3,5]（1=周一…7=周日）。"""
    if text is None:
        return []
    s = str(text)
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
    days = set()
    for ch in s:
        if ch in cn:
            days.add(cn[ch])
    for n in re.findall(r"[1-7]", s):
        days.add(int(n))
    return sorted(days)


def next_training_date(profile, after=None):
    """档案训练日安排之后的第一个训练日；未配置则返回明天。"""
    after = after or date.today()
    days = parse_training_days(profile.get("训练日安排") if profile else None)
    d = after + timedelta(days=1)
    if not days:
        return d, False
    for _ in range(7):
        if d.isoweekday() in days:  # isoweekday: Mon=1
            return d, True
        d += timedelta(days=1)
    return after + timedelta(days=1), False


def next_open_training_date(profile, after, busy_rows, max_advance=6):
    """第一个没有待完成计划的训练日（首周默认计划按主题轮转占位后，
    下次同主题计划要跳过已占用的训练日，避免一天两份计划）。
    busy_rows：训练记录全量行；连续 max_advance 个训练日全满则退回第一个（原行为）。"""
    booked = {str(p.get("日期") or "") for p in busy_rows
              if isinstance(p, dict) and str(p.get("状态") or "").strip() == "待完成"}
    d, fallback = after, None
    for _ in range(max_advance):
        d, scheduled = next_training_date(profile, after=d)
        if fallback is None:
            fallback = (d, scheduled)
        if d.strftime("%Y-%m-%d") not in booked:
            return d, scheduled
    return fallback


def today_str():
    return datetime.now().strftime("%Y-%m-%d")
