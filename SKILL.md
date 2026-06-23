---
name: product-selector
description: >
  Analyze Amazon product-selection viability from an ASIN, keyword, category
  NodeId, product URL, or Feishu candidate queue. Use Sorftime CLI (mandatory)
  for all data collection; MCP is fallback only when CLI returns no data.
  Deterministic Python/Node scoring and finance tools, confirmed attribute
  schemas, and builtin Feishu Base. Batch-fetch evidence, classify Top100
  attributes, compare segments, analyze VOC, and separately decide Market GO,
  Financial GO, and Launch Feasibility. Output traceable raw JSON,
  evidence-index.json, pivot.csv, tagged-products.json, decision.json,
  full-report.md, decision-card.html, and Feishu live payloads with readback. Use for Amazon
  product screening, niche or competitor research, sourcing-cost ceilings,
  product-development decisions, and batch candidate evaluation. Missing cost
  runs reverse finance; missing CPC or click CVR keeps Financial Decision
  PENDING; unknown schemas, API costs, or unconfirmed dimensions stop final
  decisions instead of guessing.
---

# Product Selector

Use this Skill as an evidence-backed decision pipeline. Run deterministic scripts
for extraction, validation, scoring, and finance. Use model judgment only for
evidence synthesis, VOC interpretation, and recommendations.

## Non-Negotiable Gates

0. **CLI-first data collection**. All Sorftime data MUST come from `sorftime.cmd api`
   (ProductRequest, KeywordRequest, CategoryRequest, CategoryTrend, ProductReviewsQuery).
   MCP tools are fallback ONLY when CLI returns empty/error — never the default.
1. Use only Sorftime responses, user input, and explicitly labeled estimates.
2. All Feishu writes are live with search-before-create/upsert and verified readback.
3. Estimate API points before calling. Stop when `execution.api_budget` would be
   exceeded. Unknown endpoint cost is blocking.
4. Keep `Market Decision`, `Financial Decision`, `Launch Feasibility`, and
   `Overall Decision` separate.
5. Never substitute Sorftime `SearchConversionRate` for advertising click CVR.
6. Require an explicit price unit (`cents` or `usd`) for CategoryRequest data.
7. Use confirmed dimension schemas for final tagging. Draft dimensions are not
   decision-eligible.
8. Treat zero-supply cells as observations, not opportunities, until independent
   demand evidence exists.
9. Treat patent, compliance, product safety, and supply chain as hard gates.

Read [operating-rules.md](references/operating-rules.md) before financial analysis
or live persistence. It contains the fixed business thresholds and missing-data
rules.

## Sorftime CLI Endpoints (mandatory)

All data collection uses `sorftime.cmd api <Endpoint> '<json-params>'`.
CLI returns English-keyed JSON (`ListingSalesVolumeOfMonth`, `SalesPrice`, etc.)
that matches `attribute-tagger.py` FIELD_ALIASES exactly.

| Endpoint | Cost | Use |
|----------|:---:|------|
| ProductRequest | 1 | Product detail: price, FBA, rank, sales, reviews |
| KeywordRequest | 1 | Keyword detail: search volume, CPC, CVR, share |
| KeywordExtends | 5 | Keyword extension words |
| CategoryRequest | 5 | Category Top100 products + stats |
| CategoryTrend | 5 | 25-month trend: sales, price, NPS, concentration |
| ProductReviewsQuery | 5 | Product reviews (positive/negative/all) |
| ASINKeywordRanking | 2 | ASIN keyword ranking positions |

Full analysis budget: ~30 points. Always estimate before calling.

## Startup

1. Read `config.local.json`; otherwise use `config.example.json`.
2. Read [configuration.md](references/configuration.md) and run:

```powershell
python scripts/validate_config.py <config>
```

3. Confirm `python`, `node`, and `sorftime.cmd` are available on Windows.
4. Read [bitable-adapters.md](references/bitable-adapters.md) only when Feishu is
   involved. Prefer builtin Feishu/MCP over `lark-cli`.
5. Create analysis key `<domain>:<entry-type>:<normalized-entry>` and a new
   timestamped run directory.

## Modes

| Mode | Use | Point ceiling |
|---|---|---:|
| `quick` | Directional market decision | 25 |
| `full` | Formal product-selection decision | 60 |
| `deep-voc` | GO/CONDITIONAL GO review evidence | full + review calls |
| `batch` | Feishu candidate queue | Per item; max parallel 3 |

Use `full` when the user does not specify a mode. For batch work, show item count,
deduplicated analysis keys, point estimate, and batch plan before calls.

## Stable Workflow

### 1. Acquire Evidence

**Input:** ASIN, keyword, NodeId, product URL, or candidate record.

**Action:** Follow [workflow-market.md](references/workflow-market.md). Use
`scripts/sorftime_call.py` for budget checks, UTF-8 handling, bounded retry, and
raw-response persistence.

**Output:** `raw/*.json` and `evidence-index.json`. The minimum set contains
product facts, three keyword dimensions, CategoryRequest Top100, and required
trend/review evidence. Record every missing source and its decision impact.

### 2. Build Validated Attributes

**Input:** CategoryRequest JSON, explicit price unit, and a confirmed dimension
file from `references/dimensions/`.

**Action:** Prefer deterministic rules:

```powershell
python scripts/build_pivot_table.py --input <category.json> `
  --dimensions-file <confirmed-dimensions.json> --price-unit cents `
  --output <run-dir>/pivot.csv
```

If agent tagging is needed, first generate a bounded prompt, then validate the
returned JSON against the confirmed schema:

```powershell
python scripts/build_pivot_table.py --input <category.json> `
  --dimensions-file <confirmed-dimensions.json> --price-unit cents `
  --prompt-only --output <run-dir>/tagging.prompt.txt

python scripts/check_tagging.py --input <category.json> `
  --tagged-json <tagged.json> --dimensions-file <confirmed-dimensions.json> `
  --price-unit cents
```

**Output:** `pivot.csv`, `tagged-products.json`, `tagging-validation.json`, and
`enrich-asins.json`. Any missing ASIN, duplicate ASIN, invalid enum, or excessive
unknown ratio blocks the final pivot.

For an unknown category, run `attribute-tagger.py` without a dimension file to
create `dimension-draft.json`; require confirmation before rerunning this step.

### 3. Decide Market Viability

**Input:** evidence index, validated pivot, distributions, trends, and hard gates.

**Action:** Read [go-nogo-scoring.md](references/go-nogo-scoring.md), score each
dimension with evidence IDs, and run `scripts/score_go_nogo.py`.

**Output:** `Market Decision`, score breakdown, Top 3 opportunities, Top 3 risks,
unverified assumptions, and the smallest next experiment.

### 4. Analyze VOC and Product Opportunity

**Input:** selected competitor set, review evidence, keyword evidence, and pivot.

**Action:** Group pain points by attribute and map each verified pain point to a
product response. Read [cross-analysis.md](references/cross-analysis.md). Load
[review-insight-integration.md](references/review-insight-integration.md) only for
deep VOC.

**Output:** pain-point table with evidence IDs, opportunity priority, and Tier 1
product specification.

### 5. Decide Financial and Launch Feasibility

**Input:** price, fees, cost/freight when known, CPC, click CVR, return rate,
advertising share, and optional logistics/capital constraints.

**Action:** Read [finance.md](references/finance.md). Use reverse finance when cost
is missing, static finance for unit economics, and scenario finance for formal
launch decisions.

```powershell
node scripts/financial_model/cli.js --input <financial-request.json> `
  --output <run-dir>/raw/financial-result.json
```

**Output:** `Financial Decision`, `Launch Feasibility`, unit economics, 0-80%
advertising-share sensitivity, peak cash need, and payback month. Missing required
inputs produce `PENDING`/`needs_input`, never zero-filled calculations.

### 6. Persist and Deliver

**Input:** validated evidence, decisions, report content, and configured adapters.

**Action:**

| Step | Table | Write Condition | Content |
|:---:|------|:---:|------|
| 6a | 产品初选 (tbljJBWDxaLerJsN) | **Always** | ASIN, 产品名称, 类目, 核心关键词, 价格带, 推进状态=待分析 |
| 6b | AI分析参考 (tblMeN1P5LvXsp2e) | **Always** | 29+ fields: struct + AI text + link back to candidate |
| 6c | 产品初筛 (tblPhc8dHOelKPPF) | Overall GO/COND | 16-dimension assessment |
| 6d | 财务分析 (tblllu3JJYrG5KGE) | Financial GO only | 48-field P&L from finance engine |
| 6e | 产品开发 (tbl3dtXNC3Emy38k) | Overall GO/COND | Diff direction + product matrix |
| 6f | 供应商管理 (tblu1Q70vnmsiBZ5) | Manual | User provides 1688 link |

Capture candidate record_id, pass to all downstream tables,
and read back each link field to verify resolution.

Select field values MUST come from [operating-rules.md](references/operating-rules.md)
deterministic mapping tables — never guess.
Human-only fields (产品定位, 定位理由, 后验追踪) must be left empty.

Generate `decision-card.html` and `full-report.md`. Run `report_lint.py`.

**Output:**

```text
<output-dir>/<analysis-key>/<timestamp>/
  raw/*.json
  evidence-index.json
  pivot.csv
  tagged-products.json
  tagging-validation.json
  raw/financial-result.json
  runtime/finance-payload.json
  decision.json
  decision-card.html
  full-report.md
```

Every user-facing narrative must be Chinese. Preserve English API names and field
identifiers where needed for traceability.

## Completion

Run all applicable gates before claiming completion:

```powershell
python scripts/check_tagging.py <required arguments>
python scripts/report_lint.py <run-dir>/full-report.md
python scripts/check_report.py --run-dir <run-dir> `
  --overall-decision <decision> --financial-decision <decision>
python scripts/check_all.py --asin <asin> --report-dir <run-dir> `
  --overall <decision> --financial <decision> --feishu-verification <verification.json>
```

Before release or after external API changes, also run:

```powershell
python scripts/run_evals.py
python scripts/replay_sample_run.py --output-dir <temporary-dir>
```

Report failures, skipped live calls, missing evidence, and remaining uncertainty.

## Conditional References

- Supplier research: [supplier-workflow.md](references/supplier-workflow.md)
- Monitoring: [monitoring-workflow.md](references/monitoring-workflow.md)
- Cross-market comparison: [cross-market-scan.md](references/cross-market-scan.md)
- Report and field coverage: [report-contract.md](references/report-contract.md)
