# 任务契约：Product Selector 全面优化

## 0. 当前发布任务（2026-06-22）

目标：发布 `v1.1.0` 团队稳定版，同时保留 `v1.0.0` 回滚基线。

本轮必须完成：

- [x] 修复 pivot CSV 无输出和价格单位猜测问题。
- [x] 增加版本化属性标注 schema、严格校验和 golden fixture。
- [x] 将 eval 从“清单校验”升级为可执行的完整 sample run。
- [x] 修正飞书质量门禁的假通过。
- [x] 精简 `SKILL.md`，让 description 明确输入、输出、工具、触发、处理和边界。
- [x] 全套测试、Skill validation 和 sample replay 通过。
- [ ] 推送新分支和 `v1.1.0` 标签；旧版可通过 `v1.0.0` 恢复。

发布边界：不调用付费 Sorftime API，不写正式飞书数据，不删除历史报告。

## 1. 目标

结合现有评估和用户提供的十项方案，将 product-selector 重构为可跨品类、可跨运行时、可验证、默认安全且支持后续扩展的 Amazon 选品 Skill。

## 2. 背景与输入

- 当前仓库：`D:\Codex\product-selector`
- 上游仓库：`zhangxinxin2323-ui/product-selector`
- 核心输入：
  - 现有 `SKILL.md`、references、`attribute-tagger.py`、evals
  - 用户提供的 P0-P3 优化清单
  - Skill Creator 的渐进披露、脚本确定性和 forward-test 规范
  - 飞书 Base 默认使用 MCP / builtin Feishu Provider 的全局规则

## 3. 边界

- 不直接修改 GitHub `main`。
- 不写入正式飞书表、监控数据库或供应商数据。
- 不执行会消耗 Sorftime 积分的真实分析，除非用户另行授权。
- 不把平台命令、表结构和长报告规范重新堆入 `SKILL.md`。

## 4. 决策授权

不用问，直接做：
- 本地分支、文件组织、脚本实现、测试数据、措辞和格式。
- 修复确定性 bug、增加 dry-run / upsert / 验证约束。

必须停下来问：
- 推送 GitHub 分支、创建 PR、修改线上飞书数据。
- 运行可能消耗 Sorftime 积分的真实 ASIN 全链路测试。

## 5. 验收标准

- [x] `SKILL.md` 收敛为核心路由，详细流程按需加载。
- [x] 属性标注支持维度文件、未知品类自发现草稿、真实空白组合识别。
- [x] 飞书写入遵循 MCP 优先、dry-run、search-before-create/upsert、回读验证。
- [x] 支持无真实成本时的反向财务测算，并区分 Market GO 与 Financial GO。
- [x] 深度 VOC、监控桥接、供应商、跨站点扫描都有明确触发和安全边界。
- [x] Sorftime 调用具备跨平台重试包装和可观测错误输出。
- [x] 配置和输出路径外置，不硬编码个人目录或正式 Base token。
- [x] evals 包含 fixture、确定性断言和负面场景。
- [x] 所有新增脚本通过本地测试，Skill 元数据通过 quick validation。
- [x] 检查不存在密钥泄露、正式表误写或旧路径残留。

以上为本地实现验收。整体完工仍需真实 Sorftime fixture/ASIN 验收；正式飞书 mutation
只在用户需要且明确授权时执行，不作为默认安全验收的前置条件。

## 6. 汇报格式

结论先行 → 数据事实 → 分析推断 → 失败与跳过 → 验证证据。

## 7. 进度区

| 时间 | 完成事项 | 验证证据 | 待决问题 |
|---|---|---|---|
| 2026-06-22 | 完成 v1.1.0 稳定性修复、严格标注门禁、黄金 replay、Skill 主流程精简 | 40 tests；6 eval；sample replay；dry-run gate 全通过；live 无回读证据按预期失败 | 真实 Sorftime fixture 仍为 0/2，不在未授权情况下消耗积分 |
| 2026-06-18 | 完成仓库与 Skill Creator 规范盘点 | 已读取全部现有核心文件和模板 | 尚未运行真实 Sorftime / 飞书链路 |
| 2026-06-18 | 完成主 Skill、配置、adapter、双层决策与扩展工作流重构 | `SKILL.md` 193 行；25 个本地引用全部存在；无旧 token/table_id 残留 | 真实飞书 adapter 尚未执行 mutation |
| 2026-06-18 | 完成属性、财务、评分、预算重试、VOC bundle、监控 payload、报告和配置脚本 | `python scripts/run_evals.py`：28/28 通过；含 Code 99 真重试、Code 4 不重试、预算硬阻断、合成全链路 | 真实 Sorftime 全链路需用户授权积分消耗 |
| 2026-06-18 | 完成 Skill 和数据格式验证 | `quick_validate.py`：Skill is valid；全部 JSON `ConvertFrom-Json` 成功 | GitHub 推送/PR 属于外部发布，待用户确认 |
| 2026-06-18 | 完成无积分环境核验 | `sorftime.cmd whoami`：CLI 可用且已认证；未发出付费 API 请求 | 待指定真实 ASIN 和积分上限 |
| 2026-06-18 | 增加可执行 eval 与证据等级门禁 | 默认 eval 校验 5 个合成 fixture 的引用和 SHA-256；`--require-live` 按预期失败并指出缺 2 个端点 | 等授权后采集并登记真实 fixture |
| 2026-06-18 | 启动内置财务决策包与飞书闭环优化 | 已确认参考 `product-financial-model` 的静态、动态和三情景逻辑，但 Skill 不依赖桌面模块 | 待完成实现与本地验收 |
| 2026-06-18 | 完成优化版 Skill 落地性复核 | `quick_validate.py` 在 `PYTHONUTF8=1` 下通过；JS 财务示例可运行；`python scripts/run_evals.py` 实测 29 项中 1 项失败；live fixture 为 0/2 | `$product-selector` 尚未安装注册；飞书 live adapter/回读未实测；配置百分比口径与 JS 请求口径待统一；50% 广告压力口径待明确并固化为门禁 |
| 2026-06-18 | 将反向寻源门槛改为采购 + 单件头程的总落地成本 | 无头程示例输出总落地上限 `$8.90` 且采购价上限为 `null`；头程 `$4` 时派生采购价上限 `$4.90`；`run_evals.py` 32/32 通过；Skill validation 通过 | 真实头程仍需货代报价或带包装尺寸/重量/批量/运输方式的可追溯估算；live fixture 仍为 0/2 |

## 8. 十项方案完工审计

| # | 要求 | 当前证据 | 状态 |
|---:|---|---|---|
| 1 | 属性引擎跨品类、维度文件、自发现 | 通用引擎 + 4 个维度库；未知品类输出 draft 且 `decision_eligible=false`；测试覆盖空白、薄供给和误匹配 | 本地完成 |
| 2 | 多平台数据写入适配 | `bitable-adapters.md` 明确 builtin/MCP → Provider → CLI fallback；live 强制 upsert 与回读 | 本地完成，未做线上 mutation |
| 3 | Review Insight 联动 | GO/CONDITIONAL 触发、评论 bundle、稳定 evidence ID、回流协议均已实现和测试 | 本地完成，未调用外部 Skill |
| 4 | 反向财务测算 | 盈亏平衡、目标 M、目标利润率、采购上限及参数边界测试 | 完成 |
| 5 | 监控数据库桥接 | 稳定 upsert key、初始快照 payload、GO-only 和 dry-run 边界 | 本地完成，未写线上库 |
| 6 | CLI 错误处理与重试 | Code 99 退避、Code 4/97 终止、超时、预算和未知费用阻断；假 CLI 实测 | 完成 |
| 7 | 输出路径配置化 | `execution.output_dir` + 分析键 + 时间戳；无个人绝对路径 | 完成 |
| 8 | evals 与真实 fixture | 5 个 eval、5 个带哈希合成 fixture、28 个确定性/负面测试；发布门禁强制 ProductRequest + CategoryRequest 真实证据 | 部分完成：真实 Sorftime fixture 待授权采集 |
| 9 | 1688 供应链工作流 | 搜索词、质量信号、成本上限、数据口径和写入边界 | 完成（指导层） |
| 10 | 跨站点扫描 | 触发、预算、站点语义对齐、指标和汇率口径 | 完成（按需扩展层） |

## 9. 财务策略增强验收

- [ ] Skill 自带财务决策包，不依赖 `D:\modular-desktop-release` 或桌面模块运行。
- [ ] 支持反向成本上限、正向单位经济、月度现金流和三情景模拟。
- [ ] CPC/CVR、成本和物流关键输入缺失时返回 `needs_input`，不按零静默计算。
- [ ] 区分 Financial Decision、Launch Feasibility、峰值资金需求和最大损失。
- [ ] 所有自动增长曲线和情景倍率进入 assumptions，并保留模型版本和输入哈希。
- [ ] 财务结果可确定性映射为飞书 finance upsert payload，默认 dry-run，live 仍遵守 MCP 优先、search-before-create 和回读验证。
- [ ] 综合决策能接收 Launch Feasibility，且 HOLD/PENDING 不会被高市场分覆盖。
- [ ] 新增脚本通过语法、边界、fixture、端到端和 Skill validation 验收。
