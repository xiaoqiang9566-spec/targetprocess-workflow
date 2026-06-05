# Targetprocess Bug 质量自动化工作流设计

## 状态

状态截至 `2026-06-05`：

- 仓库已具备只读 Targetprocess QA 工具链，稳定入口为 `python -m tp_codex.cli`。
- 已有 workflow 命令覆盖 `healthcheck`、`bugs intake`、`bugs triage-view`、`bugs regression-queue`、`bugs risk-scan`、`bugs review-export`、`bugs history`。
- `config/workflow_rules.yaml` 已定义默认项目范围、默认团队范围、状态分组、高风险严重级别、stale 阈值和 reopen 阈值。
- 当前仓库没有正式的报表流水线、周报/月报命令、发送适配器或调度器。
- 当前仓库已有历史导出产物，但它们是结果文件，不是稳定的业务入口。

## 目标

在当前只读 Targetprocess 工具链之上，新增一套可复用的质量自动化工作流，覆盖以下四项能力：

1. 统一 bug 数据筛选和读取口径。
2. 基于 bug 数据生成质量统计、表格透视和分析工作簿。
3. 生成每周质量周报。
4. 生成每月 bug 审计和分析结果。

## 约束

### 1. 只读边界

- Targetprocess 侧保持只读。
- 不新增 create、update、transition 类命令。
- 外部发送属于真实写操作，不与 Targetprocess 读取主流程耦合。

### 2. 项目级口径

- 稳定入口必须保持为 `python -m tp_codex.cli`。
- `config/workflow_rules.yaml` 是状态分组、风险阈值和默认范围的事实来源。
- 默认范围沿用当前项目配置：
  - `project`: `Suunto work`
  - `team`: `ESW China NG3 Driver`、`ESW China NG3 Framework`、`ESW UI Team`

### 3. 验证边界

- 大规模 live 拉取前先运行 `python -m tp_codex.cli healthcheck --format json`。
- live 测试继续保持 `TP_RUN_LIVE_TESTS=1` 显式 opt-in。
- 周报和月报生成可以基于真实数据，也必须支持基于离线样例进行集成验证。

### 4. 默认发送假设

在用户未指定渠道前，默认只生成文件，由人工发送。后续如果需要邮件、Teams、钉钉或企业微信，只新增发送适配器，不回改数据与分析主流程。

## 现状证据

当前设计基于以下仓库事实：

- [README.md](D:/3681/Documents/Targetprocess/README.md) 中已定义只读 QA workflow 能力和稳定 CLI 入口。
- [config/workflow_rules.yaml](D:/3681/Documents/Targetprocess/config/workflow_rules.yaml) 中已定义默认 scope、状态分组和风险阈值。
- [src/tp_codex/service.py](D:/3681/Documents/Targetprocess/src/tp_codex/service.py) 中已存在 workflow 层、默认 scope 合并、history fan-out 开关和 `summary` 输出。
- [src/tp_codex/normalizers.py](D:/3681/Documents/Targetprocess/src/tp_codex/normalizers.py) 中已存在标准 bug 字段归一逻辑。
- [src/tp_codex/rules.py](D:/3681/Documents/Targetprocess/src/tp_codex/rules.py) 中已存在 `status_group` 和 `risk_signals` 规则增强逻辑。

注：最终实现和验证应以这些当前文件的实际内容为准。

## 整体架构

设计采用四层结构。

### 1. 源数据层

复用现有只读 workflow 命令：

- `healthcheck`
- `bugs review-export`
- `bugs risk-scan`
- `bugs history`

这层只负责读取 Targetprocess 数据，不负责报表语义。

### 2. 标准数据集层

新增统一的 `bug_master` 标准数据集构建流程。

该流程负责：

- 调用 `review-export` 获取当前 scope 内 bug 快照。
- 复用现有 `normalize_bug()` 和 `WorkflowRulesEngine.enrich_record()`。
- 追加周报、月报和透视表需要的派生字段。
- 输出稳定 CSV 和 Excel 原始明细 sheet。

这层是后续全部报表和审计的唯一事实来源。

### 3. 分析产物层

所有质量透视表、周报和月审计只消费 `bug_master`，不再各自重新拉数。

这层负责：

- 质量分析工作簿
- 周报工作簿与简版摘要
- 月度审计工作簿与审计摘要

### 4. 发送与调度层

这一层与业务分析解耦。

- `artifact` 生成属于分析层。
- `发送` 属于外部动作层。
- `调度` 属于运行控制层。

发送失败不能影响已生成的分析产物保留。

## 标准数据集设计

### 1. 读取口径

默认读取命令：

- `python -m tp_codex.cli bugs review-export --format json`

默认业务语义：

- “全量 bug”表示默认三团队 scope 内全部状态的 bug。
- 不自动等同于“仅 open bug”。
- 周报和月报默认都从同一份 scope 快照构建。

### 2. `bug_master` 基础字段

直接保留现有标准化字段：

- `bug_id`
- `name`
- `url`
- `entity_type`
- `project`
- `team`
- `owner`
- `severity`
- `priority`
- `status_raw`
- `status_group`
- `created_at`
- `updated_at`
- `last_status_change_at`
- `suunto_app_version`
- `suunto_app_platform`
- `products`
- `firmware_version`
- `reproducibility`
- `bug_category`
- `linked_feature_ids`
- `linked_user_story_ids`
- `reopen_count`
- `risk_signals`
- `data_gaps`

### 3. `bug_master` 派生字段

新增以下派生字段，供透视、周报和月审计统一复用：

- `created_date`
- `updated_date`
- `last_status_change_date`
- `created_week`
- `updated_week`
- `created_month`
- `updated_month`
- `age_days`
- `stale_days`
- `is_open`
- `is_closed`
- `is_customer_feedback`
- `is_high_risk`
- `is_reopened`
- `owner_missing`
- `aging_bucket`
- `risk_level`
- `quality_bucket`
- `audit_focus`
- `team_scope_label`

### 4. 关键派生规则

#### `is_open`

- `status_group != closed` 时为 `true`
- 不直接依赖原始状态名

#### `is_customer_feedback`

- 默认通过 bug 标签包含 `customer feedback` 判断
- 后续如果 schema 中能稳定读取标签字段，应在标准数据集层显式暴露

#### `is_high_risk`

满足以下任一条件即为高风险：

- `severity` 属于 `high_risk_severities`
- `risk_signals` 非空

#### `aging_bucket`

默认分桶：

- `0-7`
- `8-14`
- `15-30`
- `31-60`
- `60+`

#### `risk_level`

默认分级：

- `high`：高严重级别、缺 owner、超过 reopen 阈值或 stale
- `medium`：存在一般风险信号但未进入 high
- `low`：无风险信号

## 质量分析工作簿设计

分析工作簿固定为一套稳定 sheet 结构，而不是每次临时拼表。

### 1. `Overview`

面向管理摘要，展示：

- bug 总量
- 开放 bug 数
- 高风险 bug 数
- customer feedback bug 数
- 超期 bug 数
- reopen bug 数
- 2-4 个趋势图

### 2. `Bug_Master`

完整 `bug_master` 明细表，其他 sheet 全部从此处取数。

### 3. `Team_Status`

按团队 × 状态组透视，回答当前积压主要分布在哪支团队和哪个阶段。

### 4. `Severity_Risk`

按严重级别 × 风险等级透视，回答风险集中在哪类问题。

### 5. `Aging_Stale`

按 aging bucket、stale、owner 缺失情况透视，回答长期滞留问题规模。

### 6. `Customer_Feedback`

只看 `customer feedback` 口径，回答售后问题的当前存量与风险分布。

### 7. `Weekly_Trend`

按周聚合：

- 新增
- 关闭
- 净增
- 高风险新增

### 8. `Monthly_Trend`

按月聚合：

- 新增
- 关闭
- reopen
- customer feedback
- 高风险

### 9. `Top_Risks`

列出当前最需要人工关注的问题清单，例如：

- 高严重级别
- 缺 owner
- stale
- reopen 超阈值

### 10. `Unmapped_Status`

暴露 `status_group = unmapped` 的记录，避免状态口径悄悄偏移。

## 周报设计

### 1. 周报目标

现有样例周报表明，周报不是“几项 KPI + 附件”的轻报表，而是一个面向管理和执行团队的综合周工作簿。

它回答四类问题：

1. 本周各产品版本发布是否正常，有无发布风险或阻塞。
2. 本周新增 bug 的规模、等级、状态和团队分布是什么。
3. 年度累计的有效 bug、售后问题、存量问题和专项质量指标当前进展如何。
4. 哪些团队、哪些问题类型和哪些具体风险需要本周持续跟进。

### 2. 周报主产物形态

周报主产物应与现有样例对齐，默认是一个累计维护的 `.xlsx` 工作簿，而不是单独一份 Markdown 正文。

默认形态包括：

- 一个长期维护的周报工作簿
- 每周新增一个 `固件质量数据概览-WeekNN` sheet
- 保留历史周报 sheet
- 保留辅助汇总 sheet，例如：
  - `NG3每周解决缺陷`
  - `数据总览-NG3`
  - `数据总览-Dilu`
  - 各产品版本发布时间表

如果后续接入发送渠道，消息正文只发送简版摘要；主交付仍然是周报工作簿附件或链接。

### 3. 当周 sheet 结构

每个 `WeekNN` sheet 不是一个全局总表，而是按产品线分区展开。每个产品区块使用固定模板，区块标题和配色允许按产品区分。

样例中已经出现的产品区块包括：

- `NG3`
- `Dilu`
- `心率带2`
- `Core 2`
- `Run 2`
- `Race 3S/Race3`

周报设计必须支持按配置增减产品区块，并允许每个区块绑定独立的数据范围和规则口径。

### 4. 产品区块模板

#### 4.1 发布情况块

每个产品区块默认先展示版本发布表，字段至少包括：

- `版本属性`
- `版本号`
- `计划发出时间`
- `实际发出时间`
- `发布状态`
- `风险/异常`

该区块不完全来自 bug 数据。如果没有可靠的自动来源，应允许从单独的版本计划数据表读取，或保留人工维护入口。

#### 4.2 本周新增 Bug 块

该区块对应样例中的“每周新增 Bug”段落和明细表，至少包括：

- 文字摘要：
  - 本周新增总数
  - 严重级别分布
  - 团队分布
  - 状态分布
  - 本周重点待解决问题
- 结构化表格：
  - 按严重级别汇总
  - 按状态列展开
  - 百分比行

注意：不同产品的状态列不完全一致。

例如：

- `NG3` 样例使用 `待分析 / 处理中 / 已解决 / 已验证 / 异常闭环`
- `Dilu` 样例使用 `客诉问题 / 开发过程问题 / 待处理 / 处理中 / 已解决&已闭环`
- 其他产品使用 `新 / 处理中 / 已解决 / 已验证 / 已拒绝` 等模式

因此设计上不能要求一个全产品通用的固定列集合，必须支持“按产品模板定义统计列”。

#### 4.3 年度有效缺陷修复块

该区块对应样例中的“有效 Bug 检出&修复情况”。

默认包含：

- 年度累计总有效 bug 数
- 待解决
- 待验证
- 非常规闭环单
- 关闭率
- 验证率
- 按严重级别分布
- 按工作组分布

这是周报中的核心累计质量指标，属于必须自动生成的主体内容。

#### 4.4 售后问题块

该区块对应样例中的“售后问题”分析。

默认包含：

- 售后问题总量
- 已关闭 / 待关闭 / 待验证 / 已拒绝 或近似状态分布
- 关闭率
- 按严重级别分布
- 按工作组分布
- 超期问题规模
- 响应或闭环周期超标统计
- 问题处理方案/跟进行动

其中“问题处理方案”通常不是从 bug 数据自动推导，需要预留人工备注区。

#### 4.5 存量问题消减块

该区块对应样例中的“存量 Bug 消减情况”。

默认包含：

- Bug 存量
- 年内关闭量
- 待研发处理
- 待复现
- 待验证
- 消减率
- 按工作组分布

这类指标需要同时展示当前存量和年内累计关闭，不是简单的本周快照。

#### 4.6 DI 或专项质量指标块

样例周报中，`Dilu` 等产品包含 `DI值`、版本 `DI值` 等专项指标块。

这说明周报设计必须允许按产品插入专项质量模块，而不只支持通用 bug 指标。

设计要求：

- DI 类指标作为可配置的衍生指标模块接入
- 指标公式、权重和口径单独配置
- 不与通用 `bug_master` 字段硬编码绑定

### 5. 周报数据与人工补充边界

样例周报包含大量“自动统计 + 人工结论 + 处理建议”混合内容，因此周报必须分为两层：

#### 5.1 自动生成层

以下内容应尽量自动生成：

- 本周新增 bug 统计
- 年度累计有效 bug 统计
- 售后问题统计
- 存量消减统计
- 团队分布
- 严重级别分布
- 关闭率、验证率、消减率
- 超期计数

#### 5.2 人工补充层

以下内容默认需要保留人工输入接口：

- 版本发布风险说明
- 本周重点问题描述
- 负责人提醒或行动项
- 问题处理方案
- 专项质量结论
- 外部链接和专题说明

因此，周报自动化不是“纯数据拼表”，而是“自动统计骨架 + 人工补充说明”的半自动模板。

### 6. 周报计算策略

周报仍应默认走快路径，但要按区块区分口径，而不是只算几项全局指标。

默认计算策略：

- 本周新增：`created_at` 落在本周窗口
- 当前存量类指标：基于当前快照
- 年度累计类指标：基于当前快照 + 年度时间窗口
- 本周关闭：优先使用 `last_status_change_at` 推导
- 高风险：严重级别与 `risk_signals` 联合判断
- 售后口径：优先使用 `customer feedback` 或配置化售后标签
- 超期口径：按产品模板定义，不强制全产品统一阈值

对于 `NG3` 样例中的响应周期和解决周期统计、`Dilu` 样例中的 `>15天` / `>45天` 超期定义，设计必须支持按产品单独配置 SLA 阈值。

### 7. 周报发送形态

后续如接入发送渠道，默认发送形态应调整为：

- 正文：简版摘要，概括本周各产品关键结论
- 附件或链接：完整周报工作簿

不建议把完整周报展开成聊天正文或长 Markdown，因为现有业务交付形态明显以 Excel 工作簿为主。

## 月度审计设计

### 1. 月审目标

月度审计不只是月报，而是识别流程质量和结构性风险。

### 2. 审计维度

固定覆盖五个维度：

- `规模变化`
- `风险质量`
- `流程效率`
- `流程异常`
- `重点问题清单`

### 3. 月审正文结构

月审正文至少包含：

- 月新增、月关闭、月净变化
- 团队分布和严重级别分布
- 高风险占比
- 超期占比
- 缺 owner 占比
- customer feedback 占比
- reopen 问题规模
- unmapped 状态和字段缺失提醒
- 候选重点问题列表

### 4. 月审 history 策略

月审允许走深路径，但不对全量 bug 默认拉完整 history。

只对候选异常集补拉 history，候选集默认包括：

- `reopen_count >= reopen_threshold`
- `stale`
- `severity in {Critical, Blocking}`
- `is_customer_feedback = true`
- `status_group = unmapped`
- `aging_bucket = 60+`

## 命令设计

建议在现有 CLI 下新增 `reports` 子命令组。

### 1. 数据与报表命令

- `reports build-dataset`
- `reports build-workbook`
- `reports weekly-report`
- `reports monthly-audit`

### 2. 发送与运行命令

- `reports send`
- `reports run-weekly`
- `reports run-monthly`

### 3. 命令职责

`build-dataset`

- 运行 `healthcheck`
- 拉取并标准化 bug 数据
- 输出 `bug_master`

`build-workbook`

- 基于 `bug_master` 生成质量分析工作簿

`weekly-report`

- 生成周报工作簿和简版摘要

`monthly-audit`

- 生成月审工作簿和审计摘要

`send`

- 只负责发送现有产物
- 不负责拉数和分析

`run-weekly`

- 串联 `healthcheck -> build-dataset -> build-workbook -> weekly-report -> send`

`run-monthly`

- 串联 `healthcheck -> build-dataset -> build-workbook -> monthly-audit -> send`

## 产物与目录结构

建议固定输出目录：

- `outputs/datasets/`
- `outputs/reports/weekly/YYYY-MM-DD/`
- `outputs/reports/monthly/YYYY-MM/`

每次运行至少保留：

- 原始导出快照
- `bug_master.csv`
- `bug_master.xlsx`
- 周报或月审工作簿 `.xlsx`
- 发送用简版摘要或审计摘要
- 运行摘要元数据

## 错误处理策略

### 1. `healthcheck` 失败

- 直接停止主流程
- 不生成伪报表

### 2. `partial_entities`

- 允许继续生成
- 但工作簿摘要区和发送摘要必须显式声明“本次数据不完整”

### 3. `partial_history`

- 允许继续生成
- 周报工作簿、月审工作簿和发送摘要必须显式标注

### 4. `unmapped` 状态

- 不阻塞生成
- 必须进入 `Unmapped_Status` 和审计提醒

### 5. 发送失败

- 分析产物保留成功
- 发送步骤单独报错
- 不回滚本次报表结果

## 验证计划

### 1. 单元测试

覆盖以下规则：

- `is_open`
- `is_customer_feedback`
- `is_high_risk`
- `aging_bucket`
- `risk_level`
- 周窗口和月窗口计算

### 2. 集成测试

使用固定样例数据验证：

- `build-dataset`
- `build-workbook`
- `weekly-report`
- `monthly-audit`

### 3. 产物验证

验证：

- CSV 列结构稳定
- Excel sheet 集合完整
- 核心汇总值可重复计算
- 无明显空报表或空透视

### 4. live 验证

只在 `TP_RUN_LIVE_TESTS=1` 下执行真实环境验证：

- `healthcheck`
- `build-dataset`
- `weekly-report`
- `monthly-audit`

## 分阶段落地顺序

建议固定为六个阶段：

1. `build-dataset`
2. `build-workbook`
3. `weekly-report`
4. `monthly-audit`
5. `send` 适配器
6. `run-weekly` / `run-monthly`

这样可以先完成：

- 统一筛选和读取
- 质量透视和工作簿
- 周报生成
- 月审生成

然后再按渠道接发送。

## 非目标

当前设计不包含：

- 修改 Targetprocess 数据
- 自动接入具体邮件、Teams、钉钉或企业微信发送实现
- 替代现有 workflow 命令
- 对整个 Targetprocess 实例做全局无 scope 数据拉取

## 风险

- 如果标签字段无法稳定读取，`is_customer_feedback` 需要补 schema 适配。
- 如果关闭时间不能仅靠当前快照稳定推导，月审中的关闭分析需要更明确 history 补拉。
- 如果后续新增团队或状态名，必须同步更新 `workflow_rules.yaml`。
- 周报默认快路径依赖 `last_status_change_at` 的可用性；若业务上要求更严格关闭定义，需要增加针对 closed 集合的补 history。

## 决策

本设计采用以下默认决策：

- 数据主干优先于发送渠道接入。
- 默认先只生成文件，由人工发送。
- 周报默认快路径，不对全量 bug 拉完整 history。
- 月审只对候选异常集补拉 history。
- 一切透视、周报和月审都只消费统一的 `bug_master`。

## 后续步骤

在本文档经用户审阅通过后，下一步应：

1. 基于本文档编写正式实现计划。
2. 先实现 `reports build-dataset`。
3. 再实现工作簿、周报和月审输出。
4. 最后再按用户指定渠道接入发送层。

## 备注

当前工作目录下 `git` 不可用，无法完成设计文档提交。当前阶段可完成文档写入和自检；后续如果仓库环境恢复，再补提交动作。
