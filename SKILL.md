---
name: product-selector
description: >
  Analyze Amazon product and niche viability from an ASIN, keyword, category node,
  product link, or Feishu candidate queue. Use Sorftime evidence to perform market
  discovery, configurable Top100 attribute tagging, cross analysis, VOC, separate
  Market GO, Financial GO, and Launch Feasibility decisions, reverse unit economics,
  bundled cash-flow/scenario simulation, Feishu persistence, supplier planning,
  monitoring handoff, and decision-card/report generation. Trigger for Amazon product selection, competitor research, category
  opportunity analysis, product screening, sourcing cost ceilings, batch selection,
  or requests such as "帮我看看这个品能不能做".
---

# Product Selector

将本 Skill 当作选品决策编排器。让脚本负责确定性计算，让模型负责解释、证据归纳和需要品味的判断。

## 核心规则

0. **⛔ 报告不是检查表 — 每个章节必须有数据表格 + 关键洞察段落。** 12 章全出现但每章只有 1 句话 = 不合格。标准：竞争格局 ≥5 行品牌表格，属性标注 ≥3 维度 × 分布表格，VOC ≥1 痛点表格 + 1 映射表格，财务 ≥1 P&L 表 + 1 敏感性表。达到 Printer Stand（330 行 174 行表格）的质量线。
1. 只使用 Sorftime 返回值、用户输入和明确标注的估算值。缺失数据写”数据缺失”，不得补造。
2. 分开输出 `Market Decision`、`Financial Decision` 与 `Launch Feasibility`。市场好、单件赚钱和资金能撑到回本是三件事。
3. 未获得真实成本时仍执行反向财务测算，优先输出“采购 + 单件头程”的总落地成本上限，不能声称已验证利润。只有头程估算有来源时才派生采购价上限。
4. 默认 `dry-run`。写飞书、监控库或供应商库前先展示拟写入摘要；仅在配置允许且用户明确要求后使用 live 写入。
5. 所有正式写入执行 search-before-create/upsert，并在写入后回读关键字段。
6. 在 API 调用前估算消耗。超出 `execution.api_budget` 时停止并让用户选择快速模式或追加预算。
7. 空白组合只表示”当前样本零供给”，必须经过关键词或 VOC 需求验证后才能称为机会。
8. **⛔ 所有面向用户的输出（报告、决策卡、飞书文本字段）必须使用中文。** 字段名/API端点/Sorftime术语保留英文。
9. **⛔ 飞书百分比字段统一用 0-1 小数（0.352 = 35.2%，0.005 = 0.5%）。** 包括：搜索转化率、CVR、ClickShare、集中度、FBA占比、自营占比、新品占比、佣金率、回款率、净利率、广告空间、广告占比、退货率、ACOS参考值。CPC/售价/FBA费/利润/成本/搜索量等金额和计数类保持原值。**⛔ 财务表写入时最易犯这个错——MCP写入后必须回读一条财务记录，检查佣金率/净利率/CVR/回款率的值是否在 0-1 区间（0.15 正确，15 错误），立即修正。**
10. **⛔ 父 ASIN 检测**：ProductRequest 返回的 FBAFee ≤ 0 或 Price ≤ 0 或 IsFBA = false → 该 ASIN 是变体父体或非 FBA 商品。不得使用 $0 FBA 费做财务测算。从 CategoryRequest 的同价格段 FBA 产品估算 FBA 费，并标注"FBA 为估算值(父ASIN)"。估算规则：用类目中同价格段(±30%)的 FBA 产品 FBA 费中位数。
11. **⛔ 退货率按品类默认值**，不得一律用 5%。品类映射：Clothing/Shoes/Jewelry→15%，Electronics→5%，Home/Kitchen/Furniture→8%，Pet Supplies→8%，Sports/Outdoors→7%，Tools→5%，Office→5%，其他→5%。用户提供实际退货率时以用户为准。
12. **⛔ 财务测算的五个运营参数取值规则**：

| 参数 | 默认值 | 来源 | 可否不填 |
|------|-------|------|:--:|
| 1688采购价 | 无默认 | **用户必须提供** | ❌ |
| 头程运费 | 无默认 | **用户必须提供** | ❌ |
| CPC | 核心词CPC（市场参考值） | KeywordRequest.Cpc | ✅ 可不填，用市场CPC |
| CVR（点击转化率） | 无默认 | **Sorftime不提供，必须从广告后台填** | ❌ ⛔绝不用搜索转化率替代 |
| 退货率 | 按品类默认 | 规则11 | ✅ 可不填，用品类默认 |
| 广告订单占比 | 50%（仅用于敏感性基准） | 精铺新品的合理假设 | ✅ 不提供时输出敏感性区间 |

**逻辑**：采购价和头程无法从 CLI 推导——缺则做反向财务(reverse)。CPC默认取市场CPC。退货率按规则11。广告占比默认50%仅用于敏感性表，不单点判生死。⛔ **CVR 缺口检测**：`核心词搜索转化率`(SearchConversionRate,来自KeywordRequest) ≠ 点击CVR。用前者替代后者→adCPA偏差10-50倍→M值失实。如果用户未提供真实CVR，正向财务不得运行，只能输出反向成本上限。

13. **⛔ Financial Decision 不得基于单一广告占比默认值做出。** 必须在决策卡和报告中输出完整的 **「广告占比敏感性表」**（0-80%，每 10% 一档），标注每档的 M 值、净利率和盈利状态。让用户看到"这个产品在 ≤X% 广告时盈利、>Y% 时亏损"，自己判断自己的广告成本控制能力。

## 启动检查

1. 读取 `config.local.json`；不存在时读取 `config.example.json` 并保持 dry-run。
2. 读取 [`references/configuration.md`](references/configuration.md)。
3. 运行 `python scripts/validate_config.py <config>`，确认配置和 live 写入条件有效。
4. 确认 `python`、`node`、`sorftime` 和输出目录可用。
5. 根据运行环境读取 [`references/bitable-adapters.md`](references/bitable-adapters.md)，优先使用 builtin Feishu / MCP。
6. 为当前任务生成稳定分析键：`<domain>:<entry-type>:<normalized-entry>`。

## 模式选择

| 模式 | 适用场景 | 默认预算 |
|---|---|---:|
| quick | 只要方向判断，或预算有限 | 25 |
| full | 正式选品与产品开发 | 60 |
| deep-voc | GO/CONDITIONAL 后需要证据级 VOC | full + 评论调用 |
| batch | 飞书候选队列 | 每项单独计费，最多并行 3 |

用户未指定时使用 `full`。批量模式先输出数量、预计消耗和 dry-run 计划。

## 工作流

### Step 1：市场发现

读取 [`references/workflow-market.md`](references/workflow-market.md)，按 ASIN、关键词或类目入口采集：

- 产品基础信息与 NodeId
- 至少三个关键词维度
- 类目 Top100 与趋势
- 竞争、新品、价格和评论门槛

使用 `scripts/sorftime_call.py` 执行调用和 bounded retry。保存原始响应及来源索引，不重复调用已有数据。

### Step 2：市场可行性

基于市场规模、竞争格局、需求清晰度和进入壁垒给出 0-10 分。读取
[`references/go-nogo-scoring.md`](references/go-nogo-scoring.md)，通过
`scripts/score_go_nogo.py` 计算 `Market Decision`。

专利、合规、产品安全和供应链属于 hard gates：

- `fail`：整体不得 GO。
- `pending`：整体最多 CONDITIONAL GO。
- `pass` / `not_applicable`：不限制决策。

### Step 3：属性、交叉与 VOC

读取 [`references/attribute-tagging.md`](references/attribute-tagging.md) 和
[`references/cross-analysis.md`](references/cross-analysis.md)。

1. 有已确认品类库时，运行：

```bash
python scripts/attribute-tagger.py --input <category.json> \
  --dimensions-file references/dimensions/<category>.json \
  --output-dir <run-dir>/attributes --price-unit cents
```

2. 没有品类库时不猜维度。运行自发现，生成 `dimension-draft.json`，让用户确认或修订后再正式标注。
3. 对高价值未知记录补查 product detail；不要为所有产品重复调用。
4. quick 模式做评论摘要；deep-voc 模式读取
   [`references/review-insight-integration.md`](references/review-insight-integration.md)。

只有具备需求证据的 `scarce` 或 `high_demand_low_supply` 组合可以进入机会优先级。

### Step 4：财务可行性

读取 [`references/finance.md`](references/finance.md)。

- 缺少采购价或头程：使用内置财务包执行 `reverse`，输出盈亏平衡落地成本和目标落地成本上限；该上限是“采购 + 单件头程”的总和。仅当 `freightAssumption` 有报价或可追溯估算时再输出隐含采购价上限；Financial Decision 保持 PENDING。
- 成本齐全且只需快速判断：执行 `static`，输出单位经济、M 值、广告空间和盈亏平衡 CPC/CVR。
- 正式立项：执行 `scenario`，加入 MOQ、生产/运输周期、销量计划、固定投入和资金约束，输出月度现金流、补货、峰值资金、回本月和三情景。

```bash
node scripts/financial_model/cli.js \
  --input <run-dir>/runtime/financial-request.json \
  --output <run-dir>/raw/financial-result.json
```

生成飞书 finance dry-run payload：

```bash
python scripts/build_finance_payload.py \
  --input <run-dir>/raw/financial-result.json \
  --analysis-key <analysis-key> --domain <domain> \
  --output <run-dir>/runtime/finance-payload.json
```

不得把 Sorftime `SearchConversionRate` 当成广告点击 CVR。正式正向模型缺 CPC/CVR 时返回 `needs_input`；反向模型只有收到显式 `fallbackAdRate` 才能估算广告成本。

### Step 5：综合决策

再次运行 `scripts/score_go_nogo.py`，合并：

- Market Decision
- Financial Decision 或 PENDING
- Launch Feasibility 或 PENDING
- hard gates

| 综合状态 | 含义 |
|---|---|
| GO | 市场、财务、Launch Feasibility 和 hard gates 全部通过 |
| CONDITIONAL GO | 市场可推进，但财务、Launch 或 hard gates 尚待验证 |
| HOLD | 证据不足、经济性偏弱或资金/回本约束不满足，暂缓 |
| NO-GO | 市场、财务或硬门槛出现明确失败 |

输出决策时同时列出 Top3 机会、Top3 风险、待验证假设和下一步最小实验。

### Step 6：持久化与交付

1. 按 [`references/bitable-schema.md`](references/bitable-schema.md) 生成候选、分析和 finance 拟写入 payload；finance payload 必须来自 `build_finance_payload.py`。
2. dry-run 时只输出 payload、分析键、目标表和预期操作。
3. live 时执行 upsert 和回读验证。
4. GO/CONDITIONAL 且用户启用深度 VOC 时执行 review-insight 联动。
5. GO 且用户启用监控时读取
   [`references/monitoring-workflow.md`](references/monitoring-workflow.md)。
6. 用户要求寻源时读取 [`references/supplier-workflow.md`](references/supplier-workflow.md)。
7. 用户要求多站点比较或配置启用时读取
   [`references/cross-market-scan.md`](references/cross-market-scan.md)。
8. 生成 `decision-card.html` 和 `full-report.md`，再运行：

```bash
python scripts/report_lint.py <run-dir>/full-report.md
```

报告质量以覆盖、证据和口径为准。**⛔ lint 通过后必须再检查内容密度**：竞争章节有 ≥5 行品牌表格、属性章节有 ≥3 个维度分布表、VOC 有痛点表格+映射表、财务有完整 P&L 表+敏感性表。全章只有一句话 = 不合格。**⛔ 飞书字段必须全部出现在报告中 — 对照下面的映射表逐项检查：**

### 飞书字段 → 报告章节 映射表（⛔ 写入报告时必须全部覆盖）

| 飞书表 | 字段 | 报告章节 | 表格形式 |
|--------|------|---------|---------|
| AI分析参考 | 细分市场名称 | §1 Executive Summary | 报告标题下第一行 |
| AI分析参考 | 核心词月搜索量/CPC/搜索转化率 | §2 市场概况 | 关键词对比表(≥3行) |
| AI分析参考 | 搜索量趋势方向 | §2 市场概况 | 搜索量趋势表(≥6个时间节点) |
| AI分析参考 | 竞品总数/Top100月销额 | §2 市场概况 | 类目KPI表 |
| AI分析参考 | Top3品牌点击集中度 | §3 竞争格局 | 品牌集中度表 |
| AI分析参考 | 品牌数量/竞争热度评估 | §3 竞争格局 | Top8品牌分布表+评级 |
| AI分析参考 | 类目新品占比/新品友好度 | §3 竞争格局 | 新品分桶表(≤3mo/3-6mo/6-12mo/>1yr) |
| AI分析参考 | 平均评论门槛 | §3 竞争格局 | 评论门槛对比表 |
| AI分析参考 | FBA占比/亚马逊自营占比 | §3 竞争格局 | 卖家结构表 |
| AI分析参考 | 市场均价/市场参考售价/价格带范围 | §3 竞争格局 | 价格分布表 |
| AI分析参考 | 销量趋势方向/垄断趋势方向 | §3 竞争格局 | 趋势方向汇总表 |
| AI分析参考 | AI综合评分/AI-推荐推进 | §10 Go/No-Go | 五维评分卡+决策标签 |
| AI分析参考 | 1688采购价/头程运费 | §8 财务分析 | P&L表输入行 |
| AI分析参考 | 当前CPC/当前点击CVR | §8 财务分析 | 广告参数表 |
| AI分析参考 | AI-核心洞察 | §1 Executive Summary | 核心洞察段落(开头或末尾) |
| AI分析参考 | AI-差异化机会 | §11 产品矩阵 | 产品矩阵Tier表前 |
| AI分析参考 | AI-风险与假设 | §9 进入壁垒 | 风险+假设+置信度表 |
| 产品初筛 | 流量机会/类目垄断/点击垄断 | §3 竞争格局 | 各维度分析文本 |
| 产品初筛 | 新品机会/差异机会/价格机会 | §4-7 | 各对应章节 |
| 产品初筛 | CPC&CVR压力测试 | §8 财务分析 | 压力测试表格 |
| 产品初筛 | 利润率/初筛判定/判断依据总结 | §8/§10 | 对应位置 |
| 财务分析 | 全部48字段 | §8 财务分析 | 完整P&L表 + 广告占比敏感性表 |
| 产品开发 | 需求采集/痛点分析 | §6 VOC | 痛点表格(≥4行) |
| 产品开发 | 改良方向/切入点/人群/场景/功能/价格 | §11 产品矩阵 | Tier规格表 |


## 输出目录

使用配置中的 `execution.output_dir`：

```text
<output-dir>/<analysis-key>/<YYYYMMDD-HHMMSS>/
  raw/
  attributes/
  runtime/
  evidence-index.json
  raw/financial-result.json
  runtime/financial-request.json
  runtime/finance-payload.json
  decision.json
  decision-card.html
  full-report.md
```

每次运行创建新时间戳目录，不覆盖旧报告。更新报告时引用上一版本并保留变更说明。

## 批量模式

1. 从候选表读取待分析项，不直接写入。
2. 去重分析键，列出总项数、预算和预计耗时。
3. 每个产品独立运行；单项失败不终止整个批次。
4. 并行不超过配置值。
5. 汇总成功、失败、跳过、API 消耗和待人工输入。

## 完成检查 (⛔ 16项对照表，必须在对话末尾输出)

> 逐项核对，靠检查表不靠记忆。缺项立即补做。No-GO跳过是正确的，但要注明。

```
═══════════════════════════════════════════
  ⛔ 任务完成检查
═══════════════════════════════════════════

P1 决策:
  [ ] Market Decision
  [ ] Financial Decision（PENDING时附反向成本上限）
  [ ] Launch Feasibility（PENDING时附缺什么）
  [ ] hard gates 全有状态

P2 飞书写入:
  [ ] candidate
  [ ] ai_market_analysis（结构化+文本+反向财务字段）
  [ ] screening→GO/COND才写
  [ ] finance→仅Financial GO时写
  [ ] 每条写入已回读验证

P3 报告:
  [ ] decision-card.html
  [ ] full-report.md
  [ ] **python scripts/check_report.py --run-dir <report-dir> --overall-decision <OD> --financial-decision <FD> → exit 0 (⛔ 失败必须修)**

P4 证据:
  [ ] 原始响应已保存 raw/
  [ ] 缺失维度显式列出
  [ ] 估算标注置信度
  [ ] SearchConversionRate未写成点击CVR
═══════════════════════════════════════════
  通过: X/16  待补: Y
═══════════════════════════════════════════
```

**⛔ 此检查必须出现在分析对话末尾。不允许浓缩为”全部通过”。**

## 参考索引

- 市场采集：[`references/workflow-market.md`](references/workflow-market.md)
- 配置：[`references/configuration.md`](references/configuration.md)
- 飞书适配：[`references/bitable-adapters.md`](references/bitable-adapters.md)
- 表结构：[`references/bitable-schema.md`](references/bitable-schema.md)
- 评分：[`references/go-nogo-scoring.md`](references/go-nogo-scoring.md)
- 属性标注：[`references/attribute-tagging.md`](references/attribute-tagging.md)
- 交叉分析：[`references/cross-analysis.md`](references/cross-analysis.md)
- 财务：[`references/finance.md`](references/finance.md)
- 深度 VOC：[`references/review-insight-integration.md`](references/review-insight-integration.md)
- 监控桥接：[`references/monitoring-workflow.md`](references/monitoring-workflow.md)
- 供应商：[`references/supplier-workflow.md`](references/supplier-workflow.md)
- 跨站点：[`references/cross-market-scan.md`](references/cross-market-scan.md)
- 报告：[`references/report-contract.md`](references/report-contract.md)
- HTML 决策卡：[`references/html-report-spec.md`](references/html-report-spec.md)
