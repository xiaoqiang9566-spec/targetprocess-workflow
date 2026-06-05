# Phase 3 Plan: Weekly Report

## Goal

在现有 `build-dataset` 和 `build-workbook` 的基础上，新增 `reports weekly-report`，让系统可以基于现有累计周报工作簿模板，追加一张新的 `固件质量数据概览-WeekNN` sheet，并自动填充当前周的质量统计内容。

本阶段优先对齐你提供的现有周报样式：

- 保留历史周报 sheet
- 保留辅助汇总 sheet
- 保留现有版式、合并单元格和公式布局
- 自动填充 bug 驱动的统计区块
- 对无法从 bug 数据直接推导的区块保留人工补充入口

## Decision

### 1. 输出形态

新增命令：

- `python -m tp_codex.cli reports weekly-report --week-label Week23 --template <base.xlsx> --output <path>`

默认输出格式为 `xlsx`，并要求：

- `--output`
- `--template`
- `--week-label`

如果只看摘要，不生成工作簿，可使用：

- `python -m tp_codex.cli reports weekly-report --format json --week-label Week23`

### 2. 工作簿策略

本阶段不新造一份“长得像周报”的新工作簿，而是以用户现有周报为基座追加周 sheet。

具体策略：

1. 读取模板工作簿
2. 找到最近一张 `固件质量数据概览-Week*` sheet
3. 复制该 sheet 的 XML 结构
4. 新建当前周 sheet，例如 `固件质量数据概览-Week23`
5. 只改写本周相关单元格值，不重画样式

这样可以最大限度保留：

- 原有格式
- 合并单元格
- 行高列宽
- 公式
- 历史周页
- 辅助汇总页

### 3. 自动与人工边界

自动填充：

- 标题
- 本周新增 bug 统计
- 年度有效 bug 统计
- 售后问题统计
- 存量/过程缺陷统计
- 工作组/严重级别分布

人工保留：

- 版本发布情况明细
- 发布风险说明
- Dilu DI 值模块
- 重点问题描述
- 行动项与处理方案

对于人工区块，本阶段默认清空旧值并写入“待人工补充”占位说明，避免沿用上周内容。

## Weekly Sheet Scope

### 保留的产品区块

当前周 sheet 维持与样例一致的六个产品区块：

- `NG3`
- `Dilu`
- `心率带2`
- `Core 2`
- `Run 2`
- `Race 3S/Race3`

### 自动支持的区块

#### NG3

- 每周新增 Bug
- 2026 年有效 Bug 检出&修复情况
- 2026 年售后问题
- 存量 Bug 消减情况

#### Dilu

- 每周新增 Bug
- 2026 年有效 Bug 修复情况
- 2026 年售后问题

#### 心率带2 / Core 2 / Run 2 / Race 3S-Race3

- 缺陷检出&修复情况
- 严重级别分布
- 工作组/模块分布（按模板可写入的位置支持）

### 本阶段不自动计算的区块

- 版本发布时间表明细
- Dilu 全量 DI 值
- Dilu 版本 DI 值

这些区块只保留模板结构，并在本周 sheet 中清空旧数据。

## Data Rules

### 1. 周窗口

`week_label` 直接作为本次周报窗口标签，当前周新增使用：

- `record.created_week == week_label`

### 2. 售后口径

售后问题使用：

- `is_customer_feedback == true`

### 3. 年度口径

年度累计口径使用：

- `created_at` 所在年份等于当前报表年份

### 4. 异常闭环

以原始 `status_raw` 关键字识别：

- `Duplicate`
- `Invalid`
- `Expired`
- `Later`
- `Wont Fix`
- `Rejected`

### 5. 工作组映射

优先使用 team 名称映射：

- `ESW China NG3 Driver` -> `驱动`
- `ESW China NG3 Framework` -> `框架`
- `ESW UI Team` -> `UI`

其他产品若缺少稳定 team 映射，则退回到原始 `team` 名称或 `Unassigned`。

## Implementation Shape

### 1. CLI

新增：

- `reports weekly-report`

参数：

- `--entity`
- `--limit`
- `--week-label`
- `--template`
- `--format json|xlsx`
- `--output`

### 2. Service

新增 workflow：

- `weekly-report`

流程：

1. 复用 `build-dataset`
2. 构建周报摘要数据
3. `json` 输出摘要
4. `xlsx` 输出时读取模板并追加新周 sheet

### 3. Workbook Builder

新增独立周报模块，负责：

- 从模板复制周 sheet
- 重写指定 cell
- 清空人工区块
- 追加 sheet 到现有 `.xlsx`
- 输出新工作簿 bytes

## Files To Change

- `src/tp_codex/cli.py`
- `src/tp_codex/service.py`
- `src/tp_codex/renderers.py`
- `src/tp_codex/__init__.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_workflows.py`

新增：

- `src/tp_codex/weekly_reports.py`

## TDD Plan

### Step 1. 先补失败测试

覆盖：

- parser 包含 `reports weekly-report`
- `weekly-report --format xlsx` 要求 `--template`、`--output`、`--week-label`
- service 能返回周报摘要
- service 能基于模板追加新的 `WeekNN` sheet
- 模板中的历史页和辅助页被保留
- 新周 sheet 中的关键区块标题和核心数字被改写

### Step 2. 再补实现

实现顺序：

1. `weekly_reports.py` 中的模板复制与 cell 改写
2. `service.py` 中的 `weekly-report`
3. `cli.py` 参数和输出约束
4. 小范围修正 `renderers.py` / `__init__.py`

### Step 3. 最后验证

至少运行：

- `pytest tests/unit/test_cli.py tests/integration/test_workflows.py -k "weekly_report" -v`
- 若通过，再跑：
  - `pytest -m "not live"`

## Risks

- 本阶段强依赖模板版式稳定，如果模板结构变化，cell 映射需要同步调整。
- 本阶段只改写当前周 sheet，不重算辅助汇总 sheet。
- 无法从 bug 数据直接推导的区块必须明确清空，否则会误继承上周内容。
