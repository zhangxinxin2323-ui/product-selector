# 飞书 Bitable Adapter

## 选择顺序

1. 已连接的 builtin Feishu / 飞书 MCP。
2. 项目内 Feishu Provider 或网关。
3. `lark-cli` fallback，仅当用户明确测试 CLI 或 MCP 不可用时使用。

Codex Desktop 场景优先通过网关 `/api/mcp/servers/enabled` 发现 `builtin-feishu`，再通过 `/api/mcp/call` 调用：

- `bitable_v1_appTable_list`
- `bitable_v1_appTableField_list`
- `bitable_v1_appTableRecord_search`
- `bitable_v1_appTableRecord_create`
- 对应更新工具

不要尝试从其他 Windows 用户目录读取 `lark-cli` 凭据。

## 写入协议

### dry-run

输出：

- adapter
- base 配置是否存在
- 目标表配置键
- 分析键
- create/update 计划
- 字段 payload

不执行 mutation。

### live

1. 读取表和字段，确认配置没有漂移。
2. 用稳定分析键或 ASIN + 站点 + 分析单元搜索记录。
3. 找到一条：update。
4. 找到零条：create。
5. 找到多条：停止，报告重复记录，不自动覆盖。
6. 回读记录，验证关键字段和关联字段。

## 幂等键

建议每张表增加文本字段 `分析键`：

```text
<domain>:<entry-type>:<normalized-entry>
```

同一分析单元更新时保留 `首次分析日期`，更新 `最近分析日期` 和报告版本。

## lark-cli fallback

仅在 fallback 路径加载具体 CLI 命令。Windows PowerShell 优先使用 `lark-cli.cmd`；MSYS 环境才设置 `MSYS_NO_PATHCONV=1`。

CLI 认证失败时不要引导读取其他用户凭据，改回 MCP 或提示用户显式登录当前运行身份。
