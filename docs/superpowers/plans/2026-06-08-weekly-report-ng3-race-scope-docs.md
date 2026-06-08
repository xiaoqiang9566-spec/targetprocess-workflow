# Weekly Report NG3 Race Scope Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update Targetprocess weekly report documentation and skill guidance so NG3 platform scope, NG3 legacy product scope, and `Race 3S/Race3` product scope are never conflated.

**Architecture:** This is a documentation-only change. The implementation updates the project experience playbook, retrospective profile, weekly-report skill entrypoint, and weekly-report workflow reference while leaving runtime product matching code unchanged.

**Tech Stack:** Markdown, Codex skill metadata frontmatter, repository documentation, `rg`, `sed`, `git`.

---

## File Structure

- Modify: `docs/codex-project-experience-playbook.md`
  - Responsibility: long-term project execution experience, including mistake patterns, correct execution, and lessons.
- Modify: `docs/codex-retrospective-profile.md`
  - Responsibility: persistent user/project preference and scope semantics profile.
- Modify: `skills/targetprocess-weekly-report/SKILL.md`
  - Responsibility: local repo weekly-report skill trigger description and default workflow.
- Modify: `skills/targetprocess-weekly-report/references/workflow.md`
  - Responsibility: detailed weekly report template and product-scope workflow guidance.
- Do not modify: `src/tp_codex/weekly_reports.py`, `config/workflow_rules.yaml`, tests, or live output files.

### Task 1: Update Project Experience Playbook

**Files:**
- Modify: `docs/codex-project-experience-playbook.md`

- [ ] **Step 1: Inspect the current execution experience section**

Run:

```bash
sed -n '1,180p' docs/codex-project-experience-playbook.md
```

Expected: The file includes numbered execution lessons and does not yet include a dedicated NG3 platform versus Race product-scope lesson.

- [ ] **Step 2: Add a new execution lesson after the existing scope-related lessons**

Use `apply_patch` to insert this section after the current “全量/当前/售后” or weekly report scope discussion:

```markdown
### NG3 平台 scope 不等于 NG3 老产品统计

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
```

- [ ] **Step 3: Verify the playbook wording**

Run:

```bash
rg -n "NG3 平台 scope|Race 3S/Race3|NG3 老产品" docs/codex-project-experience-playbook.md
```

Expected: Output shows the new lesson and includes all three phrases.

### Task 2: Update Retrospective Profile

**Files:**
- Modify: `docs/codex-retrospective-profile.md`

- [ ] **Step 1: Inspect reusable scope rules**

Run:

```bash
sed -n '180,260p' docs/codex-retrospective-profile.md
```

Expected: The reusable rules include default three-team scope and high-level bug semantics.

- [ ] **Step 2: Add NG3 product-scope rules**

Use `apply_patch` to add these rules under the existing “过滤与语义规则” or equivalent reusable rules section:

```markdown
7. 周报里的 `NG3 平台三团队 scope` 不等同于 `NG3 老产品型号合集`
8. `Race 3S/Race3` 是 NG3 平台下的新产品段，周报中必须独立统计
9. 交付 `NG3` 周报数字时，必须说明它是 NG3 老产品口径，还是包含 Products 为空记录的历史 fallback 口径
```

- [ ] **Step 3: Verify the profile wording**

Run:

```bash
rg -n "NG3 平台三团队 scope|NG3 老产品型号合集|历史 fallback" docs/codex-retrospective-profile.md
```

Expected: Output shows all three newly added semantics.

### Task 3: Update Weekly Report Skill Entrypoint

**Files:**
- Modify: `skills/targetprocess-weekly-report/SKILL.md`

- [ ] **Step 1: Inspect the current skill metadata and workflow scope step**

Run:

```bash
sed -n '1,70p' skills/targetprocess-weekly-report/SKILL.md
```

Expected: The description mentions building, repairing, validating weekly workbooks, but does not yet explicitly mention NG3 versus Race product-scope correction.

- [ ] **Step 2: Replace the skill description**

Use `apply_patch` to replace the frontmatter `description` value with this single line:

```yaml
description: Build, repair, or validate weekly QA report workbooks for this Targetprocess project from existing bug snapshot bundles and Excel templates. Use when Codex is asked to generate `WeekNN` weekly reports, reuse `bug_master.json/csv` from `outputs/reports/weekly/...`, fix formatting or content mismatches in `weekly-report-WeekNN.xlsx`, align a report strictly to a provided `.xlsx` template, validate weekly product scope, or correct NG3 versus `Race 3S/Race3` reporting semantics.
```

- [ ] **Step 3: Add scope guidance to workflow step 4**

Use `apply_patch` to add these bullets under “Choose the data scope that matches the template, not just the team scope.”:

```markdown
- Treat the default three-team live scope as `NG3 platform scope`, not as the `NG3` product total.
- Before filling any `NG3` count, inspect `Products` distribution and split out configured product sections.
- `Race 3S/Race3` is an NG3-platform new product and must remain separate from the NG3 legacy-product count.
- If `Products` is empty or ambiguous, report the ambiguity instead of silently merging the record into NG3.
```

- [ ] **Step 4: Verify skill trigger and workflow wording**

Run:

```bash
rg -n "validate weekly product scope|NG3 platform scope|Race 3S/Race3|legacy-product" skills/targetprocess-weekly-report/SKILL.md
```

Expected: Output shows the updated description and workflow bullets.

### Task 4: Update Weekly Report Workflow Reference

**Files:**
- Modify: `skills/targetprocess-weekly-report/references/workflow.md`

- [ ] **Step 1: Inspect the current scope pitfalls section**

Run:

```bash
sed -n '52,82p' skills/targetprocess-weekly-report/references/workflow.md
```

Expected: The section warns that default team scope is not always enough and mentions product leakage.

- [ ] **Step 2: Add NG3 platform versus legacy product guidance**

Use `apply_patch` to add this subsection after the existing product leakage warning:

```markdown
### NG3 platform scope versus NG3 legacy product

The default live pull for this project is usually scoped to the three NG3-platform teams:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`

That scope means "NG3 platform team data". It does not automatically mean the `NG3` product section in the weekly report.

For weekly reporting:

- `Race 3S/Race3` is an NG3-platform new product and must be counted as its own product section.
- `NG3` should mean the NG3 legacy product-model collection.
- Always inspect `products` before reporting a number as `NG3`.
- If a record has empty or unrecognized `products`, keep it in a review bucket or explicitly state that the historical team fallback was used.

The previous mistake was describing a default-scope weekly-new count such as `60` as `NG3 本周新增 60`. The correct wording is either:

- `NG3 平台三团队本周新增 60，需按 Products 继续拆分`
- `NG3 老产品本周新增 N，Race 3S/Race3 本周新增 M`
```

- [ ] **Step 3: Add this check to the validation checklist**

Use `apply_patch` to add this bullet under “Before handoff, verify:”:

```markdown
- Product-scope language distinguishes `NG3 platform scope`, `NG3 legacy product`, and `Race 3S/Race3`.
```

- [ ] **Step 4: Verify workflow reference wording**

Run:

```bash
rg -n "NG3 platform scope versus NG3 legacy product|NG3 平台三团队|Race 3S/Race3|Product-scope language" skills/targetprocess-weekly-report/references/workflow.md
```

Expected: Output shows the new subsection and validation checklist bullet.

### Task 5: Final Verification And Commit

**Files:**
- Verify: `docs/codex-project-experience-playbook.md`
- Verify: `docs/codex-retrospective-profile.md`
- Verify: `skills/targetprocess-weekly-report/SKILL.md`
- Verify: `skills/targetprocess-weekly-report/references/workflow.md`

- [ ] **Step 1: Run a cross-file scope-language check**

Run:

```bash
rg -n "NG3 平台|NG3 platform|NG3 老产品|NG3 legacy|Race 3S/Race3|Products" docs/codex-project-experience-playbook.md docs/codex-retrospective-profile.md skills/targetprocess-weekly-report/SKILL.md skills/targetprocess-weekly-report/references/workflow.md
```

Expected: Output shows each target file contains the intended scope language.

- [ ] **Step 2: Confirm only documentation files changed**

Run:

```bash
git diff --name-only
```

Expected: The implementation diff includes these four files:

```text
docs/codex-project-experience-playbook.md
docs/codex-retrospective-profile.md
skills/targetprocess-weekly-report/SKILL.md
skills/targetprocess-weekly-report/references/workflow.md
```

Existing unrelated dirty files may still appear in the working tree. Do not stage or revert them.

- [ ] **Step 3: Review the implementation diff**

Run:

```bash
git diff -- docs/codex-project-experience-playbook.md docs/codex-retrospective-profile.md skills/targetprocess-weekly-report/SKILL.md skills/targetprocess-weekly-report/references/workflow.md
```

Expected: The diff only adds product-scope documentation and skill guidance. It does not change runtime code, tests, workflow config, or generated report outputs.

- [ ] **Step 4: Stage only the documentation updates**

Run:

```bash
git add docs/codex-project-experience-playbook.md docs/codex-retrospective-profile.md skills/targetprocess-weekly-report/SKILL.md skills/targetprocess-weekly-report/references/workflow.md
```

Expected: The staged diff contains only the four documentation files.

- [ ] **Step 5: Commit the documentation updates**

Run:

```bash
git commit -m "docs: clarify weekly report ng3 race scope"
```

Expected: Git creates one commit for the scope clarification documentation.
