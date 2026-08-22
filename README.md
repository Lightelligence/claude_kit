# claude_kit

面向 RTL / DV 工程的可复用 Claude Code kit。

claude_kit 把通用 RTL/DV roles、protocol/VIP packs、项目 profile、repo-local CLI、artifact/evidence 约定，以及可选的薄 MCP bridge 放在一个可固定版本的仓库中。项目只需要通过一个 submodule 和一份很薄的 profile/adapter，就可以快速接入 Claude Code 的 RTL/DV 工作流。

## 当前状态

当前版本已经包含一个可运行的 Python MVP：

- profile 解析和校验，支持 TOML/JSON；
- 项目根目录发现和路径权限检查；
- context resolver 和可审计 manifest；
- 9 个通用 RTL/DV roles，包括 waveform-debugger；
- 7 个可按需同步或触发的通用 skills；
- common、AXI4、APB、Ethernet、PCIe、UCIe、SPI、UART、JTAG、I2C、CHI 和 generic VIP packs；
- repo-local CLI；
- 只读 project inspect；
- 有大小上限的 artifact/log 只读读取；
- profile allowlist command runner；
- profile、manifest、artifact 和 evidence schema；
- 可选 project adapter template；
- 默认只读的 stdio MCP bridge；
- project init 模板；
- fixture 和自动化测试。

当前仍未实现的内容包括更深的 RTL AST/index、波形/FSDB 专用解析器、大型 regression 状态机和具体 simulator adapter。这些属于后续迭代，不应在项目侧重复实现成与 kit 冲突的接口。

## 设计结论

推荐的分层关系：

~~~text
Claude Code
    │
    ├── 项目 CLAUDE.md / 项目规则
    │
    └── claude_kit（本仓库，固定版本）
          ├── 通用 roles
          ├── protocol / VIP packs
          ├── profile schema
          ├── repo-local CLI
          ├── artifact / evidence 契约
          └── 可选薄 MCP bridge
                    │
                    ▼
             消费项目 profile / adapter
                    │
                    ▼
             项目 RTL、DV、VIP 和工具
~~~

核心原则：

1. 通用能力放在 kit，项目差异放在 project profile/adapter。
2. Claude Code 通过 CLI 和文件化 context 获得结构化上下文。
3. MCP 只是 Claude Code 的接口层，不是 RTL/DV 能力的核心。
4. 没有 MCP 时，CLI 和 profile 工作流仍然完整可用。
5. kit 不耦合 ETX runner、bsub 或其他调度平台。
6. kit 不包含任何项目 RTL/DV、SV、Bazel 文件、波形、数据库或生成文件。

这里的 MCP bridge 指 Claude Code 的 MCP 接口，不等同于消费项目中可能名为 MCP 的 SystemVerilog、UVM 或 DV 文件。项目自己的 DV MCP、VIP 连接和 build 文件仍留在项目仓库。

## 目录

- [安装和快速开始](#安装和快速开始)
- [作为 submodule 接入项目](#作为-submodule-接入项目)
- [Project profile](#project-profile)
- [Project adapter](#project-adapter)
- [Roles](#roles)
- [Skills](#skills)
- [Protocol/VIP packs](#protocolvip-packs)
- [CLI 参考](#cli-参考)
- [Context 和 manifest](#context-和-manifest)
- [典型 RTL/DV 工作流](#典型-rtldv-工作流)
- [MCP bridge](#mcp-bridge)
- [安全边界](#安全边界)
- [开发和测试](#开发和测试)
- [故障排查](#故障排查)
- [Roadmap](#roadmap)

## 安装和快速开始

### 运行时要求

- Python 3.11 或更高版本；
- Git；
- Claude Code 可选，但使用 MCP bridge 或项目规则时需要；
- 本仓库运行时不依赖第三方 Python package；
- simulator、VIP、Bazel、Make 等工具由消费项目自行管理。

### 从源码运行

在本仓库根目录：

~~~powershell
python -m claude_kit version
python bin/claude-kit list roles
python bin/claude-kit list packs
~~~

Linux 下可以直接执行 wrapper：

~~~bash
chmod +x bin/claude-kit
./bin/claude-kit version
~~~

也可以安装成 CLI：

~~~bash
python -m pip install -e .
claude-kit version
~~~

安装是可选的。消费项目推荐调用自己固定版本的 submodule wrapper，避免依赖用户机器上的 global kit。

### 初始化一个消费项目

在消费项目根目录，假设 kit 位于 third_party/claude_kit：

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit
~~~

如果希望项目只保留最薄的 Claude Code skill 入口，可以使用 `--minimal`；之后按需运行 `sync` 把 kit 内全部通用 skills materialize 到项目：

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --minimal
python third_party/claude_kit/bin/claude-kit sync --project-root .
~~~

如果项目有 target/test/VIP mapping，希望保留一个薄 adapter，可以额外生成模板：

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-adapter
~~~

如果希望同时启用只读 MCP bridge，可以额外生成项目根目录下的 `.mcp.json`：

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-mcp
~~~

默认会创建：

~~~text
.ai/project.toml
.claude/CLAUDE.md
.claude/skills/rtl-dv-kit/SKILL.md
.claude/skills/rtl-dv-context/SKILL.md
.claude/skills/rtl-design/SKILL.md
.claude/skills/dv-engineering/SKILL.md
.claude/skills/protocol-vip/SKILL.md
.claude/skills/rtl-dv-debugging/SKILL.md
.claude/skills/rtl-dv-review/SKILL.md
~~~

使用 `--with-mcp` 时还会创建 `.mcp.json`；使用 `--with-adapter` 时还会创建 `.ai/adapter.py`。两者都是可选的，默认不会生成。

init 的特点：

- 不修改 RTL、DV、vendor、generated 或 build 文件；
- 已存在的文件默认不覆盖；
- 只有明确使用 --force 才会覆盖这些生成的集成文件；
- 生成的 profile 是模板，必须由项目维护者填写；
- 生成的 CLAUDE.md 和 skills 只提供通用规则，不包含项目路径猜测。

更新 submodule 后，可以只同步 skills，不触碰 profile 和项目规则：

~~~bash
python third_party/claude_kit/bin/claude-kit sync \
  --project-root .
~~~

### Schema 和资源位置

通用资源位于 kit 内部：

~~~text
src/claude_kit/resources/
├── claude/CLAUDE.md
├── roles/
├── skills/
├── packs/
├── schemas/
│   ├── project.schema.json
│   ├── manifest.schema.json
│   ├── artifact-result.schema.json
│   └── evidence.schema.json
└── templates/
~~~

项目 profile/adapter 只填写项目事实；schema、rules、skills、packs 和 evidence 语义由 kit 统一维护。

初始化后先运行：

~~~bash
python third_party/claude_kit/bin/claude-kit doctor \
  --project-root . \
  --strict
~~~

再运行一个只读上下文检查：

~~~bash
python third_party/claude_kit/bin/claude-kit context \
  --project-root . \
  --task "检查项目接入配置，不修改源码"
~~~

## 作为 submodule 接入项目

### 推荐目录

~~~text
my_rtl_project/
├── third_party/
│   └── claude_kit/                 # 固定到 tag 或 approved commit
├── .ai/
│   ├── project.toml                # 项目主 profile
│   ├── adapter/                    # 项目侧薄适配
│   └── overrides/                  # 项目特有补充
├── .claude/
│   ├── CLAUDE.md                   # 生成或维护的项目入口
│   └── skills/
├── CLAUDE.md                       # 项目已有规则时可继续保留
├── .mcp.json                       # 可选：项目自己的 MCP 连接
├── rtl/
├── dv/
├── tb/
├── third_party_vip/
├── generated/
└── out/
    ├── logs/
    ├── reports/
    ├── waves/
    └── coverage/
~~~

职责要保持清楚：

- third_party/claude_kit：通用 roles、packs、CLI 和 bridge；
- .ai/project.toml：项目事实、路径、target、test 和权限；
- .ai/adapter：项目差异和真实工具入口；
- .claude/CLAUDE.md：Claude Code 项目规则；
- .mcp.json：只有在需要 MCP 时才配置；
- RTL/DV/VIP/build 文件：继续留在项目本身。

### 固定版本

~~~bash
git submodule add https://github.com/Lightelligence/claude_kit.git third_party/claude_kit
git -C third_party/claude_kit checkout <approved-commit-or-tag>
git add .gitmodules third_party/claude_kit
git commit -m "Add claude kit"
~~~

项目必须记录 kit 的 tag、commit、内部包版本或 snapshot 版本。更新时先在 fixture 或小型项目上执行 doctor、context 和 smoke，再更新项目的 submodule 指针。

### 最少项目配置

最小可用接入只需要：

1. submodule；
2. .ai/project.toml；
3. 一个项目命令或 adapter 入口；
4. 一份 Claude Code 规则入口。

项目不需要复制所有通用 role、protocol pack 或 MCP tool。项目 profile 只表达差异，通用逻辑统一由 kit 提供。

## Project profile

### 文件位置和格式

默认 profile 查找顺序：

~~~text
.ai/project.toml
.claude-kit/project.toml
.ai/project.json
.claude-kit/project.json
project.toml
project.json
~~~

当前实现支持 TOML 和 JSON。推荐 TOML，因为项目维护者更容易阅读和修改。

### 完整示例

~~~toml
schema_version = 1

packs = ["common", "protocols.axi4", "vip.generic"]

[project]
id = "example_ip"
display_name = "Example IP"
root = "."
language = "systemverilog"
platform = "linux"

[roots]
rtl = ["rtl"]
dv = ["dv"]
testbench = ["tb"]
docs = ["docs"]
vendor = ["third_party_vip"]
generated = ["generated", "out"]

[roles]
defaults = ["rtl-designer", "dv-engineer", "reviewer"]

[build]
system = "project-wrapper"
simulator = "project-configured"
target = "project-target"
test_selector = "smoke"

[build.commands.inspect]
argv = ["./tools/project-cli", "inspect"]
cwd = "."
kind = "read_only"

[build.commands.lint]
argv = ["./tools/project-cli", "lint"]
cwd = "."
kind = "verification"
confirmation = "required"

[build.commands.compile]
argv = ["./tools/project-cli", "compile"]
cwd = "."
kind = "build"
confirmation = "required"

[build.commands.simulate]
argv = ["./tools/project-cli", "simulate", "--test", "smoke"]
cwd = "."
kind = "simulation"
confirmation = "required"

[vip]
axi4_interface = "axi_if"
apb_interface = "apb_if"

[permissions]
writable = ["rtl/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]

[artifacts]
logs = "out/logs"
reports = "out/reports"
waveforms = "out/waves"
coverage = "out/coverage"

[policies]
require_evidence = true
network = "disabled"
auto_commit = false
auto_push = false
~~~

### 字段说明

| 字段 | 作用 |
| --- | --- |
| schema_version | profile schema 版本，不等于 kit 版本 |
| project | 项目标识、根目录、语言和运行平台 |
| roots | RTL、DV、testbench、vendor、generated 的范围 |
| roles | 默认 role 选择；项目特有规则放在项目 `.claude/CLAUDE.md` 或 `.ai/overrides/` |
| packs | 项目真正启用的协议/VIP pack |
| build | build、lint、compile、simulation 入口 |
| vip | 项目真实接口名、实例数量和 mapping |
| permissions | writable、read-only、forbidden 路径 |
| artifacts | 日志、报告、波形和 coverage 位置 |
| policies | 网络、证据、commit 和 push 策略 |

TOML 的 `packs` 是根级字段，必须放在任何 `[project]`、`[roots]` 或其他 table 之前；如果把它写在 `[roles]` 或 `[roots]` 下面，TOML 会把它解析成该 table 的子字段，CLI 就不会使用它作为默认 pack。

### Profile 校验规则

doctor 会检查：

- schema 版本；
- project id；
- roots 类型、越界路径和缺失目录；
- permissions 是否为项目相对路径；
- writable、read_only、forbidden 是否重叠；
- build command 的 argv 是否为非空字符串列表；
- command cwd 是否越出项目根目录；
- roles 和 packs 的类型、内置 ID 引用；
- 可选 adapter 的路径和 required functions；
- command confirmation policy。

doctor 对尚不存在但可能由项目后续创建的 roots 报 warning；doctor --strict 会把 warning 也当成失败。

### 命令定义原则

项目命令必须引用项目已有的 Make、Bazel、FuseSoC、Python wrapper 或其他入口。kit 不重新实现项目 build system，也不猜测 simulator 参数。

每个命令应该明确：

- argv；
- cwd；
- kind；
- 是否只读；
- 是否需要确认；
- 产物位置；
- 失败时保留的日志。

需要 license、专用环境或远程资源的命令，应由项目 wrapper 负责；kit 只做 allowlist、cwd 和证据边界检查。

## Project adapter

Project adapter 是消费项目里的薄层，用来把通用 kit 接到真实项目。典型职责：

~~~text
load_project_profile()
resolve_target(name)
resolve_test(selector)
resolve_vip(protocol)
run_project_check(name)
collect_artifacts(run_id)
review_evidence(path)
~~~

Adapter 可以处理：

- 项目 target 和 test selector；
- RTL/DV/VIP 路径；
- interface 名称和实例数量；
- 项目已有的 Linux build/sim wrapper；
- 日志、波形、coverage 和 evidence 的收集；
- 项目结果到通用 artifact summary 的转换。

Adapter 不应该：

- 复制通用 roles 或 packs；
- 把项目源码打包到 kit；
- 让 kit 猜测项目目录；
- 在没有确认时执行 destructive 命令；
- 把 ETX、bsub 或某个调度系统变成 kit 的必需依赖。

当同一个 adapter 行为被多个项目复用时，应考虑上移到 kit；只属于一个项目的名称和路径留在项目侧。

## Roles

当前内置 roles：

| Role | 用途 |
| --- | --- |
| rtl-architect | 设计拆分、接口、状态机、数据通路和架构 review |
| rtl-designer | RTL 新增、修改、重构和局部检查 |
| dv-architect | testbench 结构、验证计划和 coverage 模型 |
| dv-engineer | test、sequence、driver、monitor、scoreboard、assertion 和 coverage |
| vip-integration | protocol/VIP mapping、连接、配置和 smoke |
| debugger | compile、elaboration、simulation、assertion、scoreboard 和 timeout debug |
| waveform-debugger | 波形、transaction、时序和状态机分析 |
| reviewer | 只读 RTL/DV review |
| evidence-reviewer | 交付前 evidence、日志和未验证声明检查 |

Role 的工作方式跨项目大体一致；项目 profile 注入架构、代码、target、test 和 VIP 细节。

Role 的共通流程：

1. 读取 profile、相关 pack、role 和项目规则。
2. 先做只读扫描并建立文件、模块、接口和命令地图。
3. 明确目标、影响范围和验收条件。
4. 只在 writable 范围内修改。
5. 使用 profile 声明的命令。
6. 记录命令、结果、跳过的检查和剩余风险。

没有运行仿真时，必须明确写“未运行仿真”，不能写“验证通过”。

## Skills

skills 是可由 Claude Code 按任务触发或由项目按需同步到 `.claude/skills/` 的执行流程：

| Skill | 触发和职责 |
| --- | --- |
| rtl-dv-context | 读取 profile、做只读 inspect 并选择最小 context |
| rtl-design | 规划和实施有边界的 RTL 修改 |
| dv-engineering | 规划 test、sequence、scoreboard、assertion 和 coverage |
| protocol-vip | 应用对应 protocol/VIP pack 并验证连接 smoke |
| rtl-dv-debugging | 根据日志、断言、scoreboard 或 timeout 证据定位问题 |
| rtl-dv-review | 做只读 RTL/DV review 和交付前检查 |
| rtl-dv-evidence | 记录可复现的 checks、artifacts、skipped/blocked 和 risks |

默认 `init` 会同步全部通用 skills；`init --minimal` 只生成一个 integration skill，之后可用 `sync` 再同步完整集合。

## Protocol/VIP packs

当前内置 packs：

| Pack | 内容 |
| --- | --- |
| common | 通用 RTL/DV、reset、握手、边界和 evidence 规则 |
| protocols.axi4 | AXI4 handshake、ordering、ID、burst、backpressure 和 response |
| protocols.apb | APB setup/access、wait state、side effect 和 error |
| protocols.ethernet | Ethernet framing、CRC、link state、backpressure 和 recovery |
| protocols.pcie | PCIe LTSSM、TLP、completion、credit、error 和 recovery |
| protocols.ucie | UCIe training、lane/width、flit、retry、flow control 和 recovery |
| protocols.spi | SPI mode、chip-select、bit order、边沿时序和多 slave |
| protocols.uart | UART baud、framing、parity、break 和 overrun |
| protocols.jtag | JTAG TAP、IR/DR、IDCODE、BYPASS 和 reset |
| protocols.i2c | I2C open-drain、START/STOP、ACK、stretch 和 arbitration |
| protocols.chi | CHI channel、credit、ordering、snoop 和 coherency |
| vip.generic | VIP 版本、连接、实例、时钟/复位和 smoke 检查 |

Pack 只提供领域规则，不提供项目绝对路径、license、VIP class、library path 或 simulator 宏。项目 profile/adapter 负责这些差异。

每个 protocol pack 至少要覆盖：

- 协议版本和适用范围；
- handshake 或 transaction 语义；
- reset、clock 和 timing 假设；
- ordering、backpressure、timeout、retry 和 error；
- RTL review 检查；
- DV positive、boundary、negative、reset 和 recovery 场景。

选择原则：

- 只加载任务真正需要的 pack；
- 明确 AXI4、AXI4-Lite、AXI-Stream 等版本；
- 将规范要求、常见实现和项目约定分开；
- pack 与 profile 冲突时报告冲突，不静默覆盖；
- 一次性 workaround 留在 project override。

## CLI 参考

### 总览

~~~text
claude-kit version
claude-kit init
claude-kit sync
claude-kit doctor
claude-kit list roles
claude-kit list packs
claude-kit list skills
claude-kit context
claude-kit manifest
claude-kit inspect
claude-kit artifact read
claude-kit check
claude-kit adapter check
claude-kit evidence check
claude-kit evidence template
claude-kit mcp serve
~~~

### version

~~~bash
claude-kit version
~~~

显示 kit 版本。当前版本为 0.1.0。

### init

~~~bash
claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit
~~~

创建最小项目集成文件。已存在的文件默认不覆盖；只有显式使用 --force 才会覆盖。
使用 --with-adapter 可额外创建 .ai/adapter.py 模板。
使用 --with-mcp 可额外创建只读 MCP 的 .mcp.json；该配置不会启用 run_check。
使用 --minimal 时只创建 `rtl-dv-kit` integration skill，不复制其余 skills；这适合希望项目仓库只保留极薄 Claude Code 配置的场景。

### sync

~~~bash
claude-kit sync --project-root .
claude-kit sync --project-root . --force
~~~

只同步 kit 提供的 Claude Code skills。默认不覆盖项目已有 skill；--force 只覆盖由 kit 生成的 skill 路径，不触碰 profile、CLAUDE.md、RTL、DV 或其他项目文件。

### doctor

~~~bash
claude-kit doctor --project-root . --strict
claude-kit doctor --project-root . --json
~~~

doctor 只读检查 profile 和安全边界。推荐在每次接入、更新 submodule 和提交项目 profile 前运行。

### list

~~~bash
claude-kit list roles
claude-kit list packs
claude-kit list skills
claude-kit list roles --json
claude-kit list packs --json
~~~

列出 role、pack 或 skill 的 ID、版本、摘要和来源。

### context

~~~bash
claude-kit context \
  --project-root . \
  --role rtl-designer \
  --pack protocols.axi4 \
  --task "修复 response channel 的 backpressure 问题" \
  --output out/claude/context.md \
  --manifest out/claude/context-manifest.json
~~~

role 和 pack 可以重复多次。没有显式选择时，使用 profile 中的 defaults。
`--task-file` 也可以提供任务说明；为避免越权读取，它必须位于 project root 内。

### manifest

~~~bash
claude-kit manifest \
  --project-root . \
  --role reviewer \
  --pack common \
  --task "审查当前变更"
~~~

只输出机器可读的 resolved context manifest，包括 profile、role、pack、任务和来源文件 hash。

### inspect

~~~bash
claude-kit inspect --project-root . --json
~~~

只读统计 profile roots 下的文件数量和扩展名。它不解析或修改 RTL，也不会访问 profile 之外的路径。

### artifact read

读取项目根目录内的日志、报告、波形索引或其他文本 artifact。默认最多读取 100 KiB，硬上限为 1 MiB；返回中保留原始文件字节数和是否截断的信息。

~~~bash
claude-kit artifact read \
  --project-root . \
  --file out/logs/smoke.log \
  --max-bytes 100000 \
  --json
~~~

该命令只读，不解析 artifact 的语义，也不会跟随越出 project root 的路径或 symlink。

### evidence

生成 evidence 模板：

~~~bash
claude-kit evidence template --project-root . --output out/evidence.json
~~~

校验证据文件：

~~~bash
claude-kit evidence check \
  --project-root . \
  --file out/evidence.json \
  --strict \
  --json
~~~

evidence 至少说明 project、task、source revision、changes、checks、skipped 和 risks。每个 check 要有状态；passed check 应尽量带实际 command 和 artifact。严格模式会把 warning 当成失败，并检查 changed path 是否落在 profile 的 writable 范围。

### check

~~~bash
claude-kit check inspect --project-root .
claude-kit check lint --project-root . --confirm
~~~

只允许运行 profile 的 build.commands 中登记的命令：

- kind 为 read_only 的命令可直接运行；
- confirmation 为 required 的命令必须带 --confirm；
- argv 不经过 shell 拼接；
- cwd 必须位于项目根目录内；
- 输出包含状态、argv、cwd、退出码、stdout 和 stderr；超时或启动失败时会保留失败原因并返回空的退出码。

### adapter check

如果 profile 声明了可选 adapter，可以显式检查它的路径、导入和契约函数：

~~~bash
claude-kit adapter check --project-root . --json
~~

adapter check 会导入项目侧 Python adapter，检查 required functions、已知函数签名是否至少接受一个参数，但不会自动调用 resolve_target、resolve_test、resolve_vip 或 collect_artifacts。需要实际运行项目行为时，仍应通过 profile 的 allowlisted command 并保留 evidence。

### mcp serve

~~~bash
claude-kit mcp serve \
  --project-root . \
  --profile .ai/project.toml
~~~

默认只提供只读工具。只有明确使用 --allow-exec 才会暴露 run_check，且 tool call 仍必须提交 confirm = true。

## Context 和 manifest

Resolved context 由以下来源合并：

~~~text
generic role guidance
  + selected protocol/VIP pack
  + project profile facts
  + task-local instruction
  + explicit user request
~~~

当前 CLI resolver 自动合并的是 role、pack、profile 和 task；项目 `.claude/CLAUDE.md`、`.ai/overrides/` 以及用户请求由 Claude Code 的规则层继续提供，不会被 kit 偷猜或隐式读取。这样可以保持 manifest 的来源边界清楚。

Context 包含：

1. Project facts：根目录、路径分类、工具和命令；
2. Task instructions：本次任务目标、限制和验收条件；
3. Role/pack guidance：工作顺序、领域检查项和风险；
4. Evidence contract：命令、产物、未运行检查和未决风险。

Manifest 记录：

~~~json
{
  "schema_version": 1,
  "project": "example_ip",
  "profile": ".ai/project.toml",
  "roles": ["rtl-designer"],
  "packs": ["protocols.axi4"],
  "task": "task text",
  "sources": [
    {
      "path": "roles/rtl-designer.md",
      "sha256": "..."
    }
  ],
  "warnings": []
}
~~~

Manifest 不包含完整源码，也不应包含 password、token、secret、private key 或 license 内容。

## 典型 RTL/DV 工作流

### 新项目接入

1. 固定 kit submodule 版本。
2. 运行 init，生成 profile 和 Claude Code 集成入口。
3. 填写 RTL、DV、testbench、vendor、generated 和 artifact 路径。
4. 登记项目已有的 inspect、lint、compile、simulation 和 regression wrapper。
5. 选择 roles 和 protocol/VIP packs。
6. 配置 writable/read-only/forbidden。
7. 运行 doctor --strict。
8. 用 reviewer 对 profile 做一次只读检查。
9. 运行 context/inspect smoke。
10. 再决定是否启用 MCP。

### RTL 新增或修改

推荐 rtl-architect 加 rtl-designer：

1. 读取 profile、模块、接口、相关 test 和项目规则。
2. 建立状态机、数据通路、握手和 reset 模型。
3. 写明不变量、延迟、ordering、backpressure 和 error 语义。
4. 只修改 writable 路径。
5. 先运行最小 lint/compile，再运行相关单元仿真。
6. 检查参数、位宽、signedness、queue 边界和恢复路径。
7. 记录未覆盖 corner case 和未运行检查。

### DV 新增或修改

推荐 dv-architect 加 dv-engineer：

1. 读取 DUT interface、transaction、寄存器和现有 bench。
2. 区分 driver、monitor、sequencer、scoreboard、reference model 和 coverage。
3. 规划 positive、boundary、negative、reset 和 recovery 场景。
4. 明确比较时点、排序、ID、mask、延迟和容忍范围。
5. 先运行单 test，再根据证据扩大回归。
6. 检查 assertion、functional coverage 和 scoreboard evidence。

test 结束不等于验证完成；必须说明关键 corner case 和覆盖缺口。

### Protocol/VIP 集成

推荐 vip-integration 加对应 protocol pack：

1. 选择协议版本和 pack。
2. 在 profile/adapter 中记录真实 VIP 版本、接口、实例数量和 simulator 入口。
3. 检查每个实例的 clock、reset、方向和 mapping。
4. 运行 reset、单笔传输、backpressure、error 和 recovery smoke。
5. 再覆盖并发、随机延迟、outstanding、重试和 lane/width 场景。
6. 将 VIP warning、protocol violation、scoreboard mismatch 和环境错误分开。

### 编译或仿真失败

使用 debugger：

1. 保存精确命令、cwd、退出码和第一处错误。
2. 区分环境、compile、link、runtime、assertion、scoreboard 和 timeout。
3. 确认日志属于当前 source/test/seed。
4. 缩小到单 test、单 seed、单 transaction 或最小复现。
5. 提出可证伪的根因假设。
6. 修复后先重跑最小复现，再扩大检查。
7. 保留前后结果和 artifact 路径。

kit 可以调用项目 wrapper，但不负责远程调度、license 申请或资源分配。

### Review 和交付

reviewer 默认只读，问题格式：

~~~text
[P1] path:line
Problem: concrete behavior or risk
Evidence: code, log, waveform or test
Impact: functional, protocol, timing, verification or maintenance
Suggestion: smallest useful correction
~~~

交付前确认：

- 变更范围与任务一致；
- vendor/generated/build/secret 没有误改；
- 关键检查已运行或有明确豁免；
- 日志和报告能定位到本次变更；
- 失败、跳过和未决风险已记录；
- 没有未经授权的 commit、push、网络访问或 destructive 操作。

## MCP bridge

### 定位

MCP bridge 是 CLI/context resolver 的适配层，不是另一个工作流引擎。

它应该：

- 默认关闭；
- 复用 CLI 的 profile、schema 和权限；
- 只暴露少量稳定接口；
- 不保存对话或 secret；
- 在没有 MCP 时不影响 CLI 工作流。

### 当前只读工具

默认提供：

- get_project_profile；
- list_roles；
- list_packs；
- resolve_context；
- inspect_design；
- read_artifact；
- review_evidence。

使用 --allow-exec 后才增加：

- run_check。

run_check 仍要求 tool arguments 中显式传入 confirm = true，并且只运行 profile 已登记的命令。

### Claude Code 连接

消费项目可以在自己的 MCP 配置中指向：

~~~json
{
  "mcpServers": {
    "claude-kit": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "third_party/claude_kit/bin/claude-kit",
        "mcp",
        "serve",
        "--project-root",
        ".",
        "--profile",
        ".ai/project.toml"
      ]
    }
  }
}
~~~

MCP 配置是可选的。项目的 .mcp.json 只负责连接 bridge；profile、adapter 和真实工具入口仍属于项目侧内容。

### MCP 和项目 DV MCP 的边界

本 bridge 不会读取或重写项目内部的 SV、Bazel、UVM 或 DV MCP 实现。它只通过项目 profile 看到项目声明的 roots、commands、artifacts 和权限。

## 安全边界

### 路径

- 默认只允许项目根目录内的相对路径。
- writable、read_only 和 forbidden 重叠时 doctor 失败。
- vendor、generated、build、out 和 .git 默认只读或禁止写入。
- 不因路径不存在就自动创建源码目录。
- artifact 读取拒绝越出项目根目录的路径。
- artifact 读取默认限制为 100 KiB，最大为 1 MiB，避免把完整大日志送入 context。

### 命令

- 只运行 profile 登记的 argv。
- 不拼接未经处理的 shell 字符串。
- 记录 argv、cwd、退出码和产物。
- clean、删除、覆盖、commit、push 和高成本回归需要显式确认。
- 不自动发现并运行未知脚本。

### Secret 和网络

- context、manifest 和日志摘要不得暴露 password、token、private key 或 license。
- 默认不访问网络。
- bridge 不默认上传源码、波形或日志。
- 需要外部服务时，由用户和项目 wrapper 明确控制。

### ETX

本仓库不包含 ETX runner，也不以 ETX 为运行前提。它不会实现：

- bsub/ETX job submission；
- runner 选择和资源调度；
- license server 管理；
- simulator 安装和版本切换；
- 大规模回归重试；
- 集中式结果数据库。

项目可以自行在 wrapper 中使用任何本地或远程基础设施，kit 只调用 profile 声明的入口。

## 开发和测试

### 本地测试

~~~powershell
python -m compileall -q src bin
python -m unittest discover -s tests -v
~~~

仓库的 `.github/workflows/ci.yml` 会在 Python 3.11、3.12、3.13 上执行同一组 compile、安装态 CLI 和 unittest 检查；它不启动 simulator、不提交 ETX/bsub 作业，也不需要项目 license。

当前 fixture 覆盖：

- role/pack catalog；
- profile TOML 加载；
- doctor strict；
- permission overlap；
- context 和 manifest source hash；
- inspect roots；
- artifact 越界保护；
- command confirmation；
- init 的非破坏行为；
- skill catalog 和 sync；
- evidence schema、artifact 引用和 read-only path；
- CLI doctor/context/check/evidence；
- CLI artifact read；
- MCP tools/list、profile 脱敏、artifact read 和只读工具。

### 添加 role

1. 放到 src/claude_kit/resources/roles/。
2. 使用 front matter 声明 id、version 和 scope。
3. 写清目标、先读内容、工作顺序、检查项、证据和禁止事项。
4. 保持跨项目通用，不硬编码项目路径。
5. 更新 catalog、context 测试和 README。

### 添加 pack

1. 在 src/claude_kit/resources/packs/<family>/<name>/ 创建 pack.json。
2. 为 metadata 提供 id、version、kind、summary 和 entrypoints。
3. 写清协议版本、适用范围、reset、握手、错误、边界和验证建议。
4. 不放项目绝对路径、VIP license、token 或 simulator 宏。
5. 更新 pack catalog、fixture 和 README。

### 添加 skill

1. 放到 src/claude_kit/resources/skills/<skill-id>/SKILL.md。
2. 使用 front matter 声明 name、version 和 description。
3. 只写跨项目通用的 Claude Code 工作规则。
4. 不在 skill 中硬编码项目路径、target、license 或调度平台。
5. 更新 skill catalog、sync 测试和 README。

### 添加 CLI 命令

需要说明：

- 用户问题；
- 输入、输出和退出码；
- 读/写/执行属性；
- profile policy 和确认规则；
- 路径校验；
- 没有 MCP 时的行为；
- 单元测试和文档。

### Pull request 清单

- [ ] 属于通用 kit，而不是未抽象的项目 workaround。
- [ ] 没有本机路径、用户名、secret、license 或 ETX 硬编码。
- [ ] role/pack 有唯一 ID、版本和适用范围。
- [ ] schema/context/CLI 测试已更新。
- [ ] 新命令的权限和确认策略已说明。
- [ ] README、CLI help 和实际行为一致。
- [ ] fixture 可以复现关键行为。
- [ ] 验证命令、结果和未运行检查已记录。

## 故障排查

### 找不到 profile

在消费项目根目录运行，或者显式传入 --project-root 和 --profile。检查 profile 是否位于默认查找路径。

### doctor 报 roots 不存在

这通常是 profile 模板还没有按真实项目路径填写。普通 doctor 会 warning，doctor strict 会失败。修正 profile，不要把真实项目路径硬编码进 kit。

### permissions overlap

同一个路径不能同时 writable、read_only 或 forbidden。缩小 glob 范围，并再次运行 doctor。

### 找不到 role 或 pack

检查 submodule commit、ID 大小写和 profile 引用：

~~~bash
claude-kit list roles
claude-kit list packs
~~~

### check 被拒绝

确认命令已登记在 build.commands，cwd 位于项目根目录内；如果命令标记 confirmation = required，使用 --confirm。

### context 太长

减少默认 packs，只选择当前任务需要的 role/pack；将项目事实放 profile，长篇协议知识放 pack，不要重复写入 CLAUDE.md。

### MCP 不可用

先验证 CLI：

~~~bash
claude-kit doctor --strict
claude-kit context --task "read-only smoke"
~~~

CLI 可用后，再检查 MCP 的 command、args、project root、profile 和 stdio 连接。MCP 故障不应阻塞 CLI 工作流。

## Roadmap

后续优先级：

1. 稳定 profile、role、pack 和 manifest schema。
2. 增加 profile 迁移和更细的 path capability。
3. 增加 RTL module/instance/dependency index。
4. 增加更丰富的 log、coverage 和 evidence parser。
5. 增加项目 adapter interface 和 adapter contract test。
6. 增加更多协议/VIP packs。
7. 增加可选的 artifact-backed 长任务状态。
8. 在真实 RTL/DV 项目上试用并减少项目侧配置。
9. 保持 MCP 薄化，不把大型执行逻辑迁入 MCP。

每一步都必须保持：

- kit 不耦合 ETX runner；
- 项目差异留在 profile/adapter；
- 没有 MCP 时 CLI 仍可用；
- 不把消费项目 RTL/DV 文件移入本仓库。

## License

本项目使用 [MIT License](LICENSE)。
