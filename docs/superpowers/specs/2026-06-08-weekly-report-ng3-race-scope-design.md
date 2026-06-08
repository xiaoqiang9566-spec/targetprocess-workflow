# Weekly Report NG3 And Race Scope Design

日期：2026-06-08

## 背景

当前 Targetprocess live 拉取默认使用 `config/workflow_rules.yaml` 中的三团队 scope：

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`

这个 scope 表示 NG3 平台相关团队范围，不等同于周报里的 `NG3` 产品统计范围。`Race 3S/Race3` 是 NG3 平台下的新产品，已在 `weekly_report.product_sections` 中作为独立产品段存在。之前把本周新增 `60` 直接描述为 `NG3` 新增，容易让 `NG3` 被理解成平台全量，而不是 NG3 老产品型号合集。

## 目标

本次只沉淀执行经验和 skill 口径，防止后续周报任务复发同类误判。

必须明确：

- live 拉取结果默认是 NG3 平台三团队数据。
- 周报产品统计必须再按 `Products` 字段拆分产品段。
- `Race 3S/Race3` 必须作为独立新产品统计。
- 周报里的 `NG3` 应解释为 NG3 老产品型号合集，不能直接等同于三团队平台全量。

## 非目标

本次不修改 `src/tp_codex/weekly_reports.py` 的产品归类逻辑。

原因：

- 现有 `_match_product()` 对 Products 为空但团队命中三团队的记录有 NG3 fallback，属于历史兼容行为。
- 若直接移除 fallback，可能漏掉 Products 为空的真实 NG3 老产品记录。
- 要改变自动计算逻辑，需要先确认 NG3 老产品型号关键词清单和历史报表兼容要求。

## 方案

采用文档和 skill 沉淀方案。

### 1. 更新项目经验文档

在 `docs/codex-project-experience-playbook.md` 追加一条经验：

- 错误做法：把默认三团队 live scope 直接叫作 `NG3` 产品统计。
- 正确方式：先声明这是 NG3 平台团队范围，再按 `Products` 字段拆产品。
- 教训：团队范围、平台范围和产品型号范围必须分开命名。

### 2. 更新长期复盘档案

在 `docs/codex-retrospective-profile.md` 的口径规则里补充：

- `NG3 平台三团队 scope` 不等同于 `NG3 老产品型号合集`。
- `Race 3S/Race3` 是 NG3 平台下的新产品段，应独立统计。
- 周报交付时，如果给出 `NG3` 数字，必须说明其产品口径。

### 3. 更新 weekly-report skill

更新仓库内 `skills/targetprocess-weekly-report/SKILL.md`：

- description 增加“产品口径纠偏、NG3 vs Race scope 校验”触发语义。
- 在 Workflow 的数据 scope 步骤中加入强制检查：三团队 live 数据只是平台范围，填报前必须检查 `Products` 分布。
- 明确 `Race 3S/Race3` 不得合入 `NG3` 周报数字。

同步更新该 skill 的 `references/workflow.md`：

- 在 Scope Pitfalls 中新增 `NG3 platform vs NG3 legacy product` 小节。
- 记录最终正确执行方式和验证清单。

### 4. 保持代码不变

不改：

- `config/workflow_rules.yaml`
- `src/tp_codex/weekly_reports.py`
- 周报相关测试

如果后续要实现自动归类纠偏，应另开实现计划，并先补充 NG3 老产品型号关键词配置。

## 数据流

周报执行时的数据解释顺序应为：

1. 读取或复用 `bug_master.json` / live workflow 导出。
2. 确认数据来自默认三团队 scope，即 NG3 平台团队范围。
3. 检查 `products` 字段分布。
4. 先把 `Race 3S/Race3`、`Dilu`、`Core 2`、`Run 2`、`心率带2` 等明确产品段分出。
5. 剩余符合 NG3 老产品口径的数据才能进入 `NG3` 周报数字。
6. 对 Products 为空或无法识别的记录，在交付摘要中标为需复核，不直接静默归入 NG3。

## 错误处理

如果现有导出缺少 `Products` 字段或产品分布明显异常：

- 不直接填写 NG3 周报数字。
- 先在回复中说明当前只能确认平台 scope，不能确认产品 scope。
- 要求使用包含 `Products` 的 `bug_master.json` 或重新生成带 `Products` 的导出。

如果用户明确要求沿用历史 fallback 口径：

- 可以继续使用现有自动结果。
- 必须在交付说明中写明：`NG3` 数字包含 Products 为空但团队命中三团队的记录。

## 验证

实施文档更新后执行：

- 读取 `docs/codex-project-experience-playbook.md`，确认新增经验包含错误做法、正确方式、教训。
- 读取 `docs/codex-retrospective-profile.md`，确认口径规则包含 NG3 平台、NG3 老产品、Race 新产品三者区别。
- 读取 `skills/targetprocess-weekly-report/SKILL.md` 和 `skills/targetprocess-weekly-report/references/workflow.md`，确认 skill description 和 workflow 均能触发产品口径校验。
- 不运行 live 命令。
- 不运行测试，除非后续实现阶段修改代码。

## 后续实现入口

本 spec 获得 review 后，进入 `superpowers:writing-plans`，生成实施计划。实施计划应只覆盖 Markdown 和 skill 文档更新，不包含代码变更。
