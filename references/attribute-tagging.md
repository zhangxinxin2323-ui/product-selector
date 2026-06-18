# Top100 属性标注

## 原则

- 通用引擎放在 `scripts/attribute-tagger.py`。
- 品类知识放在 `references/dimensions/*.json`。
- 未确认的自动发现维度只能用于探索，不能直接驱动正式蓝海结论。
- 标题是主要证据，五点/描述用于补充，卖家属性字段只作低置信参考。

## 维度文件格式

```json
{
  "schema_version": 1,
  "status": "confirmed",
  "name": "electronics-accessories",
  "dimensions": {
    "connector": {
      "values": [
        {
          "name": "usb-c",
          "patterns": ["usb c", "usb-c", "type c"],
          "excludes": []
        }
      ]
    }
  },
  "cross_pairs": [["connector", "power_class"]]
}
```

同义词合并到同一个 value。容易误判的词放入 `excludes`。正则模式使用 `re:` 前缀。

## 已知品类

```bash
python scripts/attribute-tagger.py \
  --input <category-response.json> \
  --dimensions-file references/dimensions/electronics.json \
  --output-dir <run-dir>/attributes \
  --price-unit cents
```

高客单价品类不要依赖 `--price-unit auto`，显式指定 `usd` 或 `cents`。

## 未知品类

不传 `--dimensions-file`：

```bash
python scripts/attribute-tagger.py \
  --input <category-response.json> \
  --output-dir <run-dir>/attributes
```

脚本会：

1. 使用通用材质、颜色、包装维度。
2. 按标题文档频率提取 1-3 gram 和规格单位。
3. 写出 `dimension-draft.json`。
4. 标记 `requires_dimension_confirmation: true`。
5. 标记 `decision_eligible: false`；所有交叉矩阵保持探索性。

让用户确认以下内容：

- 删除品类名、营销词和无决策意义词。
- 合并单复数、拼写变体和同义词。
- 将候选值分配到 5-8 个真正的购买决策维度。
- 添加高风险误判排除词。
- 将 `status` 改为 `confirmed` 后重新运行。

不要把自动草稿直接保存为正式维度库。

## 输出

| 文件 | 内容 |
|---|---|
| `top100_parsed.json` | 基础字段、属性值和逐维度置信度 |
| `attribute_summary.json` | 分布、覆盖率、统计和警告 |
| `cross_analysis.json` | 完整组合矩阵 |
| `uncertain_products.json` | 需要补查详情的产品 |
| `dimension-draft.json` | 未知品类候选维度 |

优先补查“高销量 + 关键维度未知”的产品，而不是对全部 Top100 调详情接口。
`scarce` 仍需独立需求证据；只有已确认维度下的
`high_demand_low_supply` 才能直接成为机会候选。
