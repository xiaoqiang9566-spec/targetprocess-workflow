# Phase 2 Plan: Build Workbook

## Goal

在现有 `reports build-dataset` 的基础上，新增 `reports build-workbook`，生成一份面向质量分析的 `.xlsx` 工作簿，固定包含以下 sheet：

- `Overview`
- `Bug_Master`
- `Team_Status`
- `Severity_Risk`
- `Aging_Stale`
- `Customer_Feedback`
- `Weekly_Trend`
- `Monthly_Trend`
- `Top_Risks`
- `Unmapped_Status`

本阶段只实现“质量分析工作簿”，不实现与现有样例周报对齐的累计周报模板。周报模板保留到第三阶段 `weekly-report`。

## Decision

### 1. CLI 入口

新增命令：

- `python -m tp_codex.cli reports build-workbook --output <path>`

默认输出格式为 `xlsx`，并要求显式提供 `--output`。如果需要只查看摘要，可使用：

- `python -m tp_codex.cli reports build-workbook --format json`

### 2. 数据来源

`build-workbook` 不直接读取外部 CSV，而是在 service 内部复用 `build-dataset` 的同一套 scope、select 和派生字段逻辑，保证工作簿和后续周报/月审继续共享同一份 `bug_master` 数据口径。

### 3. 工作簿实现方式

当前项目未声明 `openpyxl`、`xlsxwriter` 等依赖，因此本阶段不引入新第三方库，而是在仓库内新增一个最小可用的 OOXML `.xlsx` 写入器：

- 使用 `zipfile` 生成标准 `.xlsx` 包
- 使用内联字符串单元格，避免 shared strings 复杂度
- 提供最小样式能力，至少支持：
  - 标题行
  - 表头行
  - 普通文本/数字/布尔值

这样可以保持项目离线可测，也不增加运行时依赖。

### 4. 本阶段范围

本阶段 sheet 内容以“稳定统计表”为主，不实现图表对象。

- `Overview` 提供核心摘要指标和分布表
- 趋势以表格形式放在 `Weekly_Trend` 和 `Monthly_Trend`
- `Top_Risks` 和 `Unmapped_Status` 提供可执行清单

图表、美化和样式强化留到后续增强，不阻塞当前自动化主链路。

## Data Model

### `Overview`

输出以下摘要指标：

- `total_records`
- `open_records`
- `closed_records`
- `high_risk_records`
- `customer_feedback_records`
- `stale_records`
- `reopened_records`
- `owner_missing_records`
- `unmapped_status_records`

并附带：

- 按 `status_group` 分布
- 按 `team` 分布
- 按 `severity` 分布

### `Bug_Master`

完整输出 `BUG_DATASET_FIELDNAMES` 对应的明细表。

### `Team_Status`

透视维度：

- 行：`team`
- 列：`status_group`
- 值：bug count

追加 `total_records` 列。

### `Severity_Risk`

透视维度：

- 行：`severity`
- 列：`risk_level`
- 值：bug count

追加 `total_records` 列。

### `Aging_Stale`

按 `aging_bucket` 汇总以下列：

- `total_records`
- `open_records`
- `stale_records`
- `owner_missing_records`
- `high_risk_records`

### `Customer_Feedback`

只保留 `is_customer_feedback = true` 的记录，输出：

- 摘要指标
- 按 `team` 分布
- 按 `status_group` 分布
- 明细清单

### `Weekly_Trend`

按 `created_week` 和 closed bug 的 `last_status_change_at` 所在周生成趋势表，至少包含：

- `week`
- `created_count`
- `closed_count`
- `net_change`
- `high_risk_created_count`
- `customer_feedback_created_count`

### `Monthly_Trend`

按月输出：

- `month`
- `created_count`
- `closed_count`
- `reopened_count`
- `customer_feedback_created_count`
- `high_risk_created_count`

### `Top_Risks`

输出需要人工优先关注的清单，排序优先级：

1. `risk_level = high`
2. `is_customer_feedback = true`
3. `owner_missing = true`
4. `stale_days` 降序
5. `reopen_count` 降序

列至少包括：

- `bug_id`
- `name`
- `team`
- `severity`
- `status_group`
- `risk_level`
- `stale_days`
- `reopen_count`
- `owner`
- `audit_focus`

### `Unmapped_Status`

只输出 `status_group = unmapped` 的记录明细，确保状态映射漂移可见。

## Files To Change

- `src/tp_codex/cli.py`
- `src/tp_codex/service.py`
- `src/tp_codex/renderers.py`
- `src/tp_codex/__init__.py`
- `tests/unit/test_cli.py`
- `tests/unit/test_renderers.py`
- `tests/integration/test_workflows.py`

新增：

- `src/tp_codex/workbooks.py`

## TDD Plan

### Step 1. 先补失败测试

新增或扩展测试覆盖：

- parser 包含 `reports build-workbook`
- `build-workbook` 的 `xlsx` 输出必须要求 `--output`
- service 会生成包含预期 sheet 名称的工作簿 artifact
- `render_output(..., "xlsx")` 返回二进制内容
- `Team_Status`、`Top_Risks`、`Unmapped_Status` 等关键 sheet 的核心内容存在

### Step 2. 再补实现

实现顺序：

1. `workbooks.py`
2. `service.py` 中的 `build-workbook`
3. `renderers.py` 的二进制输出支持
4. `cli.py` 的文件写出逻辑

### Step 3. 最后验证

至少运行：

- `pytest tests/unit/test_cli.py tests/unit/test_renderers.py tests/integration/test_workflows.py -k "build_workbook or xlsx" -v`
- 若通过，再跑：
  - `pytest -m "not live"`

## Risks

- 由于没有引入 Excel 库，OOXML 生成逻辑需要用测试锁住结构，避免生成 Excel 无法打开的包。
- 当前趋势表基于快照时间字段推导，不等同于全历史审计口径；月审阶段如需更严格口径，再补 history 深路径。
- 本阶段不处理图表和复杂格式，先确保数据正确、sheet 结构稳定、Excel 可打开。
