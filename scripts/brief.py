#!/usr/bin/env python3
"""早安简报数据汇总：一条命令给齐简报所需的全部数据，避免定时会话里让 AI 自己算星期几/数缺勤天数。
用法（定时任务 prompt 里引用）:
  python3 -B brief.py                 # 按今天出数据
  python3 -B brief.py --date 2026-09-07   # 预览/调试指定日期（训练日早报、缺勤分支等）
返回 JSON：档案要点、今天是否训练日及待完成计划（动作带教学链接）、昨天计划回收钩子、今天已做事项、缺勤天数。
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(Path(__file__).absolute().parent))  # 调用目录优先（软链不解析，fitlib 靠它识别安装形态）
import fitlib as fl  # noqa: E402

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def _s(v):
    return str(v or "").strip()


def main():
    ap = argparse.ArgumentParser(description="早安简报数据汇总")
    ap.add_argument("--date", help="按指定日期出数据（YYYY-MM-DD），预览/调试用；默认今天")
    args = ap.parse_args()
    config = fl.load_config()
    profile = fl.get_profile(config) or {}
    today = date.fromisoformat(args.date) if args.date else date.today()
    t_key = today.strftime("%Y-%m-%d")
    y_key = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    _, train = fl.read_sheet(config, "训练记录", "H")
    _, weight = fl.read_sheet(config, "体重记录", "D")
    _, diet = fl.read_sheet(config, "饮食记录", "D")
    train = train if isinstance(train, list) else []
    weight = weight if isinstance(weight, list) else []
    diet = diet if isinstance(diet, list) else []

    done = [r for r in train if _s(r.get("状态")) == "已完成"]
    plans = [r for r in train if _s(r.get("状态")) == "待完成"]

    # 今天计划（按主题分组，动作附教学链接）
    themes = {}
    for r in plans:
        if _s(r.get("日期")) == t_key:
            name = r.get("动作名称")
            themes.setdefault(_s(r.get("训练主题")), []).append(
                {"name": name, "sets": r.get("组数"),
                 "reps": r.get("次数"), "weight": r.get("重量kg"),
                 "video": fl.video_for(name)})
    plan_list = [{"theme": k, "items": v} for k, v in themes.items()]

    # 今天已做（去重铁律的依据：已做的不提醒换成认可）
    training_done_today = any(_s(r.get("日期")) == t_key for r in done)
    weight_today = any(_s(r.get("日期")) == t_key for r in weight)
    diet_today = any(_s(r.get("日期")) == t_key for r in diet)

    # 昨天回收钩子：昨天有计划但没交作业
    yesterday_hook = (any(_s(r.get("日期")) == y_key for r in plans)
                      and not any(_s(r.get("日期")) == y_key for r in done))

    # 训练日判断（isoweekday 1=周一…7=周日，与 parse_training_days 口径一致）
    days_cfg = fl.parse_training_days(profile.get("训练日安排"))
    is_training_day = (today.isoweekday() in days_cfg) if days_cfg else None

    # 缺勤天数：从昨天往前数连续没有任何记录的天数；从没记录过 = 新用户，不计缺勤
    date_set = {_s(r.get("日期")) for r in done}
    date_set |= {_s(r.get("日期")) for r in weight}
    date_set |= {_s(r.get("日期")) for r in diet}
    date_set.discard("")
    last_record = max(date_set) if date_set else None
    new_user = last_record is None
    absent = 0
    if last_record:
        d = today - timedelta(days=1)
        while d.strftime("%Y-%m-%d") > last_record and absent <= 60:
            absent += 1
            d -= timedelta(days=1)

    fl.out({
        "ok": True,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "profile": {
            "用户昵称": profile.get("用户昵称"),
            "回复风格": profile.get("回复风格"),
            "记忆备注": profile.get("记忆备注"),
            "当前体重kg": profile.get("当前体重kg"),
            "目标体重kg": profile.get("目标体重kg"),
            "当前档位kg": profile.get("当前档位kg"),
            "碳水g": profile.get("碳水g"),
            "蛋白g": profile.get("蛋白g"),
            "脂肪g": profile.get("脂肪g"),
            "训练日安排": profile.get("训练日安排"),
            "每周训练天数": profile.get("每周训练天数"),
        },
        "today": {
            "date": t_key,
            "weekday": "周" + WEEKDAY_CN[today.weekday()],
            "is_training_day": is_training_day,
            "has_plan": bool(plan_list),
            "plan": plan_list,
            "training_done_today": training_done_today,
        },
        "yesterday_hook": yesterday_hook,
        "activity": {"weight_today": weight_today, "diet_today": diet_today},
        "absence": {"days": absent, "last_record_date": last_record, "new_user": new_user},
    })


if __name__ == "__main__":
    main()
