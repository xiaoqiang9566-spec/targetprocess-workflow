# Targetprocess Codex 复盘经验档案

最后更新：2026-06-06

## 适用方式

本文档是 `Targetprocess` 项目的长期复盘资产，面向后续所有在本仓库内执行的 Codex 会话。

加载顺序建议：

1. `AGENTS.md`
2. `docs/codex-project-experience-playbook.md`
3. 本文档
4. `skills/targetprocess-qa/SKILL.md`
5. `config/workflow_rules.yaml`

本文档不重复搬运大段历史原文，只保留可复用模式、证据位置和稳定规则。

## 证据范围

本次复盘基于以下证据源抽取：

- 项目文档：`/Users/xiaoqiang/Documents/targetprocess/AGENTS.md`、`/Users/xiaoqiang/Documents/targetprocess/README.md`、`/Users/xiaoqiang/Documents/targetprocess/docs/codex-project-experience-playbook.md`、`/Users/xiaoqiang/Documents/targetprocess/docs/live-validation-notes-2026-06-03.md`、`/Users/xiaoqiang/Documents/targetprocess/docs/integration-readiness-checklist.md`
- 项目设计文档：`/Users/xiaoqiang/Documents/targetprocess/docs/superpowers/specs/2026-06-03-history-mode-design.md`、`/Users/xiaoqiang/Documents/targetprocess/docs/superpowers/specs/2026-06-05-targetprocess-retrospective-design.md`、`/Users/xiaoqiang/Documents/targetprocess/docs/superpowers/specs/2026-06-06-targetprocess-end-user-export-design.md`
- 项目相关会话索引：`/Users/xiaoqiang/.codex/state_5.sqlite`。本次扫描时共 `106` 条线程，其中 `cwd` 命中 `targetprocess` 的线程共 `26` 条
- 全局执行日志：`/Users/xiaoqiang/.codex/logs_2.sqlite`。本次扫描时共 `194311` 条日志
- 关键原始会话：`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-03T00-20-35-019e8923-0be0-7953-8d6a-3b05ffa4b111.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-05T22-32-08-019e9832-d5c5-7b82-86db-4ac10289e581.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-05T23-02-33-019e984e-ac96-74a1-8c46-fa0dfeeae42b.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-06T05-09-27-019e999e-95d5-7512-a8b7-e7c75c49c161.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-06T09-02-43-019e9a74-2636-7141-b087-15c658153793.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-06T09-50-09-019e9a9f-92ac-7a72-99bb-3776b2b2c6a6.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-06T10-51-25-019e9ad7-a975-7240-8595-d88027017c88.jsonl`、`/Users/xiaoqiang/.codex/archived_sessions/rollout-2026-06-06T10-56-00-019e9adb-dac6-7e61-9a40-4862d4c13253.jsonl`、`/Users/xiaoqiang/.codex/sessions/2026/06/06/rollout-2026-06-06T12-31-29-019e9b33-464f-7891-ba43-c8da36c1c441.jsonl`、`/Users/xiaoqiang/.codex/sessions/2026/06/06/rollout-2026-06-06T12-54-45-019e9b48-9219-7313-aa69-da59000f680e.jsonl`、`/Users/xiaoqiang/.codex/sessions/2026/06/06/rollout-2026-06-06T13-06-03-019e9b52-ee27-77d2-9f49-421d32c89a56.jsonl`

## 一、执行经验总结

### 1. 浏览器可访问不等于 CLI/API 可用

导致问题的做法：

- 把浏览器能打开 `Targetprocess` 页面，直接等同于 CLI 已具备可读鉴权
- 用浏览器里的会话状态，代替 `healthcheck`、真实 API 响应和本地配置验证

最终正确方式：

- CLI 链路单独验证，先跑 `python -m tp_codex.cli healthcheck --format json`
- 分离“浏览器会话可用”和“Codex 当前 shell 凭据可用”这两件事

教训：

- 真实系统里，“页面能打开”和“自动化链路可读”是两套独立前提

### 2. 稳定入口要先钉死，不能临时绕开 workflow

导致问题的做法：

- 直接拼 REST 过滤、直接试基础实体命令、或者把 `entities list` 当成业务导出命令
- 没先读取项目 playbook、skill 和 `workflow_rules.yaml`

最终正确方式：

- 稳定入口固定为 `python -m tp_codex.cli`
- QA 导出优先走 `bugs review-export` 或 `reports build-dataset`
- `schema snapshot`、`entities list` 只保留给调试、字段发现和能力探查

教训：

- 这个项目的业务口径沉淀在 workflow 层，不在一次性查询里

### 3. worktree 或新会话不会自动继承 live 凭据

导致问题的做法：

- 默认假设切换到新工作树或新会话后，`TP_ACCESS_TOKEN` 之类环境变量仍然可用
- 看到 `no Targetprocess credentials configured` 后先怀疑命令或 where 子句

最终正确方式：

- 先检查当前 shell 的实际凭据来源
- 已知当前用户把凭据放在 `~/.config/targetprocess/env.zsh` 时，需要在执行会话中显式加载
- 先区分“没有凭据”“凭据过期”“沙箱无网络”三类问题，再继续排查

教训：

- live 能力依赖当前会话上下文，不依赖仓库历史成功记录

### 4. 日期过滤不能假设字符串比较在当前实例可用

导致问题的做法：

- 直接用 `CreateDate >= "2020-01-01"` 这类字符串比较，假设上游会自动做日期转换

最终正确方式：

- 当前实例应优先使用 `DateTime.Parse("YYYY-MM-DD")`
- 已验证稳定形式包括：
  - `CreateDate >= DateTime.Parse("2026-01-01") and CreateDate < DateTime.Parse("2027-01-01")`
  - `ModifyDate >= DateTime.Parse("2026-01-01") and ModifyDate < DateTime.Parse("2027-01-01")`

教训：

- where 子句要以当前实例实际接受的语法为准，不能拿通用记忆硬套

### 5. “有变更记录”默认应走 `ModifyDate`，不是深 history 过滤

导致问题的做法：

- 把“有变更记录”理解成“history 里在该时间段出现过任意事件”，从而把常规导出升级成 history fan-out 问题

最终正确方式：

- 在本项目第一优先口径里：
  - “新增” = `CreateDate`
  - “有变更记录” = `ModifyDate`
- 只有用户明确要求 history 级别语义时，才进入深路径

教训：

- 高频业务语义要优先映射到主查询字段，避免把 routine 导出做成高成本历史审计

### 6. history fan-out 只能作为显式慢路径

导致问题的做法：

- 把 `--history-mode full` 当成默认路径，或者把小样本的耗时误当成大结果集也可接受

最终正确方式：

- 默认保持 `--history-mode off`
- 仅在用户明确需要嵌入每条 bug 的原始 history 时才用 `full`
- 当前已有 live 基线证明：
  - `review-export --history-mode off --limit 20` 约 `2.83s`
  - `review-export --history-mode full --limit 20` 约 `68.82s`

教训：

- 性能策略必须由测量决定，不由直觉决定

### 7. 大导出要串成受控流程，而不是只跑单条命令

导致问题的做法：

- 只执行导出命令，不记录健康检查结果、开始时间、结束时间和最终条数
- 最后只能口头汇报耗时，无法复核

最终正确方式：

- 对大导出统一采用：
  - `healthcheck`
  - 真实导出
  - 计时文件落盘
  - 条数校验
- 近期稳定样例：
  - `2026` 年创建 bug 导出：`2324` 条，`98` 秒
  - `2020-01-01` 至今创建 bug 导出：`317997` 条，`626` 秒
  - `2026` 年有变更记录 bug 导出：`318037` 条，`777` 秒

教训：

- 用户要的是“整段流程耗时”，不是单条子命令的局部耗时

### 8. 大结果交付优先 CSV 和文件路径，不要把 JSON 倾倒进对话

导致问题的做法：

- 把完整 JSON 直接贴进聊天，或者只给原始结果不给落盘路径

最终正确方式：

- 面向交付时优先 `--format csv --output <path>`
- 对话里只保留：
  - 文件路径
  - 记录总数
  - 耗时
  - 关键限制和口径

教训：

- 可读性、可下载性、可复核性，本身就是交付质量的一部分

### 9. 稳定结论要回填到长期资产，而不是停留在单次对话

导致问题的做法：

- 同类问题每次重头探索
- 经验只停在 session 和记忆里，没写进项目文档或配置链路

最终正确方式：

- 稳定经验写入长期文档
- 用 `AGENTS.md` 明确把经验文档加进默认加载链路
- 对业务口径同步更新 skill、playbook 或规则配置

教训：

- 复盘只有进入默认执行上下文，才真正产生复利

## 二、我的偏好与理念提炼

### 1. 产品与系统设计理念

- 最终用户入口偏向自然语言，但稳定执行底座必须是 CLI/workflow，而不是 prompt 直接拼逻辑
- 高价值业务语义应优先固化到代码和规则里，skill 负责翻译，不负责长期承载核心口径
- 高频语义应先覆盖最常见、最稳定、最可测的一小组，长尾条件允许回退到原生 `--where`
- 工具要服务真实业务动作：bug 导出、QA 评审、售后分析、risk scan、regression queue，而不是只做技术演示

### 2. 运行耗时与性能偏好

- 用户会明确要求记录“整个流程”的耗时，而不是只看查询语句本身
- routine 路径偏好快路径，避免默认 history fan-out
- 任何“是否值得走慢路径”的判断，最好有可复核时间数据
- 对大导出，用户接受分钟级任务，但要求可见、可落盘、可核对

### 3. 口径与数据语义偏好

- 先锁定口径，再拉数
- 默认 scope、状态分组、高风险阈值都应以 `workflow_rules.yaml` 为事实来源
- “全量 bug”不等同于“全实例所有 bug”，而是当前项目默认三团队范围内的全状态 bug
- “当前 bug”也不默认等同于 open bug
- “有变更记录”这种自然语言，如果可以由主字段表达，应优先走主字段定义

### 4. 编码与实现偏好

- 稳定入口优先，不喜欢为了一个需求新增平行入口
- 结构化过滤、默认 scope 合并、字段集定义应落在代码里，而不是依赖会话解释
- 修改后要补文档、补规则、补可复用说明，避免知识只留在代码 diff 或对话历史中
- 中文文档是首选归档形式，且要能被后续会话直接复用

### 5. 交付与沟通偏好

- 输出偏好结论先行、路径明确、少铺垫
- 喜欢文件化交付：CSV、Markdown、规则文档、skill 文档、配置引用
- 说“继续”“下一步”时，默认是在当前链路上推进，不需要重新做大段背景解释
- 聊天里要高信号摘要，低信号大正文落文件

### 6. 个人风格档案

- 语言偏好：中文、直接、结构化、面向执行
- 决策偏好：先收口径，再看实现，再给结论
- 质量偏好：证据优先于推断，可审计性优先于表面“好像完成了”
- 协作偏好：能直接推进就推进，真正高风险或需要写权限时再请求确认

## 三、可复用规则清单

### 启动规则

1. 进入本项目先读 `AGENTS.md`、`docs/codex-project-experience-playbook.md` 和本文档
2. 只要是 QA/bug 业务任务，再读 `skills/targetprocess-qa/SKILL.md`
3. 涉及 live 前，先检查当前会话是否真的有可用凭据，而不是假设上一个会话成功过

### 命令与入口规则

1. 稳定入口始终是 `python -m tp_codex.cli`
2. 业务任务优先 workflow 命令
3. `entities list` 和 `schema snapshot` 只用于调试、探查和 schema 发现
4. 默认保持只读，不增加 create、update、transition

### 过滤与语义规则

1. “新增”默认映射 `CreateDate`
2. “有变更记录”默认映射 `ModifyDate`
3. “未闭环”默认按 `workflow_rules.closed` 的补集定义
4. “全量 bug”默认是默认三团队 scope 内的全状态 bug
5. 高语义频次过滤优先落在结构化代码规则里，长尾条件才回退到原生 `--where`
6. 时间过滤优先使用 `DateTime.Parse("YYYY-MM-DD")`

### 性能与耗时规则

1. 大 live 拉取前先跑 `healthcheck`
2. `triage-view`、`risk-scan`、`review-export` 默认 `--history-mode off`
3. 只有显式请求嵌入 history 明细时才用 `--history-mode full`
4. 大导出默认记录开始时间、结束时间、总耗时、最终条数和 where 子句

### 交付规则

1. 大结果优先导出文件，不在对话里输出巨型 JSON
2. 最终回复至少给出文件路径、核心条数、耗时和关键口径
3. 对不完整结果必须明确写出 warning 或限制，不把 partial 结果伪装成完整结果

### 文档与继承规则

1. 新稳定经验先写文档，再依赖记忆
2. 文档写完后，要把绝对路径挂进 `AGENTS.md`
3. 对话里确认过的长期规则，后续不要重复试探，应先按默认规则执行
4. 修改文档或配置后，必须回读校验，确认路径和内容能被后续会话直接引用

## 后续维护方式

- 新增稳定坑点时，追加到“一、执行经验总结”
- 新增偏好或设计理念时，追加到“二、我的偏好与理念提炼”
- 新增默认可执行规则时，追加到“三、可复用规则清单”
- 若后续新增全局 `~/.codex/AGENTS.md` 规则，也应继续保留本仓库 `AGENTS.md` 对本文档的绝对路径引用，避免配置链路只剩单点
