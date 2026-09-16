# 在 Claude Code 中使用 rtl-dv-review

[English](rtl-dv-review.md) | 简体中文

## 功能与使用前提

用于检查 diff、分支、RTL 模块或 DV 环境中的功能缺陷和验证盲区。
这是评审 skill，不是实现、仿真或 sign-off 命令。模型会读取相关代码、规格和
已有证据，不是只看孤立片段。

在消费项目目录中打开 Claude Code。项目的 `.claude/skills/rtl-dv-review/`
必须包含对应版本的 `SKILL.md` 和三份 `references/` 文件，可以是已部署副本，
也可以是项目管理的链接。只更新 kit checkout 不会自动更新项目中已有的副本。

以下示例输入 **Claude Code 对话框，不是终端 shell**。日常 review 不需要
Python 命令；将占位符替换为真实路径或 ref。找不到 skill 时，请维护者检查部署
路径、kit 版本和项目既有部署方式，更新后重新打开 Claude Code 会话。
维护操作见 [skill 同步说明](command-reference.md#sync)，不需要每次 review 都执行。
不要盲目 force-sync 覆盖项目自定义内容，也不要随意替换已有托管链接。

## 静态 review 与 EDA 验证的区别

默认进行只读代码分析，可以读取指定的已有日志和报告；不自动编译、仿真、回归、
生成覆盖率、综合或执行 CDC。读取已有报告不等于启动新 EDA 任务。
要求 review 也不代表允许改源码、写报告文件或发布 PR/MR 评论。

| 需求 | 选择 | 结果含义 |
| --- | --- | --- |
| 查逻辑 bug、验证盲区 | `rtl-dv-review` | 有代码证据的静态发现，不是工具验证 |
| 使用项目 VCS-only lane 检查 RTL | 注册 Bazel `soc_lint` | RTL 编译/展开与 lint，不检查 DV testbench |
| 检查 DV 环境是否能编译 | 注册 Bazel `soc_comp` | 所选 testbench 的编译/展开，不证明运行正确 |
| 验证具体运行场景 | 选择后调用注册 `soc_sim` | 指定 test/config/seed 的结果，不代表完整覆盖 |
| 调查已有失败 | `rtl-dv-debugging` 与相关 debug tools | 围绕已有证据诊断原因 |
| 核对交付声明和 artifacts | `rtl-dv-evidence` | 检查证据一致性与完整性，不产生新的设计证明 |

以上工具名对应项目 Bazel contract。执行前确认启用的 server/schema 和目标映射，
不能把同名 Make 工具当成同一后端。EDA 必须遵循项目授权和注册 MCP 工具要求；
调用 skill 不会自动获得执行权限，也不能消除工具或 license 的前置依赖。

## 可直接复制的示例

### 当前未提交的改动

```text
/rtl-dv-review Review my uncommitted RTL and DV changes, including relevant untracked files. Focus on functional bugs and verification blind spots. Do not modify files or run EDA tools.
```

### 当前分支

将 `<base-ref>` 替换成实际目标，例如 `github/main` 或 `origin/main`。
这个例子检查已提交的分支差异，不自动包含工作区未提交改动。

```text
/rtl-dv-review Review changes from the merge-base of <base-ref> and HEAD to HEAD. Record both revisions. Separate newly introduced defects from pre-existing issues. Inspect relevant dependencies as needed. Do not run EDA tools.
```

### RTL 模块

```text
/rtl-dv-review Review <rtl-module-path> against <spec-path>. Focus on backpressure, simultaneous FIFO push/pop, supported parameter boundaries, and reset or flush with outstanding transactions. Report concrete failure scenarios rather than style preferences. Keep the review read-only; do not run EDA tools.
```

### DV environment

```text
/rtl-dv-review Review <dv-env-path>. Focus on monitor sampling, transaction ownership, scoreboard matching, reset handling, TLM connections, and test completion. Follow affected dependencies only as needed. Separate confirmed defects from missing validation. Do not edit files or run EDA tools.
```

### Assertions / coverage 与已有报告

```text
/rtl-dv-review Review <assertion-or-coverage-file> using <spec-path> and the existing report at <report-path>. Check sampling, reset gating, assertion activation and coverage meaning. Verify the report's source/configuration identity. Missing activation evidence is not proof of vacuity. Do not run simulation or modify exclusions.
```

### Review 后选择验证，可以多选

```text
List numbered, targeted validation options for the findings. For each, show the finding addressed, registered MCP tool, exact target/test/configuration, expected evidence and any known runtime or prerequisite. Allow multiple selections. Do not execute anything yet.
```

看过实际选项后，例如回复：

```text
Run only options 1 and 3 through the registered MCP tools with the listed targets and configuration. Do not add other checks. Report each option separately with status, source revision, tool/target/test/seed where applicable, artifact paths and remaining limitations.
```

编号指当次给出的选项，不是固定工具编号。缺少必要参数时，先补齐对应任务的参数，
不要编造 target、seed 或耗时估计。回归、coverage、综合、CDC 始终是单独选择项，
不会因为 review DV 就自动执行。

## 结果应该包含什么

先列问题，按严重度排序。每项包含 priority、`path:line`、触发条件、证据、
错误结果、影响与最小修正方向。随后说明检查范围/版本、假设、已执行检查及未验证项。
示例格式如下，仅为说明，不是真实项目发现：

```text
[P1] <scoreboard-file>:<line>
Trigger: the producer reuses a transaction before the queued handle is compared.
Evidence: the queue retains the same handle that the next sample mutates.
Impact: earlier observations are overwritten, masking or inventing mismatches.
Correction: preserve transaction ownership or snapshot retained data.
Validation: a directed two-transaction test; not executed during this review.
```

如果 subscriber 立即消费数据、不保留对象，不能只因为没有 clone 就报告 bug。
同样，无效数据未 reset、合法的旧式代码风格也不自动构成缺陷。
“未发现 actionable findings”仅表示在声明范围内没有发现；编译成功也不是 sign-off。
AI 可能漏报或误报，工程师应先核对证据，再决定是否修改。

## 如何更高效，以及已验证到哪里

优先提供 diff 或具体模块及有关规格，避免默认全仓库扫描。已有报告和配置一次提供
清楚即可。skill 根据任务按需读取 RTL、DV/UVM、assertion/coverage 清单。
先 review，再选择能解决具体疑问的最小验证集合。

本地核心测试验证了 catalog、部署与参考文件完整性。增强指令尚未进行 ETX 原生
Claude Code 的行为 benchmark，因此没有发现率、误报率或 token 节省的实测结论。

后续相似 skills 的说明结构参见
[Skill 使用文档更新清单](skill-usage-documentation.md)。
