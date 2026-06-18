# Amazon Review Insight 联动

## 触发

满足任一条件才启用：

- 用户明确要求深度 VOC。
- `integrations.review_insight.enabled=true` 且 Market Decision 为 GO/CONDITIONAL GO。
- 差异化机会主要依赖评论证据。

预算不足时退回 quick VOC，不中断整个选品流程。

## 数据准备

1. 选择 3-5 个代表 ASIN，不只分析单一产品。
2. 正负评论分开采集，记录 ASIN、星级、日期和来源。
3. 使用以下命令写入 `<run-dir>/runtime/<analysis-key>-review-bundle.json`：

```bash
python scripts/build_review_bundle.py \
  --input <negative-reviews.json> \
  --input <positive-reviews.json> \
  --asin <ASIN> \
  --output <run-dir>/runtime/<analysis-key>-review-bundle.json
```
4. 不把凭据或原始用户信息写入 bundle。

## 调用

若 amazon-review-insight Skill 可用，调用其 `analyze-bundle` 工作流。不要复制其方法论到本 Skill。

要求输出：

- 痛点主题及频次
- evidence_ids
- 涉及 ASIN
- 严重度与可解决性
- 正向卖点
- 评论覆盖和样本限制

## 回流

将 evidence_ids 回流到：

- 属性维度候选
- 痛点到方案映射
- 交叉组合需求验证
- 产品开发建议
- 报告 VOC 章节

没有 evidence_id 的主观推断单独标为 hypothesis。
