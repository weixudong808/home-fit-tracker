#!/usr/bin/env python3
"""个人健身数据录入脚本 - 统一处理训练、体重、饮食记录（本地 xlsx 存储）。
用法:
  # 训练记录（自动联动：旧计划置已跳过 + 按渐进超负荷生成下次计划）
  python3 record.py training --date 2026-09-06 --theme 上肢 --exercises '[{"name":"俯卧撑","sets":4,"reps":12,"weight":0,"notes":"备注"}]'
  # 体重记录（自动联动：更新档案 + 达标自动进档重算营养素）
  python3 record.py weight --date 2026-09-06 --weight 75.5 --body-fat 18.2
  # 饮食记录
  python3 record.py diet --date 2026-09-06 --meal 午餐 --content "米饭+鸡胸肉+西兰花"
每次成功录入后自动刷新本地 HTML 看板（dashboard 字段返回看板路径）。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(Path(__file__).absolute().parent))  # 调用目录优先（软链不解析，fitlib 靠它识别安装形态）
import fitlib as fl  # noqa: E402


def _with_video(items):
    """计划条目补教学链接（映射没有的为 None，调用方不带你别编）。"""
    for it in items:
        it["video"] = fl.video_for(it.get("name"))
    return items


def record_training(config, args):
    """录入训练记录。"""
    exercises = json.loads(args.exercises) if isinstance(args.exercises, str) else args.exercises
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    theme = args.theme or infer_theme(exercises)
    rows = []
    for ex in exercises:
        rows.append([
            date,
            theme,
            ex.get("name", ""),
            ex.get("sets", 0),
            ex.get("reps", 0),
            ex.get("weight", 0),
            ex.get("notes", ""),
            "已完成",
        ])
    result = fl.append_rows(
        config, "训练记录",
        fl.TRAIN_COLS,
        {"日期": "datetime64[ns]", "组数": "float64", "次数": "float64", "重量kg": "float64"},
        {"日期": "yyyy-mm-dd"},
        rows,
    )
    if result.get("ok"):
        resp = {
            "ok": True,
            "type": "training",
            "date": date,
            "theme": theme,
            "count": len(rows),
            "exercises": [ex.get("name") for ex in exercises],
        }
        resp.update(fl.storage_info(config))
        if not getattr(args, "no_plan", False):
            resp["plan_link"] = link_training_plan(config, date, theme, exercises)
        resp["dashboard"] = fl.refresh_dashboard(config)
        return resp
    return result


def link_training_plan(config, date, theme, exercises):
    """训练录入联动（单表版）：同部位旧待完成计划置「已跳过」+ 按渐进超负荷生成下次计划行。失败不影响录入。"""
    info = {"skipped_plan_rows": [], "next_plan": None}
    try:
        _, rows_all = fl.read_sheet(config, "训练记录", "H")
        skipped = set()
        if isinstance(rows_all, list):
            for p in rows_all:
                if (str(p.get("状态") or "待完成").strip() == "待完成"
                        and str(p.get("训练主题") or "").strip() == theme
                        and str(p.get("日期") or "") <= date):
                    r = fl.set_cells(config, "训练记录", f"H{p['_row']}", [["已跳过"]])
                    if r.get("ok"):
                        info["skipped_plan_rows"].append(p["_row"])
                        skipped.add(p["_row"])
        profile = fl.get_profile(config)
        after = datetime.strptime(date, "%Y-%m-%d").date()
        next_d, scheduled = fl.next_open_training_date(
            profile or {}, after=after,
            busy_rows=rows_all if isinstance(rows_all, list) else [])
        next_date = next_d.strftime("%Y-%m-%d")
        dup = False
        if isinstance(rows_all, list):
            dup = any(
                p.get("_row") not in skipped
                and str(p.get("日期") or "") == next_date
                and str(p.get("训练主题") or "").strip() == theme
                and str(p.get("状态") or "").strip() == "待完成"
                for p in rows_all)
        if not dup:
            plan_rows, progressed = [], []
            for ex in exercises:
                w, reps = fl.next_progression(ex.get("weight", 0), ex.get("reps", 10))
                sets = int(float(ex.get("sets", 3)))
                plan_rows.append([next_date, theme, ex.get("name", ""), sets, reps, w,
                                  f"基于{date}训练自动进阶", "待完成"])
                progressed.append({"name": ex.get("name", ""), "sets": sets,
                                   "reps": reps, "weight": w,
                                   "from": f"{ex.get('weight',0)}kg×{ex.get('reps',10)}次"})
            wres = fl.append_rows(
                config, "训练记录", fl.TRAIN_COLS,
                {"日期": "datetime64[ns]", "组数": "float64",
                 "次数": "float64", "重量kg": "float64"},
                {"日期": "yyyy-mm-dd"}, plan_rows)
            if wres.get("ok"):
                info["next_plan"] = {"date": next_date,
                                     "scheduled_by_profile": scheduled,
                                     "items": _with_video(progressed)}
            else:
                info["next_plan_error"] = wres.get("error")
    except Exception as e:  # 联动兜底，不影响已成功的录入
        info["link_error"] = str(e)
    return info


def record_weight(config, args):
    """录入体重记录。"""
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    row = [date, args.weight]
    if args.body_fat is not None:
        row.append(args.body_fat)
    else:
        row.append(None)
    row.append(args.notes or "")
    result = fl.append_rows(
        config, "体重记录",
        fl.WEIGHT_COLS,
        {"日期": "datetime64[ns]", "体重kg": "float64", "体脂率%": "float64"},
        {"日期": "yyyy-mm-dd"},
        [row],
    )
    if result.get("ok"):
        resp = {
            "ok": True,
            "type": "weight",
            "date": date,
            "weight": args.weight,
            "body_fat": args.body_fat,
        }
        resp.update(fl.storage_info(config))
        if not getattr(args, "no_link", False):
            resp["profile_link"] = link_weight(config, args.weight, args.body_fat)
        resp["dashboard"] = fl.refresh_dashboard(config)
        return resp
    return result


def link_weight(config, weight, body_fat):
    """体重录入联动：更新档案当前体重 + 阶段联动（达标自动进档、重算营养素）。"""
    info = {}
    try:
        fields = {"当前体重kg": weight}
        if body_fat is not None:
            fields["体脂率%"] = body_fat
        fl.upsert_profile(config, fields)
        profile = fl.get_profile(config)
        if profile:
            new_fields, event = fl.advance_tier(profile, weight)
            if event:
                info["tier_event"] = event
                if new_fields:
                    fl.upsert_profile(config, new_fields)
    except Exception as e:
        info["link_error"] = str(e)
    return info


def record_diet(config, args):
    """录入饮食记录。"""
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    meal = args.meal or infer_meal()
    row = [date, meal, args.content, args.notes or ""]
    result = fl.append_rows(
        config, "饮食记录",
        fl.DIET_COLS,
        {"日期": "datetime64[ns]"},
        {"日期": "yyyy-mm-dd"},
        [row],
    )
    if result.get("ok"):
        resp = {
            "ok": True,
            "type": "diet",
            "date": date,
            "meal": meal,
            "content": args.content,
        }
        resp.update(fl.storage_info(config))
        resp["dashboard"] = fl.refresh_dashboard(config)
        return resp
    return result


def infer_theme(exercises):
    """根据动作推断训练主题。整堂课匹配默认计划模板优先（上肢/下肢等混合主题靠单动作推不出）。"""
    names = [str(ex.get("name", "")).strip() for ex in exercises]
    best, best_hits = None, 0
    for tpl in fl.DEFAULT_PLAN_TEMPLATES.values():
        for theme, moves in tpl.items():
            hits = sum(1 for n in names if n in moves)
            if hits > best_hits:
                best, best_hits = theme, hits
    if best_hits >= 2:
        return best
    # 精确动作名 → 主题（按模板定义顺序，先出现先归）
    exact = {}
    for tpl in fl.DEFAULT_PLAN_TEMPLATES.values():
        for theme, moves in tpl.items():
            for m in moves:
                exact.setdefault(m, theme)
    for n in names:
        if n in exact:
            return exact[n]
    theme_map = {
        "胸": ["卧推", "推胸", "夹胸", "飞鸟", "俯卧撑", "臂屈伸"],
        "背": ["引体", "划船", "硬拉", "超人式", "下拉"],
        "腿": ["深蹲", "蹲", "箭步", "臀桥", "提踵", "腿举"],
        "肩": ["肩推", "推肩", "侧平举", "前平举"],
        "手臂": ["弯举", "下压"],
        "核心": ["平板支撑", "卷腹", "俄罗斯转体", "登山跑", "举腿"],
        "有氧": ["跑步", "跳绳", "开合跳", "波比跳", "快走", "骑车", "游泳", "跳操"],
    }
    for ex in exercises:
        name = ex.get("name", "")
        for theme, keywords in theme_map.items():
            if any(kw in name for kw in keywords):
                return theme
    return "全身"


def infer_meal():
    """根据当前时间推断餐次。"""
    hour = datetime.now().hour
    if hour < 10:
        return "早餐"
    elif hour < 14:
        return "午餐"
    elif hour < 18:
        return "加餐"
    else:
        return "晚餐"


def main():
    parser = argparse.ArgumentParser(description="个人健身数据录入")
    subparsers = parser.add_subparsers(dest="type", required=True)
    # 训练
    p_train = subparsers.add_parser("training", help="录入训练记录")
    p_train.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    p_train.add_argument("--theme", help="训练主题，默认自动推断")
    p_train.add_argument("--exercises", required=True, help='动作JSON，如 [{"name":"俯卧撑","sets":4,"reps":12,"weight":0}]')
    p_train.add_argument("--no-plan", action="store_true", help="只录入，不生成下次训练计划")
    # 体重
    p_weight = subparsers.add_parser("weight", help="录入体重记录")
    p_weight.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    p_weight.add_argument("--weight", type=float, required=True, help="体重 kg")
    p_weight.add_argument("--body-fat", type=float, help="体脂率 %")
    p_weight.add_argument("--notes", help="备注")
    p_weight.add_argument("--no-link", action="store_true", help="只录入，不更新档案/档位")
    # 饮食
    p_diet = subparsers.add_parser("diet", help="录入饮食记录")
    p_diet.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    p_diet.add_argument("--meal", help="餐次：早餐/午餐/晚餐/加餐，默认按时间推断")
    p_diet.add_argument("--content", required=True, help="食物内容描述")
    p_diet.add_argument("--notes", help="备注")
    args = parser.parse_args()
    config = fl.load_config()
    if args.type == "training":
        result = record_training(config, args)
    elif args.type == "weight":
        result = record_weight(config, args)
    elif args.type == "diet":
        result = record_diet(config, args)
    else:
        result = {"ok": False, "error": f"未知类型: {args.type}"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
