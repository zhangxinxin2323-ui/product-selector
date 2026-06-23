# 产品监控桥接

## 安全边界

只有以下条件全部满足才创建监控记录：

- 综合决策为 GO。
- `integrations.monitoring.enabled=true`。
- 监控表配置存在。
- 用户明确允许写入监控库。

CONDITIONAL GO 只生成监控建议，不自动创建日级任务。

## Upsert 键

```text
<domain>:asin:<ASIN>
```

先搜索，存在则补充选品关联，不重复创建。

## 建议字段

- ASIN
- 站点
- 追踪频率
- 初始售价
- 初始 BSR
- 初始评分
- 初始评论数
- 初始抓取时间
- 关联分析键
- 关联选品开发记录 ID
- 监控状态

初始快照必须来自本次原始 ProductRequest，不从报告文本反向解析。

先生成 payload：

```bash
python scripts/build_monitor_payload.py \
  --input <run-dir>/raw/product.json \
  --analysis-key <analysis-key> \
  --domain 1 \
  --price-unit cents \
  --output <run-dir>/runtime/monitor-payload.json
```

## 完成验证

live 写入后回读 ASIN、站点、频率、初始快照和关联记录。任一缺失都标记桥接失败，但不回滚已完成的选品分析。
