# 配置与运行目录

## 配置加载

按以下顺序读取：

1. 用户明确指定的配置文件。
2. Skill 根目录的 `config.local.json`。
3. `config.example.json`。

`config.local.json` 已加入 `.gitignore`，可以保存私人 Base token 环境变量名、table_id 和本机集成路径。不要把 app secret、访问令牌或解密后的凭据写入 Skill 文件和报告。

## 安全默认值

- `execution.write_mode`: `live`
- `execution.api_budget`: `60`
- `execution.max_parallel`: `3`
- `integrations.*.enabled`: `false`

配置缺失时 `write_mode` 必须为 `live`，需校验飞书配置完整性和 base_token_env。

## 输出目录

使用相对 Skill 或项目工作目录的 `execution.output_dir`，默认 `./outputs`。不要硬编码用户主目录或 `D:` 下的个人路径。

每次执行使用：

```text
<output-dir>/<analysis-key>/<timestamp>/
```

其中 `analysis-key` 只包含小写字母、数字、连字符和下划线。

## 环境变量

配置只保存环境变量名称：

```json
{
  "base_token_env": "PRODUCT_SELECTOR_BASE_TOKEN",
  "table_id_env": "PRODUCT_MONITOR_TABLE_ID"
}
```

运行时读取对应变量；日志只显示“已配置/未配置”，不得回显值。

## 财务模型

- `finance.engine` 固定为 `bundled-js`，禁止硬编码桌面模块路径。
- `scenario_profile` 只能为 `conservative`、`moderate` 或 `aggressive`。
- `available_capital` 未设置时仍可计算现金流，但 Launch Feasibility 必须为 PENDING。
- `max_payback_months` 取 1-24。
- `inventory_salvage_rate` 使用 0-1；缺失时不输出最大损失估算。
- `feishu_percent_scale` 根据目标 Base 百分比字段选择 `fraction` 或 `whole`，live 前必须读取字段格式确认。
