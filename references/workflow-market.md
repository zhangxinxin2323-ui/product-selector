# 市场发现工作流

## 入口路由

### ASIN

1. `ProductRequest` 获取产品信息、费用和 NodeId。
2. `ASINRequestKeywordv2` 获取关联关键词。
3. 选择品类词、属性词和场景/规格词三个维度。
4. 获取 `CategoryRequest` 和必要趋势。

### 关键词

1. 先获得关键词详情和搜索结果中的代表 ASIN。
2. 对代表 ASIN 执行 `ProductRequest` 取得 NodeId。
3. 再获取类目 Top100。

不要使用“ASIN 反查关键词”代替关键词搜索入口，两者数据意义不同。

### 类目 NodeId

1. 直接获取 `CategoryRequest`。
2. 从 Top100 标题和关键词延伸中确定至少三个关键词维度。
3. 选择代表 ASIN补充费用、评论和产品属性。

## 调用方式

使用跨平台包装器：

```bash
python scripts/sorftime_call.py ProductRequest \
  --payload-file <run-dir>/runtime/product-request.json \
  --domain 1 \
  --remaining-budget <remaining> \
  --output <run-dir>/raw/product.json
```

请求文件内容示例：

```json
{"asin": "<ASIN>", "trend": 2}
```

Windows PowerShell 优先使用 `--payload-file`，避免内联 JSON 引号被 shell 改写。包装器强制子进程使用 UTF-8，并通过二进制 UTF-8 写 stdout，避免商品标题中的零宽字符触发 GBK 输出错误和误重试。先加 `--dry-run` 检查 endpoint、payload、domain、预计积分和剩余预算。live 调用必须传 `--remaining-budget`；未知端点费用默认阻断，不能由 Agent 自动添加 override。预算不足时包装器返回错误且不调用 CLI。Code 99 使用 bounded exponential backoff；Code 4、Code 97 和本地编码/认证错误不盲目重试。

## 最小证据集

| 证据 | 来源 |
|---|---|
| 产品、价格、评分、评论、费用、NodeId | ProductRequest |
| 三个关键词维度的搜索量/CPC/搜索转化率/竞争数 | KeywordRequest |
| Top100 产品、品牌、价格、销量、评论、上架时间、FBA | CategoryRequest |
| 销量、价格、集中度趋势 | CategoryTrend |
| 正负评论证据 | ProductReviewsQuery |

缺少任一证据时写明缺口及对决策置信度的影响。

## API 预算

调用前累计 endpoint 预计消耗。达到预算后：

1. 停止新增调用。
2. 复用已有原始响应。
3. 输出尚缺证据。
4. 让用户选择 quick 结论或追加预算。

不得为了报告篇幅重复调用。

## 证据索引

为每个原始文件记录：

```json
{
  "id": "ev-category-001",
  "source": "CategoryRequest",
  "captured_at": "ISO-8601",
  "domain": 1,
  "request": {},
  "path": "raw/category.json",
  "status": "measured"
}
```

估算值使用 `status: estimated`，用户输入使用 `status: user_provided`。
