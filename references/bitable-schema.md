# 飞书多维表格结构参考

**App Token**: `LgO2bmmgnabbylsaJtTc4gt9n2c`

## 数据流关系

```
产品初选 (tbljJBWDxaLerJsN)
  ├─→ AI分析参考 (tblMeN1P5LvXsp2e)   [单向关联]
  ├─→ 产品初筛 (tblPhc8dHOelKPPF)     [双向关联]
  │     └─→ 关联财务 (tblllu3JJYrG5KGE) [单向关联]
  ├─→ 财务分析 (tblllu3JJYrG5KGE)      [单向关联: 关联初选 + 关联初筛]
  ├─→ 产品开发 (tbl3dtXNC3Emy38k)      [双向关联: 初选 + 初筛]
  │     └─→ 关联财务 + 关联供应商
  └─→ 供应商管理 (tblu1Q70vnmsiBZ5)    [单向关联]
```

---

## 表 1：产品初选 `tbljJBWDxaLerJsN`（15 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 编号 | AutoNumber | YT+3位序号 |
| 产品名称 | Text | |
| 产品链接/ASIN/来源 | Text | ASIN 或链接 |
| 产品图片 | Attachment | |
| 核心关键词 | Text | 逗号分隔 |
| 产品定位 | MultiSelect | 精铺偏铺 / 精铺偏精 |
| 定位理由 | Text | |
| 推进状态 | SingleSelect | 待分析/已分析已做/已分析不做/已推进初筛/待定 |
| 不做核心原因 | MultiSelect | 无供应商/利润不足/起订太多/专利风险/类目垄断/合规门槛高/差异化空间不足 |
| 判定人 | User | |
| 选品人 | User | |
| 类目 | Text | |
| 主类目链接 | Url | |
| 价格带 | SingleSelect | $10以下/$10-20/$20-30/$30-50/$50-100/$100以上 |
| 发现日期 | DateTime | yyyy/MM/dd |

**lark-cli 写入模板：**
```bash
lark-cli base +record-create --base-token LgO2bmmgnabbylsaJtTc4gt9n2c \
  --table-id tbljJBWDxaLerJsN \
  --json '<JSON>'
```

---

## 表 2：产品初筛 `tblPhc8dHOelKPPF`（24 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 初筛日期 | DateTime | 主键，自动填充 |
| 产品初选 | Link → 初选 | 多选 |
| 产品名称（来自初选） | Formula | 自动拉取 |
| 链接 | Lookup | 自动拉取 |
| 图片 | Lookup | 自动拉取 |
| 目标月销量 | Number | |
| 流量机会 | Text | |
| 类目垄断 | Text | |
| 核心关键词点击转化垄断性 | Text | |
| 新品机会 | Text | |
| 差异机会 | Text | |
| 价格机会 | Text | |
| 对标竞品 | Text | |
| CPC & CVR 压力测试 | Text | |
| 利润率 | Text | |
| 专利风险 | Text | |
| 合规认证 | Text | |
| 供应链可测分析 | Text | |
| 差异点设计 | Text | |
| 初筛判定 | SingleSelect | 建议放弃/建议采样评估/建议推进开发 |
| 判断依据总结 | Text | |
| 关联开发 | DuplexLink → 产品开发 | |
| 关联AI分析 | Link → AI分析参考 | |
| **关联财务** | Link → 财务分析 | **新增** |

---

## 表 3：财务分析 `tblllu3JJYrG5KGE`（48 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 测算日期 | DateTime | 主键 |
| 关联初选 | Link → 初选 | |
| 产品名称（来自初选） | Formula | 自动拉取 |
| 竞品ASIN | Text | 原有（兼容） |
| **竞品ASIN-1** | Text | **新增** |
| **竞品ASIN-2** | Text | **新增** |
| **竞品ASIN-3** | Text | **新增** |
| 售价 | Currency USD | |
| 产品成本 | Currency USD | |
| 头程运费 | Currency USD | |
| 落地成本 | Currency USD | |
| FBA费 | Currency USD | |
| 佣金率 | Number % | |
| 理论回款率 | Number % | |
| 理论回款率评级 | SingleSelect | 较差/可控/健康/优秀 |
| 真实回款率 | Number % | |
| 真实回款率评级 | SingleSelect | 非常健康/健康/可控/危险/极度危险 |
| 净利率 | Number % | |
| 净利率评级 | SingleSelect | 极度危险/危险/可控/健康/优秀/亏损 |
| M值 | Number | |
| M值评级 | SingleSelect | 极度危险/危险/可控/健康/优秀/亏损 |
| 广告空间 | Number % | |
| 广告空间评级 | SingleSelect | 无法打广告/很危险/可控/健康/非常优秀 |
| 单件净利润 | Currency USD | |
| 盈亏平衡CPC | Currency USD | |
| 当前CPC | Currency USD | 运营假设值 |
| 当前CVR | Number % | |
| 广告订单占比 | Number % | |
| 退货率 | Number % | |
| **市场CPC** | Currency USD | **新增** — Sorftime 数据 |
| **市场CVR参考值** | Number | **新增** — 估算值（需在UI设为百分比格式） |
| **ACOS参考值** | Number | **新增** — 估算值（需在UI设为百分比格式） |
| 首批数量 | Number | |
| 首批投入 | Currency USD | |
| 峰值投入 | Currency USD | |
| 回本月份 | Text | |
| 首次盈利月份 | Text | |
| 盈利前补货次数 | Number | |
| 总补货次数 | Number | |
| 12月总销量 | Number | |
| 12月总收入 | Currency USD | |
| 12月总广告费 | Currency USD | |
| 12月累计利润 | Currency USD | |
| 12月末现金流 | Currency USD | |
| 关联开发 | Link → 产品开发 | |
| 关联供应商 | Link → 供应商管理 | |
| **关联初筛** | Link → 产品初筛 | **新增** |

---

## 表 4：产品开发 `tbl3dtXNC3Emy38k`（18 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 开发日期 | DateTime | 主键 |
| 关联初选 | Link → 初选 | |
| 产品名称（来自初选） | Formula | |
| 需求采集 | MultiSelect | 评论-差评/关键词/评论-好评/社媒/竞品卖点 |
| 需求&痛点分析 | Text | |
| 产品改良方向 | MultiSelect | 功能型/结构型/材质型/场景型/人群型/组合型/体验型/迁移型 |
| 改良切入点 | Text | |
| 成本&供应商评估 | Text | |
| 新人群定位 | Text | |
| 新场景定位 | Text | |
| 新功能定位 | Text | |
| 新价格定位 | Text | |
| 开发状态 | SingleSelect | 调研中/打样中/备货中/已上线/搁置 |
| 负责人 | User | |
| 预计完成 | DateTime | |
| 关联初筛 | DuplexLink → 初筛 | |
| 关联财务 | Link → 财务 | |
| 关联供应商 | Link → 供应商 | |

---

## 表 5：供应商管理 `tblu1Q70vnmsiBZ5`（11 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 记录日期 | DateTime | 主键 |
| 关联初选 | Link → 初选 | ⚠️ 当前 SingleLink，建议改 MultipleLink |
| 产品名称 | Lookup | 自动拉取 |
| 供应商名称 | Text | |
| 1688链接 | Url | 用户手动提供（CLI 无 1688 端点） |
| 采购价 | Number | 用户手动提供 |
| MOQ | Number | |
| 交期天 | Number | |
| 样品状态 | SingleSelect | 未索样/已索样/已收到/样品合格/样品不合格 |
| 资质认证 | Text | |
| 备注 | Text | |

---

## 表 6：AI分析参考 `tblMeN1P5LvXsp2e`（35 字段）

> 该表以**细分市场为分析单元**，不是以 ASIN 为单元。每条记录评估一个精准细分市场。
> 所有结构化数字按组排列，便于飞书排序/筛选/跨市场对比。

### 标识组（4）

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| 分析日期 | DateTime | 主键 | 自动 |
| 关联初选 | Link → 初选 | 市场发现的线索来源 | 用户选择 |
| **细分市场名称** | Text | 精准细分市场名。同质化高用子类目名，太宽用"子类目 — 细分维度" | AI 定义 |
| AI-推荐推进 | Select | GO-推荐进入/CONDITIONAL GO-有条件/HOLD-暂缓/NO-GO-放弃/建议初筛/需更多数据 | AI 综合决策 |

### 流量组（6）

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| 核心词月搜索量 | Number | 核心关键词月搜索量 | KeywordRequest.SearchVolume |
| 核心词CPC | Number | 核心关键词当前CPC(USD) | KeywordRequest.Cpc |
| 核心词搜索转化率 | Number | **搜索转化率**(SearchConversionRate, %)。=搜索后购买的比例，来自KeywordRequest。衡量购买意图强度。**⚠️ Sorftime不提供点击CVR**(CLI+MCP共11端点均无此数据)。不可用于CPC÷CVR广告效率计算，仅用于关键词质量相对比较 | KeywordRequest.SearchConversionRate |
| 搜索量趋势方向 | Select | 快速增长/稳定增长/平稳/增速放缓/下降 | KeywordRequest.SearchVolumeTrend |
| 竞品总数 | Number | 关键词维度竞争产品数 | KeywordRequest.ProductCount |
| Top100月销额 | Number | 子类目 Top100 月销售额合计(USD) | CategoryRequest 聚合 |

### 竞争组（8）

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| Top3品牌点击集中度 | Number | Top3品牌点击占比(%) | KeywordRequest.ShareClickRate |
| 品牌数量 | Number | Top100 独立品牌数 | CategoryRequest.Brand 去重 |
| 竞争热度评估 | Select | 蓝海(<20%)/分散(20-40%)/中等(40-60%)/集中(60-80%)/垄断(>80%) | 综合判断 |
| 类目新品占比 | Number | Top100 中上架≤6月产品占比(%) | CategoryRequest.OnlineDays 分桶 |
| 平均评论门槛 | Number | Top100 平均评论数 | CategoryRequest.RatingsCount |
| FBA占比 | Number | Top100 中 FBA 发货占比(%) | CategoryRequest.IsFBA 聚合 |
| 亚马逊自营占比 | Number | Top100 中 Amazon 自营销量占比(%) | CategoryTrend(9) |
| 新品友好度 | Select | 友好(>15%)/中等(10-15%)/困难(5-10%)/非常困难(<5%) | Step 1.7 新品分析 |

### 趋势组（3）

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| 销量趋势方向 | Select | 上升/稳定/下降/波动 | CategoryTrend(0) |
| 垄断趋势方向 | Select | 分散化(下降)/稳定/集中化(上升) | CategoryTrend(28) |
| 价格带范围 | Text | Top100 售价范围，格式 "$min - $max" | CategoryRequest.Price |

### 盈利参考组（2 + 2 用户输入字段）

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| 市场均价 | Number | Top100 售价平均值(USD) | CategoryRequest.Price |
| 市场参考售价 | Number | Top100 售价中位数或主流价格段(USD) | CategoryRequest.Price |

### 成本输入组（4个用户填写字段，全有值 = Step 4 触发）

| 字段名 | 类型 | 说明 | 填写方式 |
|--------|------|------|----------|
| 1688采购价 | Number | 1688 供应商采购价(USD/件) | 用户口头或飞书手动填 |
| 头程运费 | Number | 海运头程运费(USD/件) | 用户口头或飞书手动填 |
| 当前CPC | Number | 广告后台实际CPC(USD)。市场参考值可从KeywordRequest.Cpc获取 | 用户从广告后台填写 |
| 当前点击CVR | Number | 广告点击→购买转化率(%)。**⚠️ Sorftime不提供此数据**，必须用户从广告后台填写 | 用户从广告后台填写 |

**⛔ 这4个字段全有值即自动触发 Step 4 财务分析。** 另有一个可选项：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 广告订单占比 | Number | 广告订单占总订单比例(%)，默认60% | 可选，有默认值 |

### AI分析组（4）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| AI综合评分 | Number | 1-10，5维加权（市场20%+竞争25%+需求15%+壁垒20%+盈利20%） |
| AI-核心洞察 | Text | 200字综合结论：市场判断+竞争+利润+风险+方向 |
| AI-差异化机会 | Text | 基于 VOC+交叉分析的方向：痛点→方案→主图→竞品 |
| AI-风险与假设 | Text | Top3 风险+缓解+置信度标注 |

### 历史兼容（8，折旧中，保留不删）

| 字段名 | 类型 |
|--------|------|
| AI建议总览 | Text |
| AI-趋势 | Text |
| AI-竞争 | Text |
| AI-关键词流量 | Text |
| AI-评论VOC | Text |
| AI-利润测算 | Text |
| AI-市场分析 | Text |
| AI-推荐 | Text |

### 写入后自检清单（⛔ 必做）

写入记录后，回读验证以下**必填字段组**均有值：
- 标识组(4): 细分市场名称、关联初选、分析日期、AI-推荐推进
- 流量组(5): 核心词月搜索量、核心词CPC、搜索转化率、竞品总数、Top100月销额
- 竞争组(7): Top3集中度、品牌数量、竞争热度、新品占比、评论门槛、FBA占比、新品友好度
- 趋势组(3): 市场均价、价格带范围、销量趋势方向
- AI组(4): AI综合评分、AI-核心洞察、AI-差异化机会、AI-风险与假设

**23 个必填字段全部有值才算完成。`<` 符号在 JSON 中写为 `<`。**

---

## lark-cli 通用命令模板

### 创建记录
```bash
lark-cli base +record-create --base-token LgO2bmmgnabbylsaJtTc4gt9n2c \
  --table-id <TABLE_ID> --json '<JSON>'
```

### 搜索记录
```bash
lark-cli base +record-search --base-token LgO2bmmgnabbylsaJtTc4gt9n2c \
  --table-id <TABLE_ID> \
  --filter '{"conjunction":"and","conditions":[{"field_name":"<字段>","operator":"is","value":["<值>"]}]}' \
  --page-size 20
```

### 更新记录
```bash
lark-cli base +record-update --base-token LgO2bmmgnabbylsaJtTc4gt9n2c \
  --table-id <TABLE_ID> --record-id <RECORD_ID> --json '<JSON>'
```

### JSON 字段格式注意
- Text: `"字段名": "文本值"`
- Number: `"字段名": 123.45`
- SingleSelect: `"字段名": "选项名"` (不存在的选项会自动创建)
- MultiSelect: `"字段名": ["选项1","选项2"]`
- DateTime: `"字段名": 1718572800000` (毫秒时间戳)
- Link: `"字段名": ["recXXXXXX"]` (record_id 数组)
- Url: `"字段名": {"text":"显示文本","link":"https://..."}`
