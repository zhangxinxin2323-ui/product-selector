# 报告契约

## 必需章节

1. Executive Summary
2. 市场概况与三维关键词
3. 竞争格局
4. 属性分布
5. 交叉分析
6. VOC 与证据 ID
7. 供需缺口与机会优先级
8. 财务分析
9. 进入壁垒与 hard gates
10. Go/No-Go 双层评分
11. 产品矩阵与最小实验
12. 数据来源、口径和原始文件索引

章节齐全、数字可追溯比行数重要。禁止通过重复文字达到 250 行。

## 决策表达

必须同时给出：

- Market Decision
- Financial Decision
- Overall Decision
- hard gate 状态
- 置信度

缺少任一决策层时 `report_lint.py` 必须失败，不能只给警告。

财务为 PENDING 时，财务章节仍需展示反向测算和缺失输入。

## 数据诚信

- 数字后标来源或 evidence ID。
- 估算值标“估算”、假设和置信度。
- 缺失值不补造。
- `SearchConversionRate` 不写成点击 CVR。
- 零供给组合写“待验证空白”，除非有独立需求证据。

## 校验

```bash
python scripts/report_lint.py <run-dir>/full-report.md
```

lint 失败时保留草稿并报告缺项，不把草稿称为正式报告。
