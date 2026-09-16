# RTL/DV 工作流 skills 使用指南

[English](rtl-dv-workflows.md) | 简体中文

本文说明本次更新后保留的 **五项独立能力**，不再展示重复的 context 入口，
不是要求每次都依次调用的固定流程。所有示例输入 Claude Code 对话框，
不是 shell；日常使用不需要 Python 命令。把尖括号占位符替换为实际路径、
任务、目标或编号。

## 快速选择

| 入口 | 什么时候用 | 默认边界 |
| --- | --- | --- |
| [rtl-dv-kit](#rtl-dv-kit) | 项目接入、查配置、补齐任务所需事实、选择能力 | 只读，不改配置，不执行 EDA |
| [dv-engineering](#dv-engineering) | 规划或实现 DV test、sequence、checker、environment | 规划不改文件；实现不自动仿真 |
| [rtl-dv-evidence](#rtl-dv-evidence) | 核对验证声明、报告和交付证据 | 审阅只读；明确要求后才生成证据文件 |
| [rtl-dv-regression](#rtl-dv-regression) | 选择检查集合、分析或比较多次运行结果 | 分析不自动重跑；执行限于已选择项目 |
| [rtl-dv-debugging](#rtl-dv-debugging) | 分析一个已有故障的原因 | 默认只诊断；修复和重跑需要相应授权 |
| [rtl-dv-review](#rtl-dv-review) | 检查代码正确性与验证盲区 | 独立的只读代码评审，不是执行检查 |

debugging 与 regression 共用失败分类，但职责不同：前者追踪故障因果，
后者处理运行集合、分组、统计与比较。evidence 核对“结论有没有证据支持”，
不替代代码 review。整套 kit 还有其他 skills，不在本文范围内。

## 使用前提与维护命令

- 在消费项目根目录启动 Claude Code。项目规则和配置文件（通常为
  `.ai/project.toml`）决定路径权限、目标映射和执行要求。
- 完整部署应提供 `.claude/skills/<skill-name>/SKILL.md` 及相关参考文件，
  可以是同步副本或托管链接。只更新 kit checkout 不会更新已复制的旧文件。
  最小安装可以只有 `rtl-dv-kit`，它本身包含完整的上下文与路由说明。
- skill 存在不代表 MCP server、simulator、license、runner 或同名子代理可用。
  只在需要时检查注册的 `get_project_profile`、`plan_task` 等工具。
  已有事实不变时，不重复执行整套 doctor/plan/inspect。
- 项目要求 MCP-only 时，工具不可用就报告对应检查受阻，不能退回 shell。
  只有项目明确允许时，才能使用已声明的 wrapper。
- 执行前按需确认 revision、target、test、seed、simulator、工作目录和输出位置；
  源码分析不需要为了填表而编造这些参数。
- `dv-engineer`、`commander` 等 role 名称是职责指引，不代表一定装有同名
  Claude 子代理。必要时在当前会话应用指引，不自动创建或安装代理。

维护者可使用下表入口；它们不是日常 review 的前置步骤，也不是 EDA 授权：

| 维护任务 | CLI 入口 |
| --- | --- |
| 查看可用 skills | `claude-kit list skills` |
| 检查项目配置 | `claude-kit doctor --project-root . --strict` |
| 分析任务路由 | `claude-kit plan --task "<task>"` |
| 同步项目 skills | `claude-kit sync --project-root .` |
| 验证证据 JSON | `claude-kit evidence check --strict`，补齐项目与文件参数 |

同步默认保留已有文件，不代表旧副本已经刷新。已有项目应沿用其部署方式；
先检查自定义文件和托管链接，不能盲目 force-sync。新版本把原来的模板入口
移到统一的 skill 资源目录，最小安装、完整同步和共享挂载都使用同一实现。
若共享挂载发现项目自有 `rtl-dv-kit` 文件冲突，会保留文件并报告冲突，
不要删除自定义文件来绕过检查。维护详情见 [命令参考](command-reference.md)。

## 状态、证据与 sign-off

| 状态 | 含义 |
| --- | --- |
| passed | 有证据表明所选检查运行完成，预期结果与所需产物支持通过 |
| failed | 检查运行后明确失败；保留首个有因果意义的错误 |
| blocked | 所选操作受缺少输入、工具、license、权限或依赖等条件阻塞 |
| skipped | 有意未选择或超出本次范围，说明原因 |
| unknown | 证据不足以判断，包括尚未完成、报告截断或运行身份不明 |

“not run”不能说成通过。意图不执行可记 skipped，前提不满足可记 blocked；
若连是否完成都不确定，保持 unknown。进程 exit 0、工具注册成功或报告文件存在，
都不能单独证明功能正确。

**实际运行结果和证据文件是否完整是两件事。** 如果结果已证明 passed/failed，
但缺少完整 argv，应保留已知结果并报告记录缺口。严格校验只检查记录契约、
路径/权限及产物引用等，不认证每条历史声明，更不是 design sign-off。
模型和工程师仍需核对实际源码版本、配置、运行身份与输出。

外部日志通过配置的 `discover_regression_artifacts` 和
`read_regression_artifact` 读取。证据 JSON 当前的 artifacts 字段要求
项目内相对文件路径，不能直接放绝对外部路径。若明确要求生成文件，可在已授权
位置保存带来源的回执或摘录；否则报告表示方式/校验缺口，不伪造路径或复制数据。
只读审阅外部证据不要求先生成本地文件。缺失运行身份可能限制结论；仅缺本地回执
不能把原本已知的运行结果改成 unknown。

<a id="rtl-dv-kit"></a>
## rtl-dv-kit：统一上下文与路由

适用于不知道项目配置在哪里、该选什么能力，或者已有事实可能过期的情况。
只读取任务所需的缺失事实，返回配置/源码来源、范围、映射、假设和前置缺口；
不自动改 profile、权限或 MCP 配置。已知上下文的直接修改不需要先调用它。

~~~text
/rtl-dv-kit Discover the configured RTL/DV profile and route this task: <task>. Reuse facts already in the session, resolve only missing or stale facts, and return the smallest useful next skill or registered tool. Do not modify the profile, install anything, add servers, or run EDA.
~~~

~~~text
/rtl-dv-kit The task is <task>. Check only the configuration and bounded task facts that affect this work, separate observed facts from assumptions, and list any missing prerequisites. Do not start a mandatory doctor/plan/inspect chain, mutate project configuration, or execute checks.
~~~

**预期输出：** 当前项目/checkout、相关配置及源码、适用 skill/tool、已知版本、
重要假设与缺失项。只部署了最小入口时，应说明其他能力不存在，不假装已调用。
此入口按需使用；不是所有工作前都要重复运行的“总检查”。

## 旧入口迁移

`rtl-dv-context` 已合并到 `/rtl-dv-kit`，不再出现在 kit 的 skill 列表或新部署的
slash commands 中。旧 CLI/MCP 请求中的 ID 仍可在内部解析，但不是一个独立 skill。

重新 attach 时，只移除指纹仍匹配的 kit 管理的旧符号链接，不删除链接目标。
已修改的链接或项目自有目录会保留，并在 `retired_managed_paths` 中报告。
旧版复制式安装的文件不会被 sync 自动删除：先检查和保存自定义内容，再将旧
`SKILL.md` 移出 `.claude/skills`，改用统一入口。不要用强制同步覆盖自定义配置。
本次没有修改 XinAnRiver 的已部署文件；更新 kit 不等于完成消费项目迁移。

<a id="dv-engineering"></a>
## dv-engineering：DV 规划与实现

用于设计或修改 tests、sequences、drivers、monitors、scoreboards、assertions
和 coverage。先区分“只规划”与“实际实现”，将相关需求映射到激励、观测、
期望结果和失败诊断，不必给每个小改动强加所有场景类别。

实现一个 DV 改动：

~~~text
/dv-engineering Implement the focused DV change for <target> covering <scenarios>. Inspect relevant DUT and bench conventions, keep stimulus/observation/checker ownership explicit, and report changed files and static checks. Do not run simulation, regression, coverage, synthesis or CDC.
~~~

只要方案，不改代码：

~~~text
/dv-engineering Plan a focused DV change for <target> and map <requirements> to positive, boundary, negative, reset and recovery scenarios where applicable. Show driver/monitor/scoreboard/reference-model/coverage responsibilities and the smallest static checks. Do not edit files or run EDA.
~~~

列出可多选的验证菜单：

~~~text
/dv-engineering Present numbered validation choices for this change, including the registered project MCP tool, target/test/seed/simulator, expected evidence and known cost or unknown cost. Allow multiple selections in engineer order; do not execute until I explicitly select items or delegate the selected run to an available commander.
~~~

**预期输出：** 修改文件与原因、场景与检查器变化、静态检查发现，以及分类验证菜单。
选定后按顺序逐项报告结果；失败依赖导致后续不能执行时，也要单列为 blocked。
默认新测试的 simulation/regression 是 not run，而不是 passed。

RTL-only lint 不是 DV syntax check；应选项目实际的 testbench compile 工具。
已定义测试/covergroup 不代表已经运行或覆盖。不要因为改了 DV 环境，就自动附带
regression、coverage、syn、CDC。已明确批准的检查无需重复确认；新范围才重新选择。

<a id="rtl-dv-evidence"></a>
## rtl-dv-evidence：验证声明与证据

用于审阅“说通过了”是否有可追溯依据，或者准备明确要求的证据文件。
默认审阅只读，不修复源码、不执行 EDA、不清理日志、不批准 waiver 或发布评论。

审阅现有声明：

~~~text
/rtl-dv-evidence Audit the verification claims for <task> using the current project files and authorized existing artifacts only. Bind each claim to source revision, target/test/seed/simulator/configuration, run identity and artifact location; classify every check as passed, failed, blocked, skipped or unknown. Do not run EDA or edit files.
~~~

检查现有 evidence JSON：

~~~text
/rtl-dv-evidence Validate <evidence-file> with the registered review_evidence tool in strict mode for schema and allowed path structure. Separately audit whether identities, exact argv, statuses and artifact references are truthful and belong to the claimed run; report tool-validation errors separately from audit findings. Do not treat strict validation as design sign-off.
~~~

明确创建或更新证据文件：

~~~text
/rtl-dv-evidence Create or update the project-local evidence file at <destination> for <task>, only as explicitly requested. Preserve actual results and exceptions; use authorized project-local receipts for external logs, and never invent paths, argv, run IDs or passing results. Do not rerun checks.
~~~

**预期输出：** 每项声明的实际状态、支持位置、矛盾、过期或缺失证据、剩余风险。
生成文件时另报路径和严格校验结果。失败记录也可以是合法的 evidence JSON；
文件校验通过不表示里面记录的运行都通过。

按需读取小段日志。旧 revision 的结果只能证明旧 revision。
不要为了让 strict 校验变绿而编造 simulator argv、删除失败项或放宽权限；
缺少命令记录导致 strict 失败时，单独报告这个缺口。

<a id="rtl-dv-regression"></a>
## rtl-dv-regression：运行集合、分组和比较

用于选择有限检查集合，或分析已有批量结果；两者默认不自动执行。
不要只按文件修改时间挑“最新结果”，要核对 run ID、源码、配置、test/seed 和来源。
客户端超时不代表远程任务停止，应先检查已有 job，不能立即重复提交。

分析已有结果：

~~~text
/rtl-dv-regression Triage the existing result set at <artifact-or-run-list> for <task>. Reuse current selections and preserve the first causal error; report target/test/configuration, source revision, seed, simulator, working directory and run identity. Do not execute new checks.
~~~

执行已经明确选择的项目：

~~~text
/rtl-dv-regression Run only selections <numbers> that I explicitly approved through the registered project MCP interface. Preserve engineer order and report every item separately; if a retry is requested, use a declared retry budget and record each retry as a new linked run without changing the original identity. Do not add wider slices, use a shell fallback, or clean up artifacts.
~~~

比较 baseline 与 candidate：

~~~text
/rtl-dv-regression Compare baseline run <run-a> with candidate run <run-b> only after verifying the complete known identity of both: source revision, target, test/configuration, seed policy, simulator, working directory and run/artifact identity. Intentional source-revision differences are allowed when the baseline/candidate relationship is explicit; state every relevant difference and limit conclusions to comparable dimensions. If identity or provenance is missing, report unknown or blocked instead of choosing by modification time or inventing argv.
~~~

**预期输出：** 每项运行/选择的状态、带分母的统计、失败分类、代表性日志、离群项
和剩余缺口。先按首个有意义的错误分组，再对代表性失败做深入诊断，避免扫描每份
完整日志。相同错误文本不证明根因相同，后续通过也不能抹掉原来的失败或 flaky 记录。

允许比较不同 revision 的 baseline/candidate，但必须说明源码差异，且其他维度
具有可比性。新增/缺失 tests、未完成运行和不同 coverage 指标要分开统计。
一次明确选择的运行不需要另加“重试预算审批”；只有请求重试时才限定次数和范围。
不擅自换 seed、扩大 slice 或删除 logs、FSDB、VDB、lock 文件。

<a id="rtl-dv-debugging"></a>
## rtl-dv-debugging：已有故障的原因分析

用于编译、展开、运行、协议、断言、scoreboard、timeout、coverage 等已有问题。
从有来源的日志和代码出发，区分直接观测、推断与未验证假设，不急着归咎于 RTL。
默认只诊断；缺少 waveform 不会自动授权生成新 waveform 或启动仿真。

只诊断：

~~~text
/rtl-dv-debugging Diagnose the existing failure in <log-or-session>. Verify its project, source revision, target/test/seed, simulator/configuration, working directory, run identity and first meaningful error; state supported causes or remaining alternatives and do not modify files or rerun anything.
~~~

读取已有调试会话：

~~~text
/rtl-dv-debugging Inspect the existing debug session <session-id> and evidence owned by <owner-or-project>. Read only bounded logs/waveform windows needed for <failure>; preserve database identity and session ownership, and report missing or optimized-away data as a gap. Do not close or overwrite sessions you do not own.
~~~

明确要求修复，但暂不重跑：

~~~text
/rtl-dv-debugging I explicitly request a fix for <path-or-cause>. Make only the smallest authorized change, then present a separate rerun selection with target/test/seed/tool and expected evidence. Do not rerun until I select it, and preserve the original failure plus before/after identity.
~~~

**预期输出：** 有支持的根因或剩余候选、置信依据、首个因果位置/时间、
预期与实际行为，以及能区分候选原因的最小检查。如果已授权修复，再列修改文件与
修复前后证据；尚未重跑就明确写 not run。

只查询相关信号和时间窗口。旧构建的 FSDB、未 dump/被优化掉的信号、X/Z 和不同采样
时刻都限制结论；缺失值不能当成零，也不能凭源码猜出“实测”内部信号值。
保留其他任务的 session，只关闭本任务创建的会话。批量分组交给 regression。

<a id="rtl-dv-review"></a>
## rtl-dv-review：相邻的代码评审能力

用于检查 diff、模块或 DV 环境的正确性；与故障诊断、证据文件审阅不同。
详细说明见 [review 指南](rtl-dv-review.zh-CN.md)。

~~~text
/rtl-dv-review Review <diff-or-path> against <spec-or-base>. Keep the review read-only, trace concrete triggers to incorrect outcomes, separate confirmed defects from hypotheses and verification gaps, and do not run EDA or edit files.
~~~

~~~text
/rtl-dv-review After the read-only review, list numbered targeted validation options for the findings. For each, show the registered MCP tool, target/test/configuration, expected evidence and missing prerequisites; allow multiple selections but do not execute anything yet.
~~~

**预期输出：** 按严重度排序的问题、文件行号、触发条件、证据、影响和最小修正方向，
以及评审范围和未验证项。没有发现问题不等于 sign-off。

## 高效使用与验证范围

- 优先给具体模块、diff、日志窗口或运行集合，不默认全仓库扫描。
- 已知事实复用，只有相关源码、配置、checkout 或需求变化时才更新上下文。
- 按需读取 skill 的参考文件；本长篇教程供工程师查阅，不是每次任务默认加载。
- 独立检查可按已选择范围继续；依赖失败的检查说明原因，不静默跳过。
- 本地测试：核心 40 项、CLI 15 项、新增部署/路由 7 项、MCP 7 项通过；
  部署测试共 20 项，其中 18 项通过、2 项在 Windows 不适用而跳过。
  已验证 wheel 包含统一入口和参考文件，并且不含退役模板。
- 另完成 8 个场景的独立指令推演。这不是 ETX 原生 Claude Code 测试，也没有执行
  EDA，因此不声称准确率、误报率、token 或耗时已经得到实测改善。

## 导航

- [项目 README](../README.zh-CN.md)、[命令参考](command-reference.md)
- [工具选择指南](tool-selection.zh-CN.md)
- [Skill 使用文档维护清单](skill-usage-documentation.md)
