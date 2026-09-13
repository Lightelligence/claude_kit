# RTL/DV 工程师的 Claude Code 工具选择指南

[English](tool-selection.md)

以项目 `.mcp.json` 和 Claude settings 为准：有 skill、源码或目录，不代表 server 已启用；能列出工具，也不代表业务运行通过。

## 我应该用哪个工具？

| 工作目标 | 优先入口 | 不能混淆的事情 |
| --- | --- | --- |
| 理解模块、规划改动 | kit profile/context + 对应 RTL/DV skill | 计划不是验证结果 |
| 查定义、引用、符号 | 项目 language-server MCP | 导航不是编译；空结果不能证明符号不存在 |
| 检查可综合 RTL | 项目 RTL-only lint | 不检查 DV testbench |
| 改 DV 后只编译检查 | compile/elaboration MCP | 编译通过不代表 scoreboard、assertion 运行通过 |
| 运行指定 test | simulation MCP | 不等于回归；若已包含编译，不要重复 compile |
| 分析已有失败 | 指定 run 的日志，再按需查询波形 | 不自动重跑、换 run 或读取整份巨型日志 |
| 查询已有 FSDB/design DB | xverif debug guide → schema → managed session/query | 不生成新的仿真数据库 |
| 查询已有 VDB | xverif coverage tools | 与 build server 执行 coverage 不同 |
| bit 计算、解释 SVA | xverif bit/SVA | 不需要为了简单计算打开波形数据库 |
| 生成寄存器/RAL/CRG | 已启用的专用 generator | 不手改生成的 RTL |
| 综合、CDC、物理实现 | 明确选择的项目 MCP lane | 不自动成为每个 DV 改动的必做项 |
| 交付检查 | evidence review / delivery workflow | 普通 dev 不必启动完整交付流程 |

Bazel 项目使用项目的 Bazel adapter。通用 Make server 中同名的 `soc_comp` 不是可以随意替换的后端。

## Tool、skill、agent 和 script 的区别

Kit bridge 新增可选的 `mcp serve --tool-profile compact`：只读工具由 14 项变为
9 项，六个目录入口合并成 `list_catalog(category)`，类别为
`roles/packs/providers/skills/workflows/checks`。默认仍为 `full`，旧调用保持兼容。
执行权限仍由独立的 `--allow-exec` 和原有确认门禁控制。

项目 launcher 选择 compact 后，可在 Claude 中输入：

```text
Call claude-kit.list_catalog with category="checks".
Show my validation choices without running them.
```

实测 tools/list 紧凑 JSON 从 3,118 降为 2,523 UTF-8 字节，减少约 19.1%。
这是 schema 体积，不代表整个会话 token 降幅；项目和模型的真实验收仍需单独执行。

- **MCP tool**：带明确参数合同的执行函数。读取、生成和昂贵验证应保持可区分。
- **Skill**：告诉 Claude 何时以及如何使用能力。只读本次需要的 skill/reference。
- **Agent/role**：限定任务角色与所有权。kit role 列表不自动注册另一组 Claude agents。
- **Rules**：稳定的项目约束。不要在每个 skill 中复制完整工具列表和环境配置。
- **Script**：维护或执行实现。通常由 Claude/入口调用，不要求工程师手写 Python。

## RTL 工程师：常用 prompt

以下输入 Claude Code 对话框，不是 shell 命令。替换尖括号中的任务事实。

```text
Inspect <module> and implement <approved-change> using rtl-design.
Preserve the interface and unrelated changes. Propose the smallest relevant
checks. Do not run simulation, synthesis, or CDC automatically.
```

```text
Use the registered RTL lint tool for <module> only.
Report the actual result and log path. Do not claim DV validation passed.
```

## DV 工程师：常用 prompt

```text
Use dv-engineering to add <scenario> to <testbench>.
Reuse the existing sequence, scoreboard, and configuration conventions.
Do not run simulation. After the changes, show the validation choices
and wait for my selection.
```

```text
Compile and elaborate <testbench> through the registered project MCP.
Do not run simulation, regression, coverage, synthesis, or CDC.
Report the result, run ID, and compile log.
```

```text
Investigate <test> using existing run <run-id>. Read only relevant log windows.
Use waveform queries only when needed. Do not silently choose another run
or rerun the test.
```

## 更高效，但不牺牲质量

1. 默认只加载当前工作需要的 server；专用生成器、PD、Jira 按需选择，并明确依赖。
2. 合并真正等价的目录/读取入口，不把不同权限和参数的动作全塞进一个 execute。
3. 缩短 skill discovery 描述，将详细示例、条件流程放进 reference。
4. 给出准确 module、target、test、run ID。要求摘要与产物路径，而不是整份日志。
5. 只复用与当前输入、源码版本匹配的证据。少跑命令但复用过期 PASS 没有价值。
6. 分别测量 tool 数量、schema 字节数、实际模型 token 和延迟，不能互相冒充。

Claude Code 的 Tool Search 可以按需加载 MCP 定义，但内部代理和模型必须支持它。
自定义 API gateway 可能默认完整加载；强开 `ENABLE_TOOL_SEARCH=true` 可能因不支持
`tool_reference` 而失败。先用实际配置验证，再改变默认行为。
参见 [Claude Code 官方说明](https://code.claude.com/docs/en/mcp#configure-tool-search)。

## xverif 的正确用法

Debug 先看 `xverif_tools`，再看所选 action 的 `xverif_debug_get_schema`。
只有需要数据库的 action variant 才打开 managed session；结束后关闭自己的 session。
Coverage 使用独立的 `xverif_cov_*` 生命周期，不混用参数。action 数量不是 MCP tool 数量。

```text
Call xverif_bit_slice with value="32'hdeadbeef", msb=15, lsb=8,
and output_format="json". Report the actual result.
```

## scripts 应放在哪里？

| 内容 | 归属 |
| --- | --- |
| 跨项目通用 kit 实现 | claude_kit 的 src/claude_kit/，带测试与稳定入口 |
| 项目特有的 Claude 配置/状态 helper | 项目 .claude/scripts/ |
| 单一 skill 自用 helper | 该 skill 的 scripts/ |
| 不依赖 Claude 的通用构建/回归/发布工具 | 保留在原项目工具目录 |
| 暂时不能同步迁移的旧调用方 | 留薄兼容入口，不复制实现 |

迁移必须同步 root 推导、imports、subprocess 调用、生成模板、测试和文档。
不能只移动文件夹；也不能因为某个 skill 调用一般构建脚本，就把它变成 Claude 专属。

## 如何阅读验证结果

记录源码版本、解释器/工具版本、host/backend、操作、期望值、实际值、artifact 路径。
明确区分：静态/schema 检查、MCP 握手/工具列表、真实业务调用、真实 Claude 选工具、未测/外部前置缺失。
mock 单测、空成功响应、目录列举和缺 license 的 SKIP 都不等于业务端到端通过。
写入/删除测试应使用可丢弃的 fixture，不在真实无关 Jira、文档或项目数据上做破坏性验收。
