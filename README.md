# Product Selector

## 版本与回滚

- `v1.1.0`：严格属性 schema、确定性 pivot、黄金样例 replay、真实门禁。
- `v1.0.0`：发布前回滚基线。新版本出现问题时可按该标签安装或检出。

Amazon 选品决策 Skill。支持 ASIN、关键词、类目 NodeId 和飞书候选队列，输出证据化的市场、属性、VOC、财务和产品开发建议。

## 设计重点

- Market Decision 与 Financial Decision 分开。
- 没有成本也执行反向财务测算，先给出“采购 + 单件头程”的总落地成本上限；有头程依据时才派生采购价上限。
- 属性标注使用外部品类维度库，不把家居规则写死在脚本中。
- 未知品类生成 `dimension-draft.json`，确认后才用于正式判断。
- 飞书优先使用 builtin Feishu / MCP，`lark-cli` 只作显式 fallback。
- 默认 dry-run，正式写入使用 search-before-create/upsert 和回读验证。
- 空白组合只表示零供给观察，不自动等于蓝海。

## 快速使用

```text
帮我分析 B0F9JZSK2Q，先 dry-run，不要写飞书。
```

```text
nail drill 值得做吗？控制在 25 积分以内。
```

```text
成本 8 美元，头程 5 美元，CPC 0.7，点击 CVR 8%，重新跑正式财务。
```

## 配置

复制 `config.example.json` 为 `config.local.json`，填写环境变量名和逻辑表对应的 table_id。

重要默认值：

```json
{
  "write_mode": "dry-run",
  "api_budget": 60,
  "output_dir": "./outputs"
}
```

不要把 app secret 或访问令牌写入配置文件。飞书凭据由 MCP / Provider 或环境变量管理。

## 确定性脚本

### 属性标注

```bash
python scripts/attribute-tagger.py \
  --input evals/fixtures/sample-electronics-category.json \
  --dimensions-file references/dimensions/electronics.json \
  --output-dir outputs/demo \
  --price-unit cents
```

### 可透视 CSV 与标注校验

```bash
python scripts/build_pivot_table.py \
  --input evals/fixtures/sample-electronics-category.json \
  --dimensions-file references/dimensions/electronics.json \
  --tagged-json evals/fixtures/sample-electronics-tagged.json \
  --price-unit cents \
  --output outputs/demo/pivot.csv

python scripts/check_tagging.py \
  --input evals/fixtures/sample-electronics-category.json \
  --tagged-json evals/fixtures/sample-electronics-tagged.json \
  --dimensions-file references/dimensions/electronics.json \
  --price-unit cents
```

内置维度库：

- `generic.json`
- `home-storage.json`
- `electronics.json`
- `outdoor.json`

### 反向财务

```bash
python scripts/finance.py reverse \
  --price 39.99 --fba-fee 8.20 --commission-rate 15 \
  --return-rate 0.05 --cpc 0.80 --cvr 8 --freight-assumption 4
```

### 正式财务

```bash
python scripts/finance.py forward \
  --price 39.99 --fba-fee 8.20 --commission-rate 15 \
  --return-rate 0.05 --product-cost 7.50 --freight 4 \
  --cpc 0.80 --cvr 8
```

### Sorftime dry-run

```bash
python scripts/sorftime_call.py CategoryRequest \
  --payload-file evals/fixtures/category-request-payload.json \
  --domain 1 --dry-run
```

### 报告校验

```bash
python scripts/report_lint.py evals/fixtures/expected-report.md
```

### 配置校验

```bash
python scripts/validate_config.py config.example.json
```

## 测试

```bash
python scripts/run_evals.py
```

完整黄金样例可重复生成 pivot、标注校验、财务结果并验证报告：

```bash
python scripts/replay_sample_run.py --output-dir outputs/sample-replay
```

测试 fixture 为合成数据，只用于验证引擎行为，不代表真实市场结论。正式发布门禁使用：

```bash
python scripts/run_evals.py --require-live
```

该命令要求至少包含 `ProductRequest` 和 `CategoryRequest` 两个具有来源元数据及
SHA-256 的真实 Sorftime fixture。

## 目录

```text
SKILL.md
config.example.json
agents/openai.yaml
scripts/
  attribute-tagger.py
  build_review_bundle.py
  build_monitor_payload.py
  finance.py
  report_lint.py
  score_go_nogo.py
  sorftime_call.py
  validate_config.py
references/
  dimensions/
  bitable-adapters.md
  bitable-schema.md
  configuration.md
  cross-analysis.md
  cross-market-scan.md
  finance.md
  go-nogo-scoring.md
  monitoring-workflow.md
  report-contract.md
  review-insight-integration.md
  supplier-workflow.md
  workflow-market.md
evals/
tests/
```
