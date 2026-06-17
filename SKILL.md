---
name: product-selector
description: >
  Amazon 精铺选品分析系统：通过 Sorftime CLI 采集市场数据，执行多维度属性标注、交叉分析、Go/No-Go 评分，
  写入飞书多维表格并输出 MD + HTML 报告。支持 ASIN / 关键词 / 类目三种入口。
  触发词：分析产品、选品、给 ASIN、查类目市场、分析关键词、帮我看看这个品、
  产品初选、初筛、财务测算、批量选品、竞品分析、1688 找货源、
  B0 开头的 ASIN、Amazon 链接、关键词分析市场。
  即使用户只说"帮我看看 XXX"，只要涉及 Amazon 产品/市场可行性判断，就应触发。
---

# Product Selector — Amazon 精铺选品系统

## 定位

融合 **市场调研深度**（属性标注 + 交叉分析 + Go/No-Go）与 **运营效率**（飞书表格 + CLI 稳定性 + 批量能力）的一体化选品系统。

## 工作原理

```
入口（ASIN / 关键词 / 类目）
    ↓
Step 1: 市场发现 → AI分析参考写入+自检
    ↓ ⛔ 💰成本弹窗（不可跳过）
    ↓ [用户给成本 or 跳过]
    ↓
Step 2: 产品初筛（GO/CONDITIONAL GO 自动触发）
    ↓
Step 3: 属性标注 + 交叉分析
    ↓
Step 4: 财务分析（成本有值自动执行）
    ↓
Step 5: 产品开发（GO/CONDITIONAL GO 自动触发）
    ↓
Step 6: 输出报告（MD + HTML）+ 流程完整性检查
```

## 前置条件

- `sorftime` CLI — `sorftime whoami` 验证
- `lark-cli` — `lark-cli auth status` 验证
- 飞书表：App Token `LgO2bmmgnabbylsaJtTc4gt9n2c`，6 张表（详见 [`references/bitable-schema.md`](references/bitable-schema.md)）

**站点 domain**：US=1, GB=2, DE=3, FR=4, IT=5, ES=6, JP=7, MX=8, AU=9, AE=10, BR=11, CA=12。默认 US。

---

## Step 0: 信息收集

收到调用后，确认：
1. **目标站点**：默认 US
2. **入口类型**：ASIN / 关键词 / 类目 nodeId
3. **选品模式**：精铺偏铺 / 精铺偏精
4. **约束条件**（可选）：价格区间、月销量、预算

如果用户直接给了 ASIN 或关键词，跳过询问，直接开始。

---

## Step 1: 市场发现

### 1.1 类目定位

**从 ASIN 入口**：
```bash
sorftime api ProductRequest '{"asin":"<ASIN>","trend":2}' --domain <D>
```
提取：品牌、售价、评分、评论数、月销、FBA费、佣金、**BsrCategory[0][1]（NodeId）**

**从关键词入口**：
```bash
sorftime api ASINRequestKeywordv2 '{"asin":"<从搜索结果取Top ASIN>","pageSize":20}' --domain <D>
sorftime api CategoryRequest '{"nodeId":"<从ProductRequest取>"}' --domain <D>
```

**从类目入口**：直接使用用户提供的 nodeId。

### 1.2 关键词多维分析（⛔ 至少 3 维度）

对核心词执行多维度对比，不得只分析单一关键词：

```bash
sorftime api KeywordRequest '{"keyword":"<品类大词>"}' --domain <D>
sorftime api KeywordRequest '{"keyword":"<属性词>"}' --domain <D>
sorftime api KeywordRequest '{"keyword":"<场景词/规格词>"}' --domain <D>
sorftime api KeywordExtends '{"keyword":"<核心词>","pageSize":20}' --domain <D>
```

**输出关键词对比表**：

| 关键词 | 维度 | 月搜索量 | CPC | 转化率 | 竞争产品数 | Top3品牌 | 数据来源 |
|--------|------|----------|-----|--------|-----------|----------|----------|
| xxx | 品类大词 | ... | ... | ... | ... | ... | KeywordRequest |
| yyy | 属性词 | ... | ... | ... | ... | ... | KeywordRequest |
| zzz | 场景词 | ... | ... | ... | ... | ... | KeywordRequest |

**检查点**：至少 3 个维度的关键词都有 KeywordRequest 数据后，进入 Step 1.3。

### 1.3 类目趋势

```bash
sorftime api CategoryTrend '{"nodeId":"<N>","trendIndex":0}' --domain <D>   # 销量趋势
sorftime api CategoryTrend '{"nodeId":"<N>","trendIndex":3}' --domain <D>   # 价格趋势
sorftime api CategoryTrend '{"nodeId":"<N>","trendIndex":28}' --domain <D>  # Top3垄断趋势
```

### 1.4 写入飞书（产品初选表）

使用 MCP `bitable_v1_appTableRecord_create`（lark-cli 无单条 create）：
```
table_id: tbljJBWDxaLerJsN
fields: {产品名称, 产品链接/ASIN/来源, 核心关键词, 类目, 价格带, 推进状态:"待分析", 发现日期}
```

**→ 输出初印象（1-2句话），等用户确认继续**

### 1.5 写入飞书（AI分析参考表）⛔ 必写

在 Step 1 数据采集完成后，**必须**写入 AI分析参考表。该表以**细分市场**为分析单元。

**21 个结构化字段**（必填，按组写入）：

| 组 | 字段 | 来源端点 | 示例值 |
|----|------|---------|--------|
| 标识 | 细分市场名称、关联初选、分析日期、AI-推荐推进 | AI定义 | "Printer Stands" |
| 流量 | 核心词月搜索量、核心词CPC、搜索转化率、搜索量趋势方向、竞品总数、Top100月销额 | KeywordRequest | 98547 / 0.65 |
| 竞争 | Top3品牌点击集中度、品牌数量、竞争热度评估、类目新品占比、平均评论门槛、FBA占比、新品友好度 | CategoryRequest+KeywordRequest | 24% / 45个 |
| 趋势 | 市场均价、价格带范围、销量趋势方向 | CategoryRequest+CategoryTrend | $56.82 |
| AI | AI综合评分、AI-核心洞察、AI-差异化机会、AI-风险与假设 | AI综合分析 | 6.95 / 200字 |
| 历史(必写) | AI建议总览、AI-趋势、AI-竞争、AI-关键词流量、AI-评论VOC、AI-利润测算、AI-市场分析 | 同上数据分别填充 | 各 100-200 字 |

写入使用 MCP `bitable_v1_appTableRecord_create`，table_id: `tblMeN1P5LvXsp2e`。

⛔ **必须同时写入新旧两组文本字段**。历史 8 个字段虽然标注"历史兼容"但不能空——它们是飞书视图中长期沉淀的对比分析基础。

**⛔ 写入后立即自检**：回读刚写入的记录（`bitable_v1_appTableRecord_search`），验证以上 29 个字段全部非空。缺值立即补填。通过后才算 Step 1 完成。

### 1.6 自动分流 ⛔

自检通过后，根据 AI-推荐推进**自动决定下一步**：

| AI-推荐推进 | 动作 |
|-------------|------|
| **GO-推荐进入** | → 自动进入 Step 2（产品初筛）→ Step 3（属性标注+交叉）→ Step 4（财务分析） |
| **CONDITIONAL GO-有条件** | → 进入 Step 2（产品初筛），标记待确认项，提示用户补充后进入 Step 4 |
| **HOLD-暂缓** | → 停止，输出 MD+HTML 报告，提示需要更多数据 |
| **NO-GO-放弃** | → 停止，输出 MD+HTML 报告，记录放弃原因 |

**只在 GO/CONDITIONAL GO 时才继续推进，不浪费 API 和用户时间。**

产品初筛（Step 2）写入飞书后，等待用户确认是否进入财务分析（需要用户提供 1688 采购价 + 头程运费）。

---

## Step 2: 产品初筛（自动触发）⛔

> GO/CONDITIONAL GO 时自动执行。AI 填写 11/16 分析维度，标记 5 个待人工确认维度。

| 维度 | 自动化 | 数据来源 | 写入格式 |
|------|:---:|------|------|
| 流量机会 | ✅ | KeywordRequest + KeywordExtends 搜索量汇总 | 文本：搜索量+趋势判断 |
| 类目垄断 | ✅ | CategoryRequest Top10/Top3 品牌卖集中度% | 文本：具体% + 判断 |
| 关键词点击垄断 | ✅ | KeywordSearchResults Top3 ASIN 点击占比 | 文本：% 值 |
| 新品机会 | ✅ | CategoryRequest OnlineDays ≤90天+Review<100 | 文本：数量+占比 |
| 差异机会 | ✅ | Step 3 交叉分析空白/薄供给输出 | 文本：具体空白组合 |
| 价格机会 | ✅ | CategoryRequest 价格分桶分布 | 文本：各段占比 |
| 对标竞品 | ✅ | Top5 ASIN ProductRequest + Reviews | 文本：ASIN+特点 |
| CPC&CVR 压力测试 | ✅ | KeywordRequest CPC × 三种场景 | 文本：3场景利润 |
| 利润率 | 🟡 | 估算（缺1688成本）标注假设 | 文本：估算+标注 |
| 差异点设计 | ✅ | VOC 痛点→优势映射 | 文本：4方向 |
| 初筛判定 | ✅ | 11维度通过/未通过计数+Go/No-Go | Select |
| 专利风险 | ❌ | ⚠️ 标记"待人工确认" | 标记 |
| 合规认证 | ❌ | ⚠️ 标记"待人工确认" | 标记 |
| 供应链可测 | ❌ | ⚠️ 标记"待人工确认" | 标记 |
| 判断依据总结 | ✅ | AI 综合 | 200字 |

### 2.2 数据采集（如尚未采集）

类目Top100、差评、搜索结果等数据如果在 Step 1 已采集，直接复用，不再重复调用 API。

```bash
# 仅当需要补充时调用
sorftime api KeywordSearchResults '{"keyword":"<核心词>","pageSize":50}' --domain <D>
sorftime api ASINKeywordRanking '{"keyword":"<核心词>","ASIN":"<参考ASIN>"}' --domain <D>
```

### 2.3 写入飞书（产品初筛表）

```bash
mcp__lark-mcp__bitable_v1_appTableRecord_create
  table_id: tblPhc8dHOelKPPF
  fields: {
    初筛日期, 产品初选(Link), 目标月销量,
    流量机会, 类目垄断, 核心关键词点击转化垄断性, 新品机会,
    差异机会, 价格机会, 对标竞品, CPC & CVR 压力测试,
    利润率, 专利风险:"⚠️ 待人工确认", 合规认证:"⚠️ 待人工确认",
    供应链可测分析:"⚠️ 待人工确认", 差异点设计,
    初筛判定, 判断依据总结, 关联AI分析
  }
```

### 2.4 等待用户动作

**→ 汇报初筛结果，提示用户需要补充的 3-5 个字段**
**→ 如果用户提供了 1688 采购价 + 头程运费 → 进入 Step 4（财务分析）**

---

## Step 3: 属性标注 + 交叉分析

> 详细方法论见 [`references/attribute-tagging.md`](references/attribute-tagging.md) 和 [`references/cross-analysis.md`](references/cross-analysis.md)

### 3.1 维度自发现

4 路并行发现品类关键维度：
1. Top100 标题高频词聚类（出现率 ≥10%）
2. KeywordExtends 延伸词分析
3. Top5 产品 product_detail 属性 Key
4. WebSearch 品类评测文章（可选）

输出 5-8 个候选维度，**让用户确认后**进入标注。

### 3.2 Top100 属性标注

**一键执行**（推荐）：
```bash
cat top100_raw.json | tail -n +3 | python <SKILL_DIR>/scripts/attribute-tagger.py --output-dir <OUT_DIR>
```
替代之前的手工 `python -c "..."` 临时脚本。输出：
- 属性分布表（每个维度的主力段+占比）
- 交叉分析矩阵（3对维度组合）
- 新品率/价格/评论/品牌聚合
- `top100_parsed.json` / `attribute_dims.json` / `cross_analysis.json`

对于标题覆盖不到的 20-30% 产品，调 `product_detail`（每批 ≤8 并行）验证。

**也可以使用 `D:\sorftime-cli\scripts\sf-extract.py`** 做基础字段提取（ASIN/品牌/价格/销量）。

### 3.3 交叉分析

对所有有意义的维度对生成交叉矩阵，识别：
- **空白**（产品数=0）→ 潜在蓝海
- **薄供给**（产品数≤2）→ 低竞争机会
- **高需求低供给** → 最优机会

⛔ 每个空白/薄供给标签必须附原因分析（技术限制？需求不存在？被忽视？）

### 3.4 痛点→优势映射

对每个属性维度的差评执行四要素映射：

| 维度 | 痛点描述 | 数据支撑 | 品牌机会 | 产品方案 |
|------|----------|----------|----------|----------|
| [维度1] | [高频不满] | [X%差评提及] | [能力优势] | [具体设计] |

---

## Step 4: 财务分析 — 半自动 P&L

> 触发条件：Step 2 初筛完成 + 用户提供 1688 采购价 + 头程运费。
> 用户只需给 2 个数字，AI 自动算完 48 字段。

### 4.1 输入

| 来源 | 数据 | 方式 |
|------|------|:--:|
| ProductRequest | 售价、FBA费、佣金率、Sorftime估算利润 | ✅ 自动 |
| KeywordRequest | 市场CPC、CVR参考值 | ✅ 自动 |
| **用户提供** | 1688采购价、头程运费 | ❌ **必须人工** |
| AI 估算 | 广告占比(默认60%)、退货率(默认5%)、仓储费 | 🟡 可调 |

### 4.2 自动计算公式

落地成本 = 产品成本 + 头程运费
理论回款率 = (售价 − FBA费 − 佣金 − 仓储费) ÷ 售价
真实回款率 = (售价 − FBA − 佣金 − 仓储 − 广告 − 退货退款) ÷ 售价
净利率 = 单件净利润 ÷ 售价
M 值 = 实际回款金额 ÷ 落地成本
广告空间 = (售价 − 落地成本 − FBA − 佣金 − 仓储) ÷ 售价
盈亏平衡 CPC = (到手收入 − 落地成本 − 退货退款 − 仓储费) × CVR ÷ 广告占比

**评级标准**：理论回款率>65%=优秀，M值>2.5=优秀，广告空间>40%=非常优秀

### 4.3 写入飞书（财务分析表）

```bash
mcp__lark-mcp__bitable_v1_appTableRecord_create
  table_id: tblllu3JJYrG5KGE
  fields: {
    测算日期, 关联初选, 关联初筛, 竞品ASIN-1/2/3,
    售价, 产品成本, 头程运费, 落地成本, FBA费, 佣金率,
    理论回款率, 理论回款率评级,
    真实回款率, 真实回款率评级,
    净利率, 净利率评级,
    M值, M值评级,
    广告空间, 广告空间评级,
    单件净利润, 盈亏平衡CPC, 当前CPC, 当前CVR,
    市场CPC, 市场CVR参考值, ACOS参考值,
    首批数量, 首批投入, 峰值投入,
    回本月份, 首次盈利月份,
    盈利前补货次数, 总补货次数,
    12月总销量, 12月总收入, 12月总广告费, 12月累计利润, 12月末现金流
  }
```

**⛔ 成本为估算时不写入**（标记"待用户确认成本"）。用户提供真实成本后才写入。

---

## Step 5: 产品开发 — 独立触发

> 基于细分市场的产品开发建议。**不依赖特定 ASIN**，可在 AI分析参考之后的任何阶段独立触发。
> 输入：细分市场名称 + VOC 分析 + 交叉分析空白

### 5.1 CLI 可自动填写的维度（12/18）

| 字段 | 数据来源 | 方式 |
|------|---------|:--:|
| 需求采集 | ProductReviewsQuery 差评 + KeywordExtends | ✅ 多选 |
| 需求&痛点分析 | VOC 四要素映射表 | ✅ |
| 产品改良方向 | 交叉分析空白 × 痛点匹配 → 8 种差异化类型 | ✅ |
| 改良切入点 | 痛点→方案映射 | ✅ |
| 新人群定位 | KeywordExtends 中的人群修饰词分析 | ✅ |
| 新场景定位 | KeywordExtends 中的场景词分析 | ✅ |
| 新功能定位 | 差评痛点反推 + 空白供给组合 | ✅ |
| 新价格定位 | 价格带分布 + 空白价格段 | ✅ |
| 成本&供应商评估 | ❌ 需 1688 | 标记待确认 |
| 开发状态 | 手动决策 | "调研中" |
| 负责人 | 手动指定 | — |
| 预计完成 | 手动指定 | — |

### 5.2 触发方式

用户说"开发这个市场"或 AI分析参考 GO 后自动提示：
> "该细分市场的差异化为：[方向]。是否需要生成产品开发建议？"

### 5.3 写入飞书（产品开发表）

```bash
mcp__lark-mcp__bitable_v1_appTableRecord_create
  table_id: tbl3dtXNC3Emy38k
  fields: {
    开发日期, 关联初选, 需求采集, 需求&痛点分析,
    产品改良方向, 改良切入点, 新人群定位, 新场景定位,
    新功能定位, 新价格定位, 成本&供应商评估:"待1688确认",
    开发状态:"调研中", 关联初筛, 关联AI分析
  }
```

---

## Step 6: 输出报告

### 6.1 写入飞书表（汇总）

按流程逐表写入（使用 MCP `bitable_v1_appTableRecord_create`）：

| 表 | 时机 | table_id |
|----|------|----------|
| 产品初选 | Step 1 完成 | tbljJBWDxaLerJsN |
| **AI分析参考** | **Step 1 完成（⛔ 必写）** | **tblMeN1P5LvXsp2e** |
| **产品初筛** | **Step 1 GO/CONDITIONAL GO → Step 2 自动触发** | **tblPhc8dHOelKPPF** |
| 财务分析 | 用户提供 1688 采购价 + 头程后 | tblllu3JJYrG5KGE |
| 产品开发 | 任何阶段独立触发 | tbl3dtXNC3Emy38k |
| 供应商管理 | 用户提供 1688 信息后 | tblu1Q70vnmsiBZ5 |

⛔ **AI分析参考每次必写**。产品初筛 GO/CONDITIONAL GO 自动触发。财务分析需精确成本。

### 6.1a 流程完整性检查（⛔ 必须放在任务末尾执行）

> **这是防漏机制。每次分析对话结束前，必须执行此检查并汇报结果。不能靠记忆——必须逐条核对。**

#### 6.1a-P1: 飞书遍写检查

| # | 表 | 触发条件 | 写了吗 |
|---|----|---------|:--:|
| 1 | 产品初选 | 永远 | |
| 2 | AI分析参考 | 永远 | |
| 3 | 产品初筛 | GO / CONDITIONAL GO | |
| 4 | 产品开发 | GO / CONDITIONAL GO | |
| 5 | 财务分析 | GO/CONDITIONAL + 用户给了 1688 成本 | |
| 6 | 供应商管理 | 用户给了 1688 链接 | |

#### 6.1a-P2: 报告文件检查

| # | 文件 | 触发条件 | 写了吗 |
|---|------|---------|:--:|
| 1 | decision-card.html | 永远 | |
| 2 | full-report.md | GO / CONDITIONAL GO | |

#### 6.1a-P3: 运营数据强制弹窗（⛔ 不可跳过）

> **在 Step 1（AI分析参考写入+自检）完成后，必须立即输出以下弹窗。**

```
┌─────────────────────────────────────────────────┐
│           📊 运营数据输入 — 5个字段               │
├─────────────────────────────────────────────────┤
│                                                 │
│  当前分析: <细分市场名称>                         │
│  参考售价: $<ASIN售价>                           │
│  Sorftime利润: $<ProfitRate>                    │
│                                                 │
│  📝 请输入运营数据（Sorftime无法自动获取）：      │
│                                                 │
│  1. 1688采购价:   $___   (成本决定M值)           │
│  2. 头程运费:     $___   (海运/空运/件)          │
│  3. 当前CPC:      $___   (广告后台实际CPC)        │
│  4. 当前点击CVR:  ___%   (广告点击→购买转化率)    │
│  5. 广告订单占比: ___%   (默认60%)              │
│                                                 │
│  💡 飞书表里手动填，或直接打字告诉我              │
│  💡 5个字段全有值 → 自动触发Step 4财务分析       │
│  💡 CPC可从KeywordRequest获取市场参考值          │
│  💡 点击CVR Sorftime不提供，必须你自己填          │
│                                                 │
└─────────────────────────────────────────────────┘
```

**⛔ 禁止在弹窗出现前输出决策卡或完整报告。**
**⚠️ Sorftime CLI+MCP 共11端点均不提供点击CVR——永远需要人工填写。**

#### 6.1a-P4: 成本输入方式 + 自动触发

**AI分析参考表有 4 个必须由用户填写的运营字段**：
- `1688采购价` / `头程运费` — 成本，决定 M 值
- `当前CPC` / `当前点击CVR` — 广告效率，决定盈亏平衡
- `广告订单占比` — 可选（默认 60%）
⚠️ `当前点击CVR` Sorftime 不提供（CLI+MCP 共 11 端点均无），100% 依赖用户填写。

**⛔ 4 个字段全有值（+广告占比默认 60%），立即触发 Step 4 财务分析。不需要用户说”进入”。**

#### 6.1a-P5: 自检回读验证

写入**任何**表后，回读验证关键字段非空。包含新增的运营数据字段组：

```
[运营组] 1688采购价、头程运费、当前CPC、当前点击CVR（4个全有=Step 4触发）
```

全部通过后才算完成。

### 6.2 输出报告（⛔ 决策卡 + 完整报告）

**文件路径**：`~/product-selector-reports/<关键词或ASIN>-<YYYYMMDD>/`

| 文件 | 格式 | 用途 | 长度 |
|------|------|------|------|
| **decision-card.html** | HTML | 半屏速判：KPI卡片+痛点评分+决策+风险，手机可看可分享 | ≤2屏 |
| **full-report.md** | Markdown | ≥10 章完整分析，电脑上细读回溯 | **≥250行** |

#### 6.2a 报告输出前自检（⛔ 未通过 = 禁止输出）

报告文件写入前，逐项检查：

```
[ ] 飞书 AI分析参考表 29+ 字段全量回读了？ → 所有数字来源有据
[ ] 报告章节 ≥ 10 章？
[ ] 19 项三端对齐表(6.3a) 逐项出现在报告中？
[ ] 所有数字有 CLI 来源标注(ProductRequest/KeywordRequest/CategoryRequest/CategoryTrend)？
[ ] 估算值标注了"估"和置信度？
[ ] 无编造数字？(检查:是否有任何数字找不到CLI来源)
```

**6 项全部通过才允许输出报告文件。**

#### decision-card.html 结构

```
┌─ Header: 细分市场名 + 决策标签(绿/橙/红) + 评分
├─ KPI 网格 (8卡片): 搜索量/CPC/CVR/新品率/评论门槛/均价/集中度/趋势
├─ 关键发现 (3-5 bullet)
├─ 风险+缓解 (2-3条)
├─ 下一步行动
└─ Footer: 数据来源 + 报告路径
```

颜色驱动：评分≥7.5=绿(GO)，6-7.4=橙(CONDITIONAL)，<6=红(NO-GO/HOLD)

#### full-report.md 结构（12 章）
1. Executive Summary（数据点→含义→行动）
2. 市场概况（KPI + 关键词多维对比 + 趋势）
3. 竞争格局（品牌集中度 + Top100 + 新品分析）
4. 属性维度分布（主力段/占比 + 关键洞察）
5. 交叉分析（矩阵 + 空白/薄供给 + 关键发现）
6. 消费者 VOC（按维度归类 + 痛点→优势映射）
7. 供需缺口与机会（优先级排序）
8. 财务测算（P&L + 压力测试 + 假设置信度）
9. 进入壁垒（6 类壁垒表）
10. Go/No-Go 评分卡
11. 产品矩阵建议（Tier 1+ 规格表）
12. 原始数据索引（API 消耗 + 飞书记录 ID）

### 6.3 报告硬性规则（⛔ 不可省略）

> 以下规则确保每份报告达到 ZPR 标准的分析深度，同时与飞书表字段一一对应。

#### 6.3a 飞书-ZPR-报告 三端对齐表（⛔ 输出前逐项对照）

| # | 飞书表字段（必须出现） | ZPR 要求维度 | full-report.md 对应章节 | CLI 数据源 |
|---|----------------------|-------------|----------------------|-----------|
| 1 | 细分市场名称 | 市场标识 | §1 产品/市场基础信息 | ProductRequest + CategoryRequest |
| 2 | 核心词月搜索量/CPC/搜索转化率/搜索量趋势方向/竞品总数 | 关键词多维对比(≥3维度) | §2 关键词分析 | KeywordRequest ×3 |
| 3 | Top3品牌点击集中度/品牌数量/竞争热度评估 | 品牌集中度+竞品格局 | §3.1 品牌集中度 | KeywordRequest + CategoryRequest |
| 4 | 类目新品占比/新品友好度/平均评论门槛 | 新品分析(时间分桶) | §3.3 新品分析 | CategoryRequest.OnlineDays |
| 5 | FBA占比/亚马逊自营占比 | 卖家结构分析 | §3 竞争格局 | CategoryRequest聚合 |
| 6 | 市场均价/市场参考售价/价格带范围 | 价格带分布 | §3.4 价格分布 | CategoryRequest.Price |
| 7 | 销量趋势方向/垄断趋势方向 | 类目趋势 | §2.3 趋势分析 | CategoryTrend(0,28) |
| 8 | **属性标注(新增)** | ZPR §1.5 Top100属性标注 | §4.1 维度分布表 | CategoryRequest标题解析 |
| 9 | **交叉分析(新增)** | ZPR §1.6 交叉矩阵 + 空白/薄供给 | §4.2 交叉分析矩阵 | Python解析Top100 |
| 10 | — | ZPR VOC差评按维度归类 | §5.2-5.3 差评痛点+映射 | ProductReviewsQuery |
| 11 | **痛点→方案映射(新增)** | ZPR 四要素映射 | §5.4 痛点→优势映射 | AI分析 |
| 12 | **供需缺口优先级(新增)** | ZPR 三维加权排序 | §6 供需缺口与机会 | 交叉分析结果 |
| 13 | AI-推荐推进/AI综合评分 | ZPR Go/No-Go评分卡 | §8 Go/No-Go评分卡 | 5维加权计算 |
| 14 | — | ZPR 进入壁垒(6类) | §7 进入壁垒评估 | 综合判断 |
| 15 | — | ZPR 产品矩阵(Tier1+) | §9 产品矩阵建议 | VOC+交叉分析 |
| 16 | 1688采购价/头程运费 | — | §6 财务测算 | 用户提供 |
| 17 | AI-核心洞察 | Executive Summary | 报告开头 | 全数据综合 |
| 18 | AI-差异化机会 | 差异化建议 | §9 产品矩阵 | VOC映射 |
| 19 | AI-风险与假设 | 风险提示 | §7 风险+缓解 | 综合判断 |

⛔ **以上 19 项必须全部出现在 full-report.md 中。对照表就是自检清单。缺一项 = 报告不合格，禁止输出。**

#### 6.3b 报告行数门槛

9. ⛔ **full-report.md 必须 ≥ 250 行** — 低于此门槛说明漏了章节
10. ⛔ **decision-card.html 必须 ≤ 2 屏** — 只做速判，不做完整分析
11. ⛔ **写完报告后回读检查**：grep 检查 `§1\|§2\|§3\|§4\|§5\|§6\|§7\|§8\|§9` 是否全部出现
12. ⛔ **如果财务分析已完成但报告无财务章节**，必须重写报告补充

#### 6.3c 数据诚信规则（⛔ 一票否决）

13. ⛔ **所有数字必须来自 Sorftime CLI 实测数据或用户在飞书填写的成本**
14. ⛔ **禁止编造任何数据** — 包括但不限于：搜索量、CPC、CVR、价格、评论数、销量、利润率
15. ⛔ **每个数据点标注来源**（ProductRequest / KeywordRequest / CategoryRequest / 用户提供）
16. ⛔ **估算值必须标注"估"和置信度** — 不能把估算伪装成实测
17. ⛔ **CLI 无返回的字段不得编造** — 如遇数据缺失，标注"数据缺失：<字段名>"而非编造数字

---

## 批量模式

```bash
# 查询待分析记录
lark-cli base +record-search --base-token LgO2bmmgnabbylsaJtTc4gt9n2c \
  --table-id tbljJBWDxaLerJsN \
  --filter '{"conjunction":"and","conditions":[{"field_name":"推进状态","operator":"is","value":["待分析"]}]}' \
  --page-size 20
```
逐个执行 Step 1-2（并行 2-3 个，避免限流），汇总输出批量报告。

---

## Sorftime CLI 端点速查

| 端点 | 消耗 | 用途 |
|------|------|------|
| ProductRequest | 1 | 产品详情（含NodeId、FBA费、佣金） |
| ASINRequestKeywordv2 | 1 | ASIN反查关键词 |
| KeywordRequest | 1 | 关键词详情（搜索量/CPC/转化率/Top3品牌） |
| KeywordExtends | 5 | 延伸关键词 |
| CategoryRequest | 5 | 类目Top100产品 |
| CategoryTrend | 5 | 类目趋势（trendIndex: 0=销量, 3=价格, 28=Top3垄断） |
| KeywordSearchResults | 5 | 关键词搜索结果产品 |
| ASINKeywordRanking | 2 | ASIN在关键词下排名 |
| ProductReviewsQuery | 5 | 产品评论（star:10=消极, 11=积极） |
| ProductReviewsCollection | 积分 | 触发实时评论采集 |
| ProductReviewsCollectionStatusQuery | 0 | 采集状态查询 |

**单产品完整流程**：~120 requests（含属性标注+交叉分析）
**快速筛选流程**（仅 Step 1-2）：~47 requests

## Bundled Scripts

| 脚本 | 用途 | 用法 |
|------|------|------|
| `scripts/attribute-tagger.py` | Top100 属性标注 + 交叉分析 | `tail -n +3 top100.json \| python <脚本> --output-dir .` |
| `D:\sorftime-cli\scripts\sf-extract.py` | 从 JSON 提取 ASIN/品牌/价格等字段 | `sorftime api ... \| python sf-extract.py --asins --top 10` |
| `D:\sorftime-cli\scripts\sf-pick.py` | 一键选品(类目→Top ASIN→详情→关键词) | `python sf-pick.py --node-id <N> --domain 1 --top 5` |

---

## 常见失败处理

| 问题 | 处理 |
|------|------|
| Sorftime Code=4 积分不足 | 提醒充值，先用已有数据分析 |
| Code=97 ASIN不存在 | 检查ASIN |
| Code=99 正在抓取 | 等5分钟重试 |
| lark-cli 认证失败 | `lark-cli auth login` |
| 评论未缓存 | 先 ProductReviewsCollection，查状态后再 Query |
| NodeId 获取失败 | 检查 BsrCategory[0][1] 是否存在 |
| Top100 不足100条 | 说明原因，用现有数据分析 |
