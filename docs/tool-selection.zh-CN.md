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
| 从已知 byte fragments 拼接 descriptor/header 字段 | xentry decode + 字段布局配置 | 不负责波形提取、valid/ready 判断或协议语义；先取得有效数据片段 |
| 生成寄存器/RAL/CRG | 已启用的专用 generator | 不手改生成的 RTL |
| 综合、CDC、物理实现 | 明确选择的项目 MCP lane | 不自动成为每个 DV 改动的必做项 |
| 交付检查 | evidence review / delivery workflow | 普通 dev 不必启动完整交付流程 |

Bazel 项目使用项目的 Bazel adapter。通用 Make server 中同名的 `soc_comp` 不是可以随意替换的后端。

不熟悉布局时用 `xverif_entry_explain`；只检查配置/输入是否合法时用
`xverif_entry_validate`；需要字段值时用 `xverif_entry_decode`。
不要每次解码都顺序调用三个工具。解码结果包含 raw 字段和来源，不会推断握手或枚举含义。

```text
Use xverif_entry_decode with config_path=<layout.yaml>, input_path=<beats.jsonl>,
and output_format="json". Report the requested fields, their raw values and
source fragments. Do not open a waveform session or infer protocol semantics.
```

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

## 按场景启动 Claude Code

项目可在 `.claude/tool-profiles.json` 中定义配置，server 名称必须与 `.mcp.json` 完全一致：

```json
{"schema_version":1,"profiles":{"rtl":{"description":"RTL editing and checks","servers":["soc-build-bazel","soc-lsp","claude-kit"]}}}
```

```sh
python3 third_party/claude_kit/bin/claude-kit tool-profiles --project-root .
python3 third_party/claude_kit/bin/claude-kit session --project-root . --tools rtl
```

第二条命令启动原生 Claude Code，此后直接输入自然语言，无须为每次 MCP 调用运行 Python。
可分别配置 debug、寄存器生成和物理设计场景；额外的原生 Claude 参数放在 `--` 之后。
入口使用临时 strict MCP 配置，退出后删除，不改模型和权限设置。
查询清单只显示名称和描述，不打印 server 凭据。
项目禁用列表或组织策略仍可能影响可用性，进入会话后用 `/mcp` 核对。

该入口已通过本地测试及 ETX 原生 Claude Code 2.1.267 的 debug 场景验收。
修复继承 PROJ_DIR 导致跨 checkout 的问题后，只连接 kit 和 xverif，
用时 12.53 秒、暴露 45 个工具，并通过 inspect_design 核验 xin_1 的绝对路径、
profile 校验通过、bit 结果为 17，项目状态仍未变。这证明已测 debug 场景的路由和调用，
不是所有功能通过的结论，也不是实际 token 节省比例。

## 脚本归属

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

### 当前 ETX 验证范围（2026-09-13）

基线发现 16 个 stdio servers、218 个工具（包含禁用的可选服务）。8 个启用的
stdio servers 暴露 89 个工具，紧凑 JSON schema 共 63,682 UTF-8 字节；不含 HTTP 绘图服务。
这些数字不是模型 token 数，也不代表全部业务功能通过。

| 能力 | 已取得的证据 | 仍需验证 |
| --- | --- | --- |
| kit 精简目录 | 本地兼容测试；实际 ETX 注册 9 个工具、2,523 schema 字节，原生 Claude 调用成功 | 更多任务质量检查 |
| 场景入口 | 7 个配置解析通过；原生 Claude debug 场景只连接 2 个服务，实际调用两者成功 | 其余场景与代表性 RTL/DV 任务质量 |
| 寄存器生成 | 13 个 yml2reg MCP 入口产生非空文件，适用时检查 XML/JSON/XLSX 可解析 | 生成 HDL 的编译与项目语义检查 |
| bit 工具 | 真实 MCP 转换、切片、计算、比较分别得到 255/-1、190、17、matched=true | 上游 MCP 参数说明修正 |
| SVA | list/scan/parse/explain 对隔离 property fixture 返回实际结果 | 更多时序语义案例 |
| xdebug | 实际 action guide 和 schema 调用 | 完整 FSDB/design/session 操作矩阵 |
| coverage | 修复 Python 路径后，真实 MCP action 目录查询通过 | VDB 查询、报告、导出、exclusion 生命周期 |
| LSP | 两个工作目录下 4 个导航工具共 8 次真实调用通过；实际目录仅含 4 个受支持工具 | 更多项目级导航案例；workspace/symbol 不再暴露 |
| 日志位置 | resolve/context/stats/annotate 对隔离日志、映射和源码返回完整结果 | 大日志和异常输入 |
| Entry 字段 | explain/validate/decode 实际通过两拍示例：0xab234，opcode=4、route=0x23、payload=0xab，来源记录正确 | 其他布局、bit 顺序及异常输入 |
| Bazel RTL lint | 实际 soc_lint 执行 axi_narrow 的 VCS-only lint；编译链接完成，检查报告 21 个 warning、零 error/fatal | 干净的正向 fixture；设计 warning 导致的失败不能写成检查通过 |
| Bazel integration | 实际 workspace 校验、target 列表、依赖/构建图查询及 vendor 配置片段生成；修复后的解析器识别 24 个真实仓库 | 三个真实 IP 路径缺失仍存在，其余构建操作未测 |
| CRG、memory-map、Excel、时钟树图 | 七个生成器实际调用均用复制的示例产生非空文件；Draw.io XML、Excalidraw JSON 可解析 | 生成 HDL 编译、项目语义与图形视觉检查 |
| OpenROAD | 隔离设计的 config/SDC 生成、空输出状态查询实际通过 | 本地综合缺少 orfs_dir/SILICON_CREW_ORFS_DIR；有限范围的 runner 检查未找到 ORFS 路径或 PATH 中的 openroad/yosys，容器方式未验证 |
| Memory wrapper | 实际 catalog 生成；修复后 96×24 逻辑接口适配到足够大的 128×32 宏，VCS 编译/仿真报告显示定向地址与掩码测试通过 | 其他 memory/FIFO 类型、物理 lib/lef 可用性与完整 signoff 尚未验证 |
| 禁用的通用生成器/Make adapters | 握手和工具列表通过 | 各自功能 fixture；日常会话不启用 |
| Atlassian/HTTP 绘图 | 仅 Atlassian 工具列表通过；绘图未测 | 非破坏性服务验证，不为测试创建真实工单 |

项目 helper 迁移通过 13 项检查，包括生成文件一致性和原有指令预算；旧路径保留兼容入口。
以上不是整个项目的 signoff 结论。
