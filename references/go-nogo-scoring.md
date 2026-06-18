# 双层 Go/No-Go 评分

## 第一层：Market Decision

| 维度 | 市场评分权重 | 依据 |
|---|---:|---|
| 市场规模 | 25% | 搜索量、类目销量、趋势 |
| 竞争格局 | 31.25% | 集中度、品牌数、新品表现 |
| 需求清晰度 | 18.75% | 三维关键词、VOC 和意图一致性 |
| 进入壁垒 | 25% | 评论、资金、技术、认证和供应链 |

权重由原五维体系去掉盈利维度后归一化。使用 `scripts/score_go_nogo.py` 计算，不手算。

## 第二层：Financial Decision

优先使用正式财务输出。缺真实成本时为 `PENDING`，同时提供反向成本上限。

建议将财务结果映射为 0-10 分：

| 分数 | 典型状态 |
|---|---|
| 8-10 | M≥2.0、净利率≥15%、盈亏平衡 CPC 有余量 |
| 6-7.9 | M≥1.6、净利率≥10%，仍需优化 |
| 4-5.9 | 接近盈亏平衡，风险高 |
| 0-3.9 | 亏损或 M<1.3 |

## 第三层：Launch Feasibility

使用内置财务包的三情景结果，不手算。缺可用资金或回本期限时为 PENDING；基准情景超资金/回本约束时为 HOLD；只有基准和悲观情景都满足约束时才为 GO。

## Hard gates

- 专利
- 合规/认证
- 产品安全
- 供应链可实现性

状态只能为 `pass`、`pending`、`fail`、`not_applicable`。`fail` 直接导致整体 NO-GO；`pending` 让整体最多 CONDITIONAL GO。

## 合并逻辑

```json
{
  "scores": {
    "market_size": 8,
    "competition": 7,
    "demand_clarity": 8,
    "barrier": 6,
    "profitability": 7
  },
  "hard_gates": {
    "patent": "pending",
    "compliance": "pass",
    "supply_chain": "pass"
  }
}
```

```bash
python scripts/score_go_nogo.py --input decision-input.json
```

报告必须分别显示市场、财务和 Launch Feasibility，再给综合判断。不得用高市场评分覆盖亏损、资金不足或回本超期。
