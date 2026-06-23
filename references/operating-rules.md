# Fixed Operating Rules

Read this file before financial analysis or live persistence. These thresholds are
part of the decision contract, not optional guidance. ALL deterministic mappings
between measurable data and Feishu select fields are defined here and nowhere else.

---

## Evidence and Missing Data

- Missing values remain missing. Do not infer facts from unrelated metrics.
- Label values as `measured`, `user_provided`, or `estimated` with an evidence ID.
- `SearchConversionRate` is **not** advertising click CVR.
- Unknown Sorftime endpoint cost blocks live execution.
- Zero supply without independent demand evidence is `blank_unvalidated`.

## Parent ASIN

Treat a product as a likely parent or non-FBA ASIN when any condition is true:
- `FBAFee <= 0`
- `Price <= 0`
- `IsFBA = false`

Do not use $0 FBA fee in finance. Estimate from median FBA products within ±30%
of target price, labeled `estimated_parent_asin`.

## Return Rate Defaults

Use user-provided actuals first. Otherwise use:

| Category | Default |
|---|---:|
| Clothing, Shoes, Jewelry | 15% |
| Electronics | 5% |
| Home, Kitchen, Furniture | 8% |
| Pet Supplies | 8% |
| Sports, Outdoors | 7% |
| Tools | 5% |
| Office | 5% |
| Other | 5% |

## Financial Inputs

| Input | Rule when missing |
|---|---|
| Product cost | Run reverse finance; Financial Decision = PENDING |
| Freight | Run reverse landed-cost ceiling; do not derive product-cost ceiling |
| CPC | May use measured core-keyword CPC |
| Click CVR | Required for forward finance; never substitute search conversion |
| Return rate | Use category default above |
| Ad-order share | Use only for sensitivity, not a single-point final decision |

Financial GO requires: M ≥ 2.0 AND net margin ≥ 15%.
Always show ad-order share 0-80% in 10-point increments with M, net margin, profit.

## Decision Layers

- Hard gate `fail` → Overall = NO-GO.
- Hard gate `pending` → Overall max = CONDITIONAL GO.
- Missing Financial Decision or Launch Feasibility → Overall cannot be GO.
- Peak capital > available capital → HOLD.
- Payback beyond configured max → HOLD.

## Three-Layer Decision → AI-推荐推进 (ai_market_analysis)

This is the definitive mapping that drives the Feishu push workflow.
Must match ai_market_analysis field options exactly.

Valid options (6): GO-推荐进入, CONDITIONAL GO-有条件, HOLD-暂缓, NO-GO-放弃, 建议初筛, 需更多数据

| Market | Financial | Launch | Hard Gates | AI-推荐推进 |
|:---:|:---:|:---:|:---:|---|
| GO | GO | GO | all pass | **GO-推荐进入** |
| GO | COND | PENDING | pass/pending | **CONDITIONAL GO-有条件** |
| COND | GO | PENDING | pass/pending | **CONDITIONAL GO-有条件** |
| COND | PENDING | NOT_RUN | pass | **建议初筛** |
| COND | HOLD | PENDING | pass | **HOLD-暂缓** |
| HOLD | PENDING | NOT_RUN | pass | **需更多数据** |
| Any | NO-GO | Any | Any | **NO-GO-放弃** |
| Any | Any | Any | fail | **NO-GO-放弃** |

"待定" is FORBIDDEN — removed from field options 2026-06-23.

## 6-Table Feishu Push Logic

| # | Table | table_id | Write Condition |
|---|------|----------|:--:|
| 1 | 产品初选 | tbljJBWDxaLerJsN | **Always** |
| 2 | AI分析参考 | tblMeN1P5LvXsp2e | **Always** |
| 3 | 产品初筛 | tblPhc8dHOelKPPF | Overall GO or CONDITIONAL |
| 4 | 财务分析 | tblllu3JJYrG5KGE | **Financial GO only** |
| 5 | 产品开发 | tbl3dtXNC3Emy38k | Overall GO or CONDITIONAL |
| 6 | 供应商管理 | tblu1Q70vnmsiBZ5 | Manual (user provides 1688 link) |

- Tables 1+2 always written, even for NO-GO (data preservation).
- Table 4 written only when Financial Decision = GO. COND/HOLD/NO-GO → skip.
- Tables 3+5 triggered in parallel (both depend on Overall, not on each other).
- NO-GO/HOLD skipping downstream tables is correct behavior, not a bug.

## Human-Only Fields (MUST NOT be written by AI)

| Table | Field | Reason |
|---|---|---|
| product_candidates | 产品定位 | Human selects positioning strategy |
| product_candidates | 定位理由 | Human explains positioning rationale |
| product_candidates | 选品人 | Auto-filled by Feishu (user field) |
| product_candidates | 判定人 | Auto-filled by Feishu (user field) |
| ai_market_analysis | 最终决策 | Post-decision manual review field |
| ai_market_analysis | 实际上线时间 | Manual after launch |
| ai_market_analysis | 6个月后状态 | Manual 6mo post-launch |
| ai_market_analysis | 决策复盘 | Manual retrospective |

## Link Fields (MUST be written by AI)

| Table | Link Field | Links To |
|---|---|---|
| ai_market_analysis | 关联初选 | product_candidates record_id |
| finance | 关联初选 | product_candidates record_id |
| product_screening | 关联初选, 关联AI分析 | candidate + ai_analysis record_ids |
| product_development | 关联初选, 关联初筛, 关联财务, 关联AI分析 | upstream record_ids |

After creating a candidate record, capture `record_id`. Pass it to every downstream
table write. Read back each link field to verify it resolved.

---

## Deterministic Select Field Mappings

All Feishu select fields have fixed options. Below are the ONLY valid values
and their deterministic mapping from Sorftime CLI data.

### 竞争热度评估 — from Top3 ClickShare (KeywordRequest.ShareClickRate)

Valid options (5): 蓝海(垄断<20%), 分散(20-40%), 中等(40-60%), 集中(60-80%), 垄断(>80%)

| ClickShare | Value |
|---|---|
| < 0.20 | 蓝海(垄断<20%) |
| 0.20 - 0.40 | 分散(20-40%) |
| 0.40 - 0.60 | 中等(40-60%) |
| 0.60 - 0.80 | 集中(60-80%) |
| > 0.80 | 垄断(>80%) |

### 新品友好度 — from 类目新品占比 (CategoryRequest ≤6mo bucket)

Valid options (4): 友好(>15%), 中等(10-15%), 困难(5-10%), 非常困难(<5%)

| 新品占比 | Value |
|---|---|
| ≥ 0.15 | 友好(>15%) |
| 0.10 - 0.15 | 中等(10-15%) |
| 0.05 - 0.10 | 困难(5-10%) |
| < 0.05 | 非常困难(<5%) |

### 销量趋势方向 — from CategoryTrend(0) YoY

Valid options (4): 上升, 稳定, 下降, 波动

| YoY growth | Value |
|---|---|
| > 0.20 | 上升 |
| 0.05 - 0.20 | 稳定 |
| < -0.05 | 下降 |
| erratic (high monthly variance) | 波动 |

### 搜索量趋势方向 — from CategoryTrend(0) + KeywordRequest

Valid options (6): 快速增长, 稳定增长, 平稳, 增速放缓, 下降, 波动

| Condition | Value |
|---|---|
| YoY > 20% and trend accelerating | 快速增长 |
| YoY 5-20% with steady slope | 稳定增长 |
| YoY -5% to 5% | 平稳 |
| Was high growth, recent quarters narrowing | 增速放缓 |
| YoY < -5% | 下降 |
| Irregular seasonal pattern | 波动 |

### 垄断趋势方向 — from CategoryTrend Top3 share trend

Valid options (3): 分散化(下降), 稳定, 集中化(上升)

| Top3 share trend | Value |
|---|---|
| Share declining over 24mo | 分散化(下降) |
| Share stable within ±5pp | 稳定 |
| Share increasing over 24mo | 集中化(上升) |

### 推进状态 (product_candidates) — AI may only write the initial value

Valid options (4): 待分析, 已分析已做, 已分析不做, 已推进初筛

| Condition | Value |
|---|---|
| Just completed analysis | 待分析 |
| All other values | Human-only (do not write) |

---

## 竞争指标阈值速查

| 指标 | 🟢 蓝海 | 🟡 正常 | 🟠 注意 | 🔴 危险 | CLI Source |
|------|:--:|:--:|:--:|:--:|---------|
| Top3 ClickShare | <20% | 20-40% | 40-60% | >60% | KeywordRequest.ShareClickRate |
| 新品率(≤6mo) | >20% | 15-20% | 10-15% | <10% | CategoryRequest.OnlineDays |
| 评论门槛 | <300 | 300-500 | 500-1000 | >1000 | CategoryRequest.RatingsCount |
| CPC | <$1.0 | $1.0-2.0 | $2.0-3.0 | >$3.0 | KeywordRequest.Cpc |
| 品牌数 | >80 | 50-80 | 20-50 | <20 | CategoryRequest.Brand |
| FBA占比 | <70% | 70-90% | 90-97% | >97% | CategoryRequest.IsFBA |

---

## Feishu Percent Scale

ALL percentage fields in Feishu use 0-1 fractions: `0.152` = 15.2%.
Currency and count fields keep original values.

After a live finance write, read back: commission rate, net margin, CVR,
return rate, settlement rate. Any value outside 0-1 fails verification.

---

## Report Density

The formal report must include:
- ≥5 brand rows in competition analysis
- ≥3 attribute distribution tables
- ≥1 VOC pain table + 1 pain-to-solution mapping table
- Complete P&L table + 0-80% advertising-share sensitivity table
- Explicit Market, Financial, Launch, Overall, hard-gate statuses
- All Feishu % fields in 0-1 range

Use [report-contract.md](report-contract.md) for chapter structure.
Use [bitable-schema.md](bitable-schema.md) for complete field mapping.
