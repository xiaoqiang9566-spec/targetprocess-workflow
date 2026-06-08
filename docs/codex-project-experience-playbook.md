# Targetprocess 项目 Codex 阶段性经验复盘

最后更新：2026-06-05

## 适用范围

本文档是 `D:\3681\Documents\Targetprocess` 项目的项目级经验文档。后续 Codex 在该项目下工作时，应先读取并遵循本文档，再结合当前用户指令、`AGENTS.md`、`README.md`、`skills/targetprocess-qa/SKILL.md`、`config/workflow_rules.yaml` 和实时验证结果执行。

若本文档与更具体、更新的用户指令或项目配置冲突，以更具体、更新的上下文为准。

## 本次复盘依据

本次复盘读取并归纳了以下来源：

- 项目说明与配置：`AGENTS.md`、`README.md`、`config/workflow_rules.yaml`。
- 项目技能与文档：`skills/targetprocess-qa/SKILL.md`、`docs/live-validation-notes-2026-06-03.md`、`docs/integration-readiness-checklist.md`、`docs/superpowers/specs/2026-06-03-history-mode-design.md`。
- Codex 会话与日志：按 `Targetprocess`、`tp_codex`、`review-export`、`workflow_rules`、`TP_RUN_LIVE_TESTS`、`history-mode`、`dashboard` 等关键词过滤出的项目相关会话记录；重点阶段集中在 2026-06-02 至 2026-06-05，尤其是 2026-06-03 的项目建设、live 验证和文档回填阶段。
- 状态库与日志库：读取项目相关线程索引、日志级别和执行目标统计，只用于识别执行模式，不搬运原始敏感正文。

敏感信息处理原则：不在本文档中记录 token、cookie、完整私有 URL 参数、账号凭据、浏览器请求头、原始大 JSON 或私密业务原文。后续复盘也只沉淀经验和口径，不复制敏感历史内容。

## 一、执行经验总结

### 1. 浏览器可访问不等于 CLI/API 可用

曾导致问题的做法：

- 把浏览器能打开 Targetprocess 页面、dashboard 或 API 链接，直接等同于 CLI/API 鉴权成功。
- 用浏览器里的请求参数、请求头或无痕窗口行为推断 CLI 环境。
- 在聊天或命令里反复处理完整 token 和 URL，增加泄露风险。

正确执行方式：

- 浏览器访问只能说明浏览器会话有效；CLI/API 必须独立验证 `TP_BASE_URL`、认证方式、当前环境变量、配置文件、网络、API 版本和返回格式。
- 大规模拉取前优先运行 `python -m tp_codex.cli healthcheck --format json`。
- 发现 `authentication failed` 时，先检查当前 shell 里是否有过期 `TP_ACCESS_TOKEN` 覆盖了 `config/targetprocess.yaml`。
- 不把完整 token、cookie、请求头或私有 URL 参数写入文档和最终回复。

经验教训：

- 真实业务系统的“能打开”和“能自动化读取”是两件事。
- 鉴权问题要按链路拆解，不凭单一现象判断。

### 2. 入口和环境必须稳定

曾导致问题的做法：

- 在错误目录运行命令，导致 `tp_codex.cli` 找不到。
- 假设 `.venv313`、系统 Python、Anaconda 和当前 `python` 是同一解释器。
- 粘贴命令时把两条命令拼到一起，出现类似 `--format jsonpython` 的参数错误。
- 使用 `Read-Host` 或临时环境变量时没有确认变量实际值，导致空 token 或空配置。

正确执行方式：

- 始终在 `D:\3681\Documents\Targetprocess` 下运行项目命令。
- 稳定入口是 `python -m tp_codex.cli`。
- 需要排查依赖时，先确认解释器路径、`python -m pip`、测试命令和实际运行命令来自同一环境。
- PowerShell 命令分步执行，尤其是设置环境变量、运行 CLI、读取退出码时不要粘连。

经验教训：

- Windows/PowerShell 环境问题往往是路径、解释器、变量覆盖和粘贴格式共同造成的。
- 先稳定入口，再谈业务结果。

### 3. Workflow 命令优先，foundation 命令只用于调试

曾导致问题的做法：

- 用 `entities list` 替代业务工作流命令，导致默认团队范围、默认字段选择和状态分组没有自动生效。
- 直接构造 REST URL 或临时 where 条件，绕开项目中已经沉淀的工作流规则。
- 把 schema 发现命令和 QA 交付命令混用。

正确执行方式：

- QA 任务优先使用 `bugs intake`、`bugs triage-view`、`bugs regression-queue`、`bugs risk-scan`、`bugs review-export`。
- `schema snapshot` 和 `entities list` 只用于 schema 发现、字段检查、基础连通性和调试。
- `config/workflow_rules.yaml` 是状态分组、风险阈值、默认团队范围和默认字段的事实来源。

经验教训：

- 项目价值在工作流层，不在一次性 API 查询。
- 正确口径比“能查到数据”更重要。

### 4. “全量”“当前”“售后”必须按项目口径解释

曾导致问题的做法：

- 把“全量 bug”理解成整个 Targetprocess 实例的所有 bug。
- 把“全量”误解成“只有 open 状态”。
- 把“售后 bug”当成自由文本搜索，而不是固定筛选口径。

正确执行方式：

- 本项目“全量 bug”或“当前 bug”默认使用 `python -m tp_codex.cli bugs review-export`。
- “全量”表示 `config/workflow_rules.yaml` 中默认 scope 内的所有 bug 记录，不自动过滤为 open 状态。
- 默认团队范围是 `ESW China NG3 Driver`、`ESW China NG3 Framework`、`ESW UI Team`。
- 默认全量导出应直接给出“首次进入各状态时间”列，不要求用户显式加 `--history-mode full`。
- “售后 bug”使用相同三团队默认范围，并筛选 tag 为 `customer feedback` 的 bug。

经验教训：

- 业务术语必须固化成配置、命令和文档，否则每次都会重新猜。
- 用户更看重可复核的口径，而不是表面上更大的数据范围。

### 4.1 NG3 平台 scope 不等于 NG3 老产品统计

曾导致问题的做法：

- 把默认三团队 live 拉取结果直接描述为 `NG3` 产品统计。
- 看到所有记录都来自 NG3 Driver / Framework / UI 团队后，忽略 `Products` 字段里的产品线拆分。
- 将 `Race 3S/Race3` 这类 NG3 平台新产品的本周新增数量，语义上合入 NG3 老产品型号合集。

正确执行方式：

- 先把默认三团队 live 结果命名为 `NG3 平台三团队 scope`。
- 周报统计前必须检查 `Products` 分布，再按 `weekly_report.product_sections` 拆分 `NG3`、`Dilu`、`心率带2`、`Core 2`、`Run 2`、`Race 3S/Race3`。
- `Race 3S/Race3` 是 NG3 平台下的新产品段，必须独立统计。
- 周报里的 `NG3` 数字只表示 NG3 老产品型号合集；如果沿用历史 fallback 口径，必须说明包含 Products 为空但团队命中三团队的记录。

经验教训：

- 团队范围、平台范围和产品型号范围是三层口径，不能用同一个 `NG3` 名称混写。
- 周报交付时，产品统计准确性优先于复用 live scope 的便利性。

### 5. 大结果必须导出，不要在聊天中倾倒 JSON

曾导致问题的做法：

- 把 `review-export --format json` 的大型 payload 直接放到聊天里。
- 只给原始数据，不给统计摘要和交付路径。

正确执行方式：

- 交付大列表时优先使用 `--format csv --output <path>`。
- 聊天里只给关键摘要，例如总数、状态分组、严重级别分布、文件路径和未验证范围。
- 分析时可用 JSON，但面向用户交付优先 CSV、Excel 或结构化 Markdown 摘要。

经验教训：

- 可读性是数据质量的一部分。
- 导出文件比聊天长文本更适合交付和复核。

### 6. History fan-out 是性能风险，必须显式选择

曾导致问题的做法：

- 默认为 `triage-view`、`risk-scan`、`review-export` 中每个 bug 拉取完整 history。
- 把小样本能跑通理解成大列表也能接受。
- 没有区分 routine QA 视图和需要嵌入 history 的诊断视图。

正确执行方式：

- `triage-view`、`risk-scan` 默认使用 `--history-mode off`。
- `review-export` 和直接 `build-dataset` 导出默认应批量查询 `BugSimpleHistory` 风格的状态快照来推导“首次进入各状态时间”，但默认结果里不暴露原始 `history`。
- 只有用户明确需要嵌入每个 bug 的 history 明细，或在做专项样本分析时，才使用 `--history-mode full`。
- `bugs history --bug-id <ID>` 是单 bug 详情路径。
- 对 `full` 模式的大批量使用必须重新测量，不把它当作常规默认路径。

经验教训：

- 默认路径应该服务高频工作流，昂贵细节应放到显式开关后面。
- 性能决策需要 live 测量，而不是凭直觉。

### 7. Targetprocess API 返回格式和分页必须验证

曾导致问题的做法：

- 假设 `api/v1` 默认返回 JSON。
- 假设 `api/v2/Bug` 一定有 `TotalCount`。
- 只取第一页就声明数据完整。
- 后续页或 history 请求失败时，没有给用户 partial warning。

正确执行方式：

- `api/v1` 调用必须请求 `format=json`。
- `api/v2/Bug` 分页不能依赖 `TotalCount` 一定存在，应读取到短页或空页为止。
- 如果实体分页或嵌入 history 拉取中途失败，必须保留已取得记录并输出 `partial_entities` 或 `partial_history` 警告。
- 完整性声明必须基于分页、限制、警告和导出结果共同判断。

经验教训：

- “没有报错”不等于“数据完整”。
- 部分结果要诚实暴露，不能伪装成完整结果。

### 7.1 Comment 有独立只读入口，但当前 CLI 还没有一等封装

已验证事实：

- 当前实例存在独立 `Comment` 实体，schema 位于 `api/v1/Comments/meta`。
- 直接只读 GET `api/v1/Comments?take=1` 可以返回真实 comment 记录，包括 `Description`、`General`、`Owner`、`CreateDate`、`DescriptionModifyDate`。
- `entities list --entity Comment` 虽然能命中实体，但当前实现仍按 bug 结构做标准化，因此输出不可直接当 comment reader 使用。

正确执行方式：

- 需要确认 comment 能否单独读取时，优先用 `schema snapshot --entity Comment` 和受控只读 GET 验证，不要假设 comment 只能从 bug history 或页面抓取。
- 在当前仓库里，如果要产品化 comment 读取，应新增 comment 专用 normalizer 和只读命令，不要复用 bug normalizer。

经验教训：

- “上游 API 有入口”和“当前 CLI 已经正确暴露入口”是两件事。
- 探查只读能力时，要同时验证 schema、真实 GET 和本地封装层的输出形状。

### 8. Live 验证必须显式 opt-in

曾导致问题的做法：

- 在没有确认环境变量、认证方式和真实 bug id 的情况下准备运行 live 测试。
- 用离线测试通过替代真实环境验证。
- live 失败后直接猜测原因，而不是按检查清单排查。

正确执行方式：

- live 测试必须显式设置 `TP_RUN_LIVE_TESTS=1`。
- 大规模 live 拉取前先跑 `healthcheck`。
- 按 `docs/integration-readiness-checklist.md` 确认基础连通、schema、workflow rules、分页、partial warning 和 runtime 风险。
- 只读验证可以推进；写入、迁移、删除或状态变更必须另行明确授权。本项目工作流默认不添加 create、update、transition 命令。

经验教训：

- live 验证是交付闭环的一部分，但必须受控。
- 真实系统操作的权限边界必须清晰。

### 9. 失败后要回填规则，而不是只修一次

曾导致问题的做法：

- 临时解决鉴权、scope、history-mode 或导出问题后，没有更新项目文档和技能。
- 用户再次提出同类需求时，Codex 仍然从头探索。

正确执行方式：

- 稳定经验写入 `AGENTS.md`、`skills/targetprocess-qa/SKILL.md`、`README.md`、项目 docs 或本文档。
- 文档要包含错误做法、正确方式、适用条件和验证方法。
- 新增口径时同步到工作流配置或技能说明，避免只停留在聊天记录里。

经验教训：

- 用户偏好可继承的知识库，而不是一次性解释。
- 复盘只有能改变下一次执行行为才有价值。

## 二、用户偏好与理念提炼

### 1. 产品设计理念

- 真实业务优先：工具要服务 Targetprocess 缺陷治理、售后反馈分析、QA triage、regression queue、risk scan 和评审导出，而不是只做技术演示。
- 闭环优先：理想路径是确认口径、读取真实数据、验证结果、导出可交付文件、沉淀规则。
- 保守自动化：本项目默认只读。任何写入、迁移、删除、状态变更都需要明确授权。
- 稳定入口优先：沿用 `python -m tp_codex.cli`、workflow commands、`workflow_rules.yaml` 和项目技能，不发明新入口。
- 性能与可用性并重：高频路径要快，昂贵信息放在显式参数后面。

### 2. 需求偏好

- 用户说“继续”“下一步”时，默认推进当前任务链路，不重新解释已确认方向。
- 用户要求“全量”“当前”“售后”时，先按本项目沉淀口径执行；如果口径有歧义，再用一句话确认。
- 用户重视文件化交付：CSV、Markdown 文档、技能文档、配置规则都比聊天长段落更可复用。
- 用户接受必要技术细节，但细节必须服务结论、验证和下一步行动。

### 3. 数据整理偏好

- 先确认统计口径，再做分析：项目、团队、状态、时间、tag、字段和是否包含 closed 状态都要明确。
- 大数据交付使用导出文件，聊天中给高信号摘要。
- 报表优先回答可行动问题：总量、状态分布、严重级别、团队范围、售后标签、风险信号、未映射状态、partial warning。
- 不把原始 JSON 当作最终报告。

### 4. 质量理念

- 口径准确性高于数据量表面完整。
- 验证证据高于推断；完成声明前必须说明跑过什么、看到什么、还有什么未验证。
- 可审计性是质量的一部分：用户应该能通过文件路径、命令、配置或文档复核结果。
- 发现坑点后要进入流程和文档，不能只在当次会话解决。

### 5. 协作风格档案

- 语言：中文、直接、结构化、少铺垫。
- 输出：结论先行，必要时补方法、限制和验证范围。
- 行动：能直接执行就执行；遇到真实系统写操作或高风险不确定性时再请求确认。
- 文档：偏好规则清单、执行经验、个人风格档案、技能说明和可复核文件。

## 三、可复用规则清单

### 项目启动规则

1. 开始任何 Targetprocess 项目任务前，先读取 `AGENTS.md` 和本文档。
2. 涉及 QA workflow 时，再读取 `skills/targetprocess-qa/SKILL.md`。
3. 涉及 scope、状态分组、风险阈值或默认字段时，以 `config/workflow_rules.yaml` 为事实来源。
4. 涉及 live 验证时，读取 `docs/integration-readiness-checklist.md` 和 `docs/live-validation-notes-2026-06-03.md`。

### 命令选择规则

1. 稳定入口始终是 `python -m tp_codex.cli`。
2. QA 业务任务优先使用 workflow 命令，不用 `entities list` 替代。
3. `entities list` 和 `schema snapshot` 只用于调试、字段发现和 schema 检查。
4. 大列表交付优先 `bugs review-export --format csv --output <path>`。
5. `triage-view`、`risk-scan`、`review-export` 默认不拉 history；需要嵌入 history 时显式加 `--history-mode full`。

### 口径规则

1. “全量 bug”默认表示默认三团队 scope 内所有状态的 bug，不自动等同于 open bug。
2. “当前 bug”沿用同一默认三团队 scope，除非用户另行限定状态。
3. “售后 bug”表示默认三团队 scope 且 tag 为 `customer feedback`。
4. 默认三团队为 `ESW China NG3 Driver`、`ESW China NG3 Framework`、`ESW UI Team`。
5. 未映射状态要原样提示，不擅自归入 open 或 closed。

### Live 与真实系统规则

1. 大 live 拉取前先跑 `healthcheck`。
2. live 测试必须显式 `TP_RUN_LIVE_TESTS=1`。
3. 如果 live 命令失败，先检查环境变量覆盖、认证方式、当前目录、解释器和网络，再判断业务系统问题。
4. 本项目保持只读，不新增 create、update、transition 工作流。
5. 写入、迁移、删除或状态变更必须获得用户明确授权。

### 数据完整性规则

1. 分页必须验证，不只取第一页。
2. 遇到分页或 history 中途失败，要输出 partial warning。
3. `api/v1` 请求需要 JSON 格式参数；`api/v2/Bug` 分页不能假设 `TotalCount` 必然存在。
4. 聊天中不得把大型 JSON 当作交付物。
5. 最终回复必须说明导出文件、核心摘要和未验证范围。

### 文档沉淀规则

1. 稳定坑点必须写入项目文档、技能或本文档。
2. 经验文档必须包含错误做法、正确方式和教训。
3. 新增业务口径要优先写入 `AGENTS.md` 或 `skills/targetprocess-qa/SKILL.md`。
4. 更新中文 Markdown 时注意 UTF-8 编码，必要时读取验证。
5. 配置和文档更新后必须做读取校验。

## 后续维护方式

- 新增业务口径时，更新“口径规则”。
- 新增 live 验证结果时，更新 `docs/live-validation-notes-2026-06-03.md` 或新增同类 live notes。
- 新增稳定执行坑点时，追加到“一、执行经验总结”。
- 用户明确纠偏偏好时，追加到“二、用户偏好与理念提炼”。
- 修改本文档后，同步确认 `AGENTS.md` 仍然引用本文档路径。
