# 财务决策包

## 目标

使用 Skill 自带的 `scripts/financial_model/` 完成可复算的财务决策。桌面财务模块只作为逻辑参考，不是运行依赖。

财务层分开回答：

1. `Financial Decision`：单位经济是否成立。
2. `Launch Feasibility`：现有资金能否撑过备货、补货和推广直至回本。

## 操作路由

| operation | 使用条件 | 核心输出 |
|---|---|---|
| reverse | 缺采购价或头程 | 总落地成本上限；有头程依据时才派生采购价上限 |
| static | 成本齐全，快速判断 | 净利润、净利率、M、广告空间、盈亏 CPC/CVR |
| dynamic | 已有逐月计划 | 月度利润、库存、补货和现金流 |
| scenario | 正式立项 | 乐观/基准/悲观、峰值资金、回本月、Launch Feasibility |

## 请求协议

使用 `financial-model/v1`。百分比统一传 0-100，例如 CVR 8% 传 `8`。**此协议与 Python `finance.py` 的 0-1 小数格式（8% 传 0.08）不同——调用 JS 引擎前必须 ×100 转换。**

正向模型必需输入：售价、佣金率、FBA、产品成本、头程、CPC、点击 CVR、广告订单占比、退货率和仓储费。动态模型另需 MOQ、生产周期、运输周期、安全库存、补货覆盖天数、目标日销和模拟月数。

`SearchConversionRate` 不是点击 CVR，不得替代广告后台或明确假设的点击 CVR。

缺少 CPC/CVR 时返回 `needs_input`，不得按零广告成本继续。固定启动成本和月度固定成本未提供时可以按零运行，但必须出现在 assumptions。

## 运行

```bash
node scripts/financial_model/cli.js \
  --input <run-dir>/runtime/financial-request.json \
  --output <run-dir>/raw/financial-result.json
```

返回值必须包含：

- `model_version`
- `decision_policy_version`
- `input_hash`
- `engine: bundled-core`
- `assumptions`、`warnings`、`provenance`

同一模型版本和相同输入必须产生相同 input hash 与核心结果。

## 反向测算

反向模式首先输出盈亏平衡落地成本、目标 M 成本和目标利润率成本。这里的落地成本统一定义为：

```text
单件总落地成本 = 单件采购成本 + 单件头程费用
```

`recommendedLandedCostCeiling` 是寻源阶段的主门槛。没有可靠的 `freightAssumption` 时，
`impliedProductCostCeiling` 必须为 `null`，不得把总落地上限误写成采购价上限。
只有头程估算有来源时，才按“总落地成本上限 - 单件头程”派生采购价上限。

## 头程估算

优先使用货代针对目标站点、运输方式和批量给出的含税/不含税报价。统一折算为单件：

```text
单件头程 = 本批次全部头程相关费用 / 可销售入仓数量
```

本批次费用至少核对干线运输、清关/报关、关税、目的港杂费和送仓费用是否包含；不要把报价中未包含的项目按零处理。预估必须记录：

- 包装后单件重量和尺寸
- 计费重或计费体积及货代计费规则
- 运输方式、起运地、目的站点和报价日期
- 批量/MOQ、预计可销售入仓数量
- 报价包含项、未包含项、币种和汇率日期
- `measured / quoted / estimated` 来源状态与置信度

没有包装尺寸、重量、批量和运输方式时，不生成采购价上限；只保留总落地成本上限，待货代报价后再拆分。

只有提供 CPC + 点击 CVR，或显式 `fallbackAdRate` 时才能计算广告成本。反向结果是寻源约束，Financial Decision 保持 PENDING。

## 正向与情景模型

静态模型计算单位经济、广告单/自然单利润和敏感性。情景模型加入：

- 首批备货和 MOQ
- 生产、运输和安全库存周期
- 逐月销量、广告占比和 CPC
- 补货付款与库存约束
- 启动固定成本和月度固定成本
- 可用资金和最长回本期限

默认增长曲线只是估算，必须写入 assumptions。用户提供逐月计划时优先使用用户计划。

`peakCashRequirement` 是峰值资金需求，不是最大损失。只有提供 `inventorySalvageRatePct` 时才输出 `maximumLossAtSalvage`。

## 决策策略

Financial Decision：

- NO-GO：单件亏损或 M < 1.3。
- GO：M >= 2.0 且净利率 >= 15%。
- CONDITIONAL GO：M >= 1.6 且净利率 >= 10%。
- 其他为 HOLD。

Launch Feasibility：

- 缺可用资金或最长回本期限：PENDING。
- 基准峰值资金超预算或基准回本超期限：HOLD。
- 基准通过但悲观情景超约束：CONDITIONAL GO。
- 基准和悲观情景均通过：GO。

Financial 或 Launch 为 HOLD/PENDING 时，整体判断不得为 GO。

## 飞书闭环

```bash
python scripts/build_finance_payload.py \
  --input <run-dir>/raw/financial-result.json \
  --analysis-key <analysis-key> --domain <domain> \
  --percent-scale <fraction|whole> \
  --output <run-dir>/runtime/finance-payload.json
```

payload 默认 `write_mode: dry-run`。live 前读取 finance 表字段和格式，只写源字段，不写公式/查找字段。按分析键搜索：一条 update、零条 create、多条停止；写后回读模型版本、输入哈希、Financial Decision、Launch Feasibility、峰值资金和回本月。
