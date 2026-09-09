# home-fit-tracker · 居家减脂私教（全平台 Agent 通用）

个人居家减脂助手：自然语言记录训练/饮食/体重，训练计划按渐进超负荷自动滚动（每个动作配人工核实过的 B 站教学视频链接），体重达标自动换档重算营养素，每日早安简报定时提醒。数据存本地 xlsx + 自动刷新的 HTML 看板，聊天里能看、点开也能看。

## 安装到 ZCode

```bash
mkdir -p ~/.zcode/skills && cp -r home-fit-tracker ~/.zcode/skills/ && python3 -B ~/.zcode/skills/home-fit-tracker/scripts/profile.py get
```
输出 `profile: null` 即装好（首次运行自动建表，数据在 `~/减脂数据/`）。重开对话直接说"我想开始减脂"即可触发建档。

装到项目里（只在该项目用）：把 `home-fit-tracker` 复制到项目的 `.zcode/skills/` 下，数据落在项目根的 `减脂数据/`。

## 安装到其他 Agent（通用套路）

任何能执行 shell 命令的 Agent（Claude Code → `~/.claude/skills/`，或其他）：

1. 把本目录交给 Agent，让它读 `SKILL.md` 并按其执行（SKILL.md 是行为指令，全部业务逻辑在 `scripts/`）
2. 依赖：Python 3.9+、openpyxl（缺了 `pip install openpyxl`）
3. 定时早报：只有平台有定时任务能力才能建（SKILL.md §5）；没有就跳过，其余功能不受影响

## 目录结构

```
home-fit-tracker/
├── SKILL.md              # AI 行为指令（核心）
├── README.md
├── references/
│   └── cron_prompts.md   # 早报定时任务操作手册 + prompt 模板
└── scripts/
    ├── record.py         # 训练/体重/饮食录入（带自动联动 + 自动刷看板）
    ├── profile.py        # 用户档案读写
    ├── plan.py           # 训练计划生成/查询/核销/首周默认计划（居家 1-6 练模板）
    ├── storage.py        # 统一查询入口
    ├── view.py           # HTML 看板生成（每次录入后自动刷新）；--shot 截图 PNG（远程/IM 部署发图用）
    ├── brief.py          # 早报数据汇总（定时会话一条命令读全表）
    ├── fitlib.py         # 公共库（存储/阶梯减重/营养素/渐进超负荷）
    └── config.json       # local_path 覆盖、cron 任务 id；一般不用手动改
```

## 数据与隐私

- 数据全部在本地 `减脂数据/`（家目录级安装 → `~/减脂数据/`；项目级安装 → 项目根 `减脂数据/`），不经过任何第三方
- 重置：删除 `减脂数据/` 目录，下次运行自动重建空表（SKILL.md 规定 AI 必须二次确认后才执行）
- 升级：用新代码覆盖技能目录即可，数据在技能目录外不受影响

## 与 fat-loss-tracker（千问版）的关系

同源架构（薄 AI + 厚脚本），主要差异：
- 本地 xlsx 单后端（去掉飞书，所有 Agent 的通用分母）
- 训练模板改为居家版（自重 + 哑铃，1-6 练全覆盖）
- 动作教学视频链接内置（`EXERCISE_VIDEOS` 人工核实制，聊天/看板/早报三处展示，映射没有的不带、不编）
- 新增 HTML 看板：每次录入自动刷新，用户随时点开看全部数据；远程/IM 部署（agent 在服务器、用户在聊天软件）用 `view.py --shot` 截图发进聊天（file:// 链接跨设备点不开）
- 早报改为"brief.py 读表 + 自包含 prompt"：定时会话是全新上下文，读不到聊天记录，一切以表格数据为准；缺勤分支（轻提/想念/牵挂）由数据口径驱动
- 去掉千问注册包全部约束（82KB 载荷、引用完整性、附件发送变通）

## 许可证

[PolyForm Noncommercial 1.0.0](LICENSE)：个人和非商业用途免费使用、修改、分发；**商业用途需另行获得授权**（联系作者洽谈商用许可）。
