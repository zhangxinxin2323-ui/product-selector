# Product Selector — Amazon 精铺选品 Skill

基于 **Sorftime CLI** 的 Amazon 精铺选品分析系统。融合市场调研深度（ZPR 属性标注 + 交叉分析 + Go/No-Go）与运营效率（飞书表格 + CLI 稳定性 + 批量能力）。

## 能力

- **3 入口**: ASIN / 关键词 / 类目
- **6 步自动分流**: GO/COND → 全流程, HOLD/NO-GO → 停止
- **属性标注**: Top100 自动维度发现 + 交叉分析 + 空白/薄供给识别
- **飞书 6 表**: 初选 → AI分析 → 初筛 → 财务 → 开发 → 供应商
- **Go/No-Go**: 5 维加权评分 + 决策矩阵
- **后验追踪**: 6 个月后复盘成功/失败原因

## 安装

```bash
# 安装到 Claude Code
cp -r product-selector ~/.claude/skills/
```

## 前置条件

- `sorftime` CLI — `npm install -g sorftime-cli`
- `lark-cli` — 飞书 CLI
- Sorftime MCP 配置（仅用于飞书写入，数据采集用 CLI）
- Python 3（可选，attribute-tagger.py 脚本需要）

## 使用

```
帮我分析 B0F9JZSK2Q
nail drill 这个品类值得做吗
产品初选表里待分析的都帮我跑
```

## 文件结构

```
product-selector/
├── SKILL.md                    # 主工作流 (580行)
├── README.md
├── evals/                      # 测试用例
├── references/                 # 方法论参考
│   ├── analysis-patterns.md    # 4 种分析模式
│   ├── attribute-tagging.md    # 属性标注指南
│   ├── bitable-schema.md       # 飞书 6 表字段
│   ├── cross-analysis.md       # 交叉分析方法论
│   ├── go-nogo-scoring.md      # 评分体系
│   └── html-report-spec.md     # HTML 决策卡规范
└── scripts/
    └── attribute-tagger.py     # Top100 属性标注脚本
```

## 输出

每次分析输出两份文件：

- `decision-card.html` — 半屏速判卡（手机可看）
- `full-report.md` — 完整分析报告（≥10 章，≥250 行）

## 飞书集成

分析结果自动写入飞书多维表格 `rwlz9eyyr5o.feishu.cn`，6 张表：

| 表 | 触发 |
|----|------|
| 产品初选 | 永远 |
| AI分析参考 (35字段) | 永远 |
| 产品初筛 | GO / CONDITIONAL |
| 财务分析 (48字段) | 用户提供成本后 |
| 产品开发 | GO / CONDITIONAL |
| 供应商管理 | 用户提供 1688 链接后 |

## 作者

基于 [zach-product-research](https://github.com/zach22-1999/amazon-skills) 方法论，融合飞书运营闭环。
