# Product Selector — Amazon 精铺选品 Skill

基于 **Sorftime CLI** 的 Amazon 选品分析，融合 ZPR 市场调研方法论 + 飞书运营闭环。
单产品完整分析约 5-10 分钟，输出速判卡 + 完整报告。

## 快速上手（3 个最常用场景）

### 场景 1：给一个 ASIN，跑全流程

```
帮我分析 B0F9JZSK2Q
```

自动执行：产品详情 → 关键词 → 类目 Top100 → 属性标注 → 交叉分析 → Go/No-Go → 写入飞书。
如果评分 GO，自动触发初筛、产品开发。（财务分析需你提供成本后触发）

### 场景 2：给一个关键词 / 品类名

```
nail drill 这个品类值得做吗
printer stand 帮我看看市场
```

自动执行：关键词搜索 → 类目定位 → 数据分析 → 飞书写入。
适合市场初筛——只想知道干不干得，不想投入完整 ASIN 分析。

### 场景 3：批量跑选品表

```
产品初选表里待分析的都帮我跑
```

遍历飞书「产品初选」表里所有「推进状态=待分析」的记录，逐个执行分析。

---

## 使用技巧

### 互动方式

**中途给成本数据**（最重要）：

```
成本 $8，头程 $5，CPC $0.70，CVR 8%
```

AI 会写入飞书 AI 分析参考表，然后**自动触发财务分析 48 字段**。
你也可以直接在飞书表对应字段里填——下次对话开始时 AI 回读发现后自动触发。

**需要的关键运营数据**：

| 字段 | 从哪来 | 用途 |
|------|--------|------|
| 1688 采购价 | 1688 搜索 / 供应商报价 | 决定 M 值 |
| 头程运费 | 货代报价 | 决定落地成本 |
| 当前 CPC | 广告后台 Campaign 实际数据 | 决定盈亏平衡 |
| 当前点击 CVR | **广告后台必填**（Sorftime 不提供此数据） | 决定广告 CPA |

> ⚠️ Sorftime 的 `SearchConversionRate` 是搜索→购买转化率，不是点击 CVR。点击 CVR 必须你自己填。

**继续 / 暂停**：
- "继续" → AI 检查飞书 6 张表哪些缺了，逐个补上
- "帮我更新下报告" → 最新数据回写 decision-card + full-report

### 流程说明

分析完成后，AI 会弹出「运营数据输入」窗口——**必须在弹窗出现后才继续下一步**。
不要跳过成本输入直接要求报告。

### 决策类型

| 决策 | 含义 | 后续动作 |
|------|------|----------|
| **GO** (≥7.5) | 推荐进入 | 自动触发初筛+产品开发 |
| **CONDITIONAL GO** (6.0-7.4) | 有条件进入 | 触发初筛+产品开发，标注待确认项 |
| **HOLD** (4.0-5.9) | 暂缓 | 停止，记录暂缓原因 |
| **NO-GO** (<4.0) | 放弃 | 停止，记录放弃数据依据 |

---

## 输出物

### 1. 飞书 6 张表

| 表 | 字段 | 何时写 |
|----|------|--------|
| 产品初选 | ASIN/关键词/类目/价格带/推进状态 | 永远 |
| **AI分析参考** | 35 字段（23 结构化数字 + 8 文本 + 4 运营） | **永远（不跳）** |
| 产品初筛 | 11/16 维度 AI 填写 + 5 人工补充 | GO / CONDITIONAL GO |
| 财务分析 | 48 字段 P&L + 月模拟 | 你提供成本后 |
| 产品开发 | 差异化方向 / 人群 / 场景 / 矩阵 | GO / CONDITIONAL GO |
| 供应商管理 | 1688 链接 / 采购价 / MOQ | 你提供 1688 信息后 |

### 2. 磁盘报告

```
~/product-selector-reports/<市场名>-<日期>/
├── decision-card.html  → 半屏速判卡（手机）
└── full-report.md      → 完整报告（≥10 章）
```

---

## 重要数据字段说明

| 字段 | 含义 | 来源 | 能用于CPC/CVR计算？ |
|------|------|------|:--:|
| 核心词月搜索量 | SearchVolume | KeywordRequest | ✅ |
| 核心词 CPC | Cpc (当前市场竞价) | KeywordRequest | ✅ |
| 核心词搜索转化率 | SearchConversionRate（搜索→购买） | KeywordRequest | ❌ 不能用于广告效率 |
| 当前 CPC | 你的实际 CPC | **你从广告后台填** | ✅ |
| 当前点击 CVR | 点击→购买 | **你从广告后台填** | ✅ |
| Top3 品牌点击集中度 | ShareClickRate | KeywordRequest | — 越低越分散越蓝海 |
| 类目新品占比 | ≤6 月新品 / Top100 总产品 | CategoryRequest | — ≥20%=友好 <10%=红灯 |
| 平均评论门槛 | Top100 平均评论数 | CategoryRequest | — <300=低壁垒 >1000=高壁垒 |
| M 值 | 实际回款 / 落地成本 | PFM 公式 | — >2.0=健康 <1.0=亏损 |

---

## 常见问题

### Q: 为什么分析完没有初筛/财务？
A: 评分 HOLD 或 NO-GO 时不触发初筛。财务分析需要你提供 1688 采购价 + 头程 + CPC + CVR。

### Q: 怎么输入成本？
A: 三种方式：① 分析完成后的弹窗里告诉 AI ② 在对话中说"成本 $X 头程 $Y" ③ 在飞书 AI分析参考表里手动填。

### Q: 数据会不会编造？
A: 所有市场数据来自 Sorftime CLI 实测。每个数据点标注来源（ProductRequest / KeywordRequest / 用户提供）。估算标注"估"和置信度。

### Q: 分析要花多少钱？
A: 单产品完整流程约 18-120 次 Sorftime API 请求（取决于是否做属性标注+交叉分析）。快速筛选模式仅约 47 次请求。查看余额：`sorftime whoami`。

### Q: CPC 和 CVR 为什么必须人工填？
A: CLI + MCP 共 11 个端点均不提供点击 CVR。Sorftime 只提供 SearchConversionRate（搜索→购买），不是点击转化率。

---

## 安装

### 前置条件

- **Claude Code** 或支持 Skill 的 IDE
- `sorftime` CLI → `npm install -g sorftime-cli`
- `lark-cli` → 飞书 CLI
- Python 3 → `scripts/attribute-tagger.py` 需要（可选）

### 安装 Skill

```bash
# 1. 克隆到 skills 目录
git clone https://github.com/zhangxinxin2323-ui/product-selector.git ~/.claude/skills/product-selector

# 2. 重启 IDE / 新开会话
```

### 配置飞书表

Skill 默认写入飞书多维表格 `rwlz9eyyr5o.feishu.cn`。如需改为你自己的表，修改 `SKILL.md` 和 `references/bitable-schema.md` 中的 App Token。

---

## 文件结构

```
product-selector/
├── SKILL.md                    # 主工作流（580行）
├── README.md                   # 使用指南（本文件）
├── .gitignore
├── evals/evals.json            # 测试用例
├── references/
│   ├── analysis-patterns.md    # 4 种分析模式（数据→空白→机会等）
│   ├── attribute-tagging.md    # Top100 属性标注指南
│   ├── bitable-schema.md       # 飞书 6 表完整字段
│   ├── cross-analysis.md       # 交叉分析方法论
│   ├── go-nogo-scoring.md      # 5 维加权评分体系
│   └── html-report-spec.md     # HTML 决策卡布局规范
└── scripts/
    └── attribute-tagger.py     # Top100 属性标注 + 交叉分析脚本
```

## 8 轮测试记录

| # | 市场 | 搜索量 | CPC | Top3% | 新品率 | 评论 | 评分 | M值 | 决策 |
|---|------|:-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Satellite Mounts | 107K | $2.15 | 32% | 28% | 162 | 7.85 | — | GO |
| 2 | Printer Stands | 98.5K | $0.65 | 24% | 11% | 445 | 6.95 | — | COND |
| 3 | Pull-Out Pan | 37K | $0.76 | 28% | 5% | 1,965 | 4.25 | — | NO |
| 4 | Aquarium | 24.5K | $0.55 | 17% | 28% | 155 | 8.05 | 1.02 | GO* |
| 5 | Cat Desk Bed | 26K | $1.60 | 30% | 20% | 3,181 | 6.55 | 1.63 | COND |
| 6 | Hat Racks | 218K | $1.00 | 26% | 15% | 2,711 | 6.70 | 5.71 | COND |
| 7 | Kitchen Carts | 77.6K | $0.70 | 15% | 15% | 2,830 | 7.55 | 2.08 | GO |
| 8 | Dishwasher | 14.9K | $0.81 | 47% | 8% | 924 | 5.30 | 0.73 | HOLD |

注：Aquarium GO* — AI 评分 8.05 但财务 M 值仅 1.02（亏损）。评分看竞争，财务看生存。

---

## 反馈

- 提 Issue：https://github.com/zhangxinxin2323-ui/product-selector/issues
- 基于 [zach-product-research](https://github.com/zach22-1999/amazon-skills) 分析框架
