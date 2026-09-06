# 动作教学视频映射表

> **唯一数据源在 `scripts/fitlib.py` 的 `EXERCISE_VIDEOS`**，本表是它的可读快照（含核实标题），两处需同步维护。
> 脚本（plan.py / record.py / brief.py / view.py）运行时都从 fitlib 取链接，本文档供人查阅和 AI 兜底参考。

## 维护红线（必须遵守）

1. **编造 URL 是红线**：映射表里没有的动作，一律不带链接，绝不现编
2. **新增/替换链接必须先人工核实**：逐条确认 HTTP 可访问 + 页面标题与动作匹配（B 站可用官方接口 `https://api.bilibili.com/x/web-interface/view?bvid=<BV号>` 复核，`code=0` 即存在）
3. 链接失效（下架/私密）时：删除或替换并重新核实，不让死链留在表里
4. 动作名必须与 `DEFAULT_PLAN_TEMPLATES` 里的动作名**精确一致**（匹配靠动作名全等）

## 当前映射（20 个动作，核实日期 2026-09-06，全部 API code=0）

| 动作 | 视频 | 链接 |
|---|---|---|
| 深蹲 | 如何完成一个标准深蹲？ | https://www.bilibili.com/video/BV1ZdzLBqEjz/ |
| 俯卧撑 | 如何做一个标准俯卧撑？ | https://www.bilibili.com/video/BV1oX5X6mEKL/ |
| 臀桥 | 练臀腰酸？如何做一个标准臀桥？超详细动作教程一看就会 | https://www.bilibili.com/video/BV1Yf4y197op/ |
| 平板支撑 | 你真的做对平板支撑了吗？（保姆级教学） | https://www.bilibili.com/video/BV1Q34y1j79r/ |
| 箭步蹲 | 箭步蹲详解 | https://www.bilibili.com/video/BV1gRbDzSER1/ |
| 提踵 | 【站姿提踵】锻炼小腿、打造小腿轮廓，徒手健身动作解析 | https://www.bilibili.com/video/BV1Vs421M7gV/ |
| 哑铃划船 | 30秒教你如何做一个标准的哑铃划船 | https://www.bilibili.com/video/BV1RM4m1S77p/ |
| 哑铃肩推 | 坐姿哑铃推肩动作详解 让肩部全程吃力 | https://www.bilibili.com/video/BV1LR7uzEEDL/ |
| 哑铃飞鸟 | 【哑铃飞鸟】动作详解，新手健身干货 | https://www.bilibili.com/video/BV1jY4y1G7h7/ |
| 哑铃弯举 | 健身房教学指南｜哑铃弯举这么做更有效！ | https://www.bilibili.com/video/BV1anmCYNEbK/ |
| 侧平举 | 【保姆级教程】哑铃侧平举——宽肩必不可少 | https://www.bilibili.com/video/BV1YR4y1v7ZY/ |
| 俯身飞鸟 | 俯身哑铃飞鸟练肩后束（新手孤立感教学） | https://www.bilibili.com/video/BV1gcmXBJEgV/ |
| 超人式 | 无器械健身，锻炼下背部肌肉，超人训练动作技术要点分析 | https://www.bilibili.com/video/BV1yt411Z75Y/ |
| 直臂下拉 | 哑铃直臂上拉（居家版直臂下拉）新手健身教学 | https://www.bilibili.com/video/BV1RT41157oz/ |
| 上斜俯卧撑 | 上斜俯卧撑：初学者或肥胖人群适用 | https://www.bilibili.com/video/BV1cH4y1V7sy/ |
| 哑铃臂屈伸 | 肱三头肌训练之哑铃臂屈伸 | https://www.bilibili.com/video/BV1c541187Wg/ |
| 椅上臂屈伸 | "板凳臂屈伸"训练须知 | https://www.bilibili.com/video/BV1Ft4y197JS/ |
| 卷腹 | 练腹肌，先做好一个卷腹动作！ | https://www.bilibili.com/video/BV1x1376RE8D/ |
| 俄罗斯转体 | 练对瘦腰，练错伤腰！俄罗斯转体完整讲解 | https://www.bilibili.com/video/BV1R2421M7oi/ |
| 登山跑 | 王牌HIIT动作登山跑详细分解 | https://www.bilibili.com/video/BV1Vb411Y7Mc/ |
