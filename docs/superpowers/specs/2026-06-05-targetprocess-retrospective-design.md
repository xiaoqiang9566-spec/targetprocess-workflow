# Targetprocess 复盘与经验沉淀 Skill 设计

## 状态

状态截至 `2026-06-05`：

- 复盘素材入口已确认，可访问 `sessions`、`archived_sessions`、线程状态库和日志库。
- 项目经验内容已经部分沉淀在 `docs/codex-project-experience-playbook.md`。
- 当前项目缺少一个明确指导 Codex 执行“历史复盘 -> 规则提炼 -> 文档回填”的独立 skill。
- 本文档定义新增 `targetprocess-retrospective` skill 的设计，不在本文档中直接实现该 skill。

## 目标

为 `D:\3681\Documents\Targetprocess` 新增一个项目内复盘 skill，用于指导 Codex：

1. 检索项目相关的 Codex 对话记录与执行日志。
2. 从原始证据中提炼执行经验、用户偏好和可复用规则。
3. 将稳定规则按职责分别回填到项目经验文档、业务 skill 或入口说明。

## 问题

当前项目已经积累了足够多的历史执行证据，但沉淀方式仍然偏“结果导向”，缺少一个稳定的复盘方法入口。

已确认的现状包括：

- `C:\Users\3681\.codex\sessions` 下存在 `36` 个 session 文件。
- `C:\Users\3681\.codex\archived_sessions` 下存在 `12` 个 archived session 文件。
- `C:\Users\3681\.codex\state_5.sqlite` 中存在 `48` 条线程记录。
- `C:\Users\3681\.codex\logs_2.sqlite` 中存在 `64581` 条日志记录。
- 与 Targetprocess 直接相关的主线会话主要集中在 `2026-03-19` 以及 `2026-06-03` 至 `2026-06-05`。

问题不在于“有没有历史”，而在于“未来 Codex 如何稳定地利用这些历史而不重复踩坑”。现有项目经验文档记录了大量结论，但没有把“如何做复盘”本身变成一个可触发、可复用的 skill。

## 决策

新增一个项目内 skill：

- 路径：`D:\3681\Documents\Targetprocess\skills\targetprocess-retrospective\SKILL.md`
- 名称：`targetprocess-retrospective`

该 skill 只负责一类工作：

- 复盘历史会话和执行日志
- 提炼执行经验和长期规则
- 回填项目经验资产

该 skill 不负责：

- 业务数据拉取
- bug 查询、导出、差异分析
- report 链接解析
- 任意 Targetprocess 业务工作流执行

这些业务动作继续由 `skills/targetprocess-qa/SKILL.md` 负责。

## 设计原则

### 1. 职责分离

项目内形成两个清晰入口：

- `targetprocess-qa`：负责“怎么做业务读取和交付”
- `targetprocess-retrospective`：负责“怎么做历史复盘和规则沉淀”

### 2. 证据优先

复盘结论必须来自当前可访问的真实证据，而不是记忆或猜测。

### 3. 模式提炼优先于原文搬运

skill 应优先提炼：

- 失败模式
- 正确做法
- 可复用规则

而不是复制长段会话或日志原文。

### 4. 回填按职责落点

不同类型的结论必须写入不同位置，避免所有经验都堆进一个文件。

## 证据来源优先级

新增 skill 应固定以下输入源优先级：

1. 当前项目上下文
2. 项目相关线程索引
3. 原始会话证据
4. 执行级日志

### 1. 当前项目上下文

优先读取：

- `AGENTS.md`
- `docs/codex-project-experience-playbook.md`
- `skills/targetprocess-qa/SKILL.md`
- `config/workflow_rules.yaml`
- `docs/superpowers/specs/*.md`
- 相关 live notes、readiness checklist、README

作用：

- 确认当前项目已经沉淀的规则
- 识别哪些经验已存在、哪些经验缺失
- 避免新结论与现有项目口径冲突

### 2. 项目相关线程索引

优先使用：

- `C:\Users\3681\.codex\state_5.sqlite` 的 `threads` 表
- `C:\Users\3681\.codex\session_index.jsonl`
- 线程标题、`preview`、`cwd`

作用：

- 先做粗筛，定位与项目直接相关的线程
- 减少对所有历史会话做无差别全量扫描

### 3. 原始会话证据

读取来源：

- `C:\Users\3681\.codex\sessions`
- `C:\Users\3681\.codex\archived_sessions`

作用：

- 提取用户请求、关键决策、失败做法、修正路径和最终稳定口径

### 4. 执行级日志

读取来源：

- `C:\Users\3681\.codex\logs_2.sqlite`

作用：

- 识别错误模式、重试模式、工具使用模式、环境问题模式

限制：

- 日志只用于补充“行为模式”
- 不直接作为业务结论正文来源

## 复盘流程

skill 的执行流程固定为六步。

### 第一步：确定复盘范围

默认先锁定当前项目相关线程，而不是直接全量扫描所有 Codex 会话。

默认筛选信号包括：

- `cwd` 包含 `Targetprocess`
- 线程标题或 `preview` 包含 `Targetprocess`、`tp_codex`、`review-export`、`workflow_rules`、`history-mode`

只有当项目内证据明显不足时，才扩展到更广泛的全局历史。

### 第二步：读取原始会话证据

对筛出的目标线程读取原始 JSONL，提取四类信息：

- 任务目标
- 关键决策
- 失败做法
- 修正后的稳定做法

不做会话原文复写，不按时间线逐句重述。

### 第三步：用日志补充执行模式

日志用于识别如下模式：

- 权限或环境判断错误
- 工具调用链路绕远
- 重试与恢复行为
- 配置覆盖问题
- 读写边界判断问题

日志不用于生成大段正文，不直接作为用户可见文档内容。

### 第四步：抽象为三层沉淀

每次复盘至少产出三层结论：

1. 执行经验
2. 用户偏好与理念
3. 可执行规则

其中：

- 执行经验回答“哪些做法导致问题，正确做法是什么”
- 用户偏好与理念回答“用户如何定义正确的口径、交付和验证”
- 可执行规则回答“未来 Codex 可以直接遵循什么规则”

### 第五步：按职责回填

回填矩阵固定如下：

- 项目级长期经验：写入 `docs/codex-project-experience-playbook.md`
- 业务工作流口径：写入 `skills/targetprocess-qa/SKILL.md`
- 复盘方法与流程：写入 `skills/targetprocess-retrospective/SKILL.md`
- 入口级加载说明：保留在 `AGENTS.md`，不堆积大段经验正文

### 第六步：完成前验证

每次复盘结束前至少检查：

1. 结论是否能追溯到真实证据来源。
2. 新增规则是否与当前项目文档冲突。
3. skill 职责是否与 `targetprocess-qa` 混淆。
4. 敏感信息是否被直接搬运到文档。

## 脱敏规则

新增 skill 必须显式禁止以下内容进入经验文档或最终回答：

- token
- cookie
- 认证头
- 完整私有 URL 参数
- 浏览器请求头
- 账号标识
- 原始大段会话正文
- 原始大段日志正文
- 不必要暴露的业务敏感原文

允许保留的内容仅包括：

- 任务主题
- 失败模式
- 正确做法
- 可复用规则
- 证据位置，如线程 ID、session 文件路径、文档路径

skill 应明确要求 Codex 用“模式归纳”替代“原文搬运”。

## 文档结构设计

`targetprocess-retrospective` skill 建议包含以下结构：

1. 适用场景
2. 不适用场景
3. 输入源优先级
4. 复盘流程
5. 脱敏与边界
6. 回填矩阵
7. 验证清单
8. 建议输出格式

其中“建议输出格式”应要求复盘结果至少覆盖：

- 执行经验总结
- 用户偏好与理念提炼
- 可复用规则清单
- 已回填位置
- 未验证范围

## 目标文件清单

本设计落地后，目标文件包括：

- 新增：`skills/targetprocess-retrospective/SKILL.md`
- 更新：`docs/codex-project-experience-playbook.md`
- 按需更新：`skills/targetprocess-qa/SKILL.md`
- 保持入口引用：`AGENTS.md`

## 非目标

本设计当前不包含以下内容：

- 新建全局通用复盘 skill
- 修改全局 `C:\Users\3681\Documents\Codex\codex-experience-playbook.md`
- 自动生成跨项目统一复盘报告
- 替代现有 Targetprocess 业务 skill

如果后续要做全局版本，应在项目内版本稳定后再抽象。

## 风险

- 项目经验文档与复盘 skill 可能出现重复描述。
- 线程粗筛关键词如果过窄，可能漏掉相关会话。
- 如果只读线程标题而不读原始 JSONL，容易提炼出过弱结论。
- 如果日志使用不当，容易把底层噪声误当成稳定规则。

## 验证计划

文档完成后至少验证以下事项：

1. `docs/superpowers/specs/2026-06-05-targetprocess-retrospective-design.md` 已写入。
2. 文档不存在临时标记、空白章节或自相矛盾描述。
3. 文档中的职责划分与当前 `skills/targetprocess-qa/SKILL.md` 一致，不把复盘职责混入业务 skill。
4. 文档中的回填矩阵与 `AGENTS.md`、项目经验文档当前加载方式兼容。

## 后续建议

在本文档经用户审阅通过后，下一步应：

1. 新增 `skills/targetprocess-retrospective/SKILL.md`
2. 将本文档中的方法规则压缩为可执行 skill 内容
3. 对项目经验文档做最小必要更新，避免重复
4. 复核 `AGENTS.md` 是否仍只承担加载入口职责

## 备注

当前工作目录下 `git` 不可用，`git rev-parse --show-toplevel` 返回“not a git repository”。因此本阶段只能完成设计文档写入和自检，不能完成文档提交。后续如果仓库环境恢复，再补提交动作。
