# claude_kit 命令与工具速查

[返回英文版 README](../README.md) | [English command reference](command-reference.md)

这是一份面向 RTL/DV 消费项目的快速查询文档。它集中说明 repo-local CLI、Claude Code 使用的只读 MCP tools、roles、skills、protocol/VIP packs、project profile，以及在 `hw/` 下进行开发时的标准用法。

如果已经知道要做什么，只需要查找对应命令、tool、参数或 Claude Code prompt，可以直接从本页开始。

## 1. 最短使用路径

在消费项目根目录执行：

```bash
CLAUDE_KIT_BIN=third_party/claude_kit/bin/claude-kit

# 确认 kit 版本和项目 profile。
python3 "$CLAUDE_KIT_BIN" version
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json

# 查看可复用内容。
python3 "$CLAUDE_KIT_BIN" list roles
python3 "$CLAUDE_KIT_BIN" list skills
python3 "$CLAUDE_KIT_BIN" list packs
python3 "$CLAUDE_KIT_BIN" list workflows

# 在读取大量 context 或修改文件前先规划任务。
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --task "Review and fix the AXI4 response path in hw/" \
  --json
```

然后从同一个项目根目录启动 Claude Code：

```bash
claude
```

如果 `.mcp.json` 中存在生成的 `claude-kit` 配置，Claude Code 会自动启动 MCP bridge。日常主入口应该是 Claude Code；上面的 shell 命令主要用于初始化、诊断、脚本和 CI。

## 2. 按意图快速查找

| 目标 | CLI | Claude Code / MCP |
| --- | --- | --- |
| 查看 kit 版本 | `version` | 让 Claude 报告已连接的 kit 版本 |
| 校验 profile 和权限 | `doctor --strict --json` | `get_project_profile` |
| 查看 roles | `list roles` | `list_roles` |
| 查看 protocol/VIP packs | `list packs` | `list_packs` |
| 查看 skills | `list skills` | `list_skills` |
| 查看 workflows | `list workflows` | `list_workflows` |
| 规划任务 | `plan --task ...` | `plan_task` |
| 加载选定的 role/pack/skill context | `context ...` | `resolve_context` |
| 查看配置的 RTL/DV 目录摘要 | `inspect --json` | `inspect_design` |
| 读取受大小限制的日志/报告 | `artifact read ...` | `read_artifact` |
| 校验 evidence JSON | `evidence check ...` | `review_evidence` |
| 查看 engineer 可选择的 check menu | `checks` | `list_checks` |
| 执行项目命令 | `check <name>` | 只有显式开启 `--allow-exec` 后才有 `run_check` |
| 执行多个选中的 check 并收集报告 | `check-batch ...` | 只有 `--allow-exec` 后才有 `run_checks` |

CLI 和 MCP bridge 共享同一套 profile、路径校验、catalog 和 evidence 规则。MCP bridge 只是 Claude Code 的接口层，不是另外一套 planner 或 build system。

## 3. 基本约定和安全边界

### 从项目根目录运行

项目路径默认都是相对于消费项目根目录。应该从根目录启动 Claude Code 和 CLI，这样 `.ai/project.toml`、`.mcp.json`、`hw/`、日志以及 profile 中的命令解析一致。

```bash
cd /path/to/consumer-project
python3 third_party/claude_kit/bin/claude-kit doctor --project-root . --strict
claude
```

如果 checkout 没有保留 executable bit，直接执行 wrapper 可能失败。稳定写法是：

```bash
python3 third_party/claude_kit/bin/claude-kit version
```

### Project profile 是权限和项目事实的唯一来源

kit 不会猜测项目目录、target、test name、simulator 参数或权限。这些内容都应该写在 `.ai/project.toml`。

RTL/DV 项目的默认模板现在包含可写的硬件目录：

```toml
[roots]
hw = ["hw"]
rtl = ["rtl"]
dv = ["dv"]
testbench = ["tb"]

[permissions]
writable = ["hw/**", "rtl/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
deletable = []
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]
```

`roots.hw = ["hw"]` 告诉 `inspect_design` 和 context resolver 硬件树在哪里；`permissions.writable = ["hw/**"]` 授权在该目录下修改文件和记录 evidence。`permissions.deletable` 是更窄的、用于审计清理废弃文件的明确范围，不授权普通修改。两者是独立声明，配置其中一个不会自动配置另一个。

只要项目 profile 声明 `hw/**` 为 writable，claude_kit 就允许读写该目录。仍然必须遵守 `read_only`、`forbidden`、symlink、project-root 和 evidence 校验。

### 先只读和规划，再执行

默认只读或规划操作包括：

- `doctor`、`list`、`plan`、`checks`、`context`、`manifest`、`inspect`、`artifact read`；
- 默认 MCP tools；
- Claude Code 对 profile 和 catalogs 的读取。

build、lint、compile、simulation、regression 和 artifact collection 命令属于消费项目。它们必须在 `[build.commands]` 中声明；`confirmation = "required"` 的命令必须显式确认。`kind = "simulation"` 或 `kind = "regression"` 的命令即使没有填写 `confirmation` 或填写为 `optional`，也必须显式确认。需要 license 或远程资源的 workload 应继续由项目 wrapper 和批准的 runner 流程负责。

新建或修改 DV test 时，默认 implementation 路径在 planning、static/lint
检查和 evidence 后结束，不会自动启动 simulation 或 regression。运行 focused
test 前先询问，或者只有在用户明确委托后才交给 `commander` role 执行。

## 4. CLI 参考

先设置 wrapper 变量：

```bash
CLAUDE_KIT_BIN=third_party/claude_kit/bin/claude-kit
```

下面所有示例也可以把 `python3 "$CLAUDE_KIT_BIN"` 换成已经安装的 `claude-kit` 命令。

### 通用参数

大多数 project-aware 命令支持：

| 参数 | 含义 |
| --- | --- |
| `--project-root PATH` | 消费项目根目录；省略时默认查找最近的 Git root。 |
| `--profile PATH` | 相对于项目根目录的 profile 路径，通常是 `.ai/project.toml`。 |
| `--json` | 在支持的命令中输出机器可读 JSON。 |

### `version`

查看 checkout 或 submodule 中 kit 的版本：

```bash
python3 "$CLAUDE_KIT_BIN" version
```

它只显示版本，不校验项目 profile。

### `init`

生成最小的项目集成文件，不修改 RTL、DV、vendor、generated 或 build 文件：

```bash
python3 "$CLAUDE_KIT_BIN" init \
  --project-root . \
  --kit-path third_party/claude_kit
```

普通初始化会生成或尝试生成：

```text
.ai/project.toml
.claude/CLAUDE.md
.claude/skills/rtl-dv-kit/SKILL.md
.claude/skills/<kit-skill>/SKILL.md
```

常用模式：

```bash
# 只生成最小集成 skill，其他 skill 以后用 sync 生成。
python3 "$CLAUDE_KIT_BIN" init --project-root . --minimal

# 不生成项目侧 skill 文件。
python3 "$CLAUDE_KIT_BIN" init --project-root . --no-skills

# 生成可选 adapter contract 模板。
python3 "$CLAUDE_KIT_BIN" init --project-root . --with-adapter

# 只在 .mcp.json 中添加或刷新 claude-kit entry。
python3 "$CLAUDE_KIT_BIN" init --project-root . --with-mcp

# 显式允许替换 kit 管理的文件。
python3 "$CLAUDE_KIT_BIN" init --project-root . --force
```

`init` 不会开启可执行 MCP tool，也不会覆盖其他项目 MCP server。生成的 profile 仍然需要项目 owner 补全，之后再运行 `doctor`。

### `sync`

生成或刷新 kit 提供的 Claude Code skills：

```bash
python3 "$CLAUDE_KIT_BIN" sync --project-root .
python3 "$CLAUDE_KIT_BIN" sync --project-root . --force
```

没有 `--force` 时保留已有文件；有 `--force` 时只替换 kit 管理的 skill 路径，不修改 profile、项目规则、源代码或 MCP servers。

### `doctor`

校验 profile、roots、commands、roles、packs、adapter 和权限边界：

```bash
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json
```

建议在开始修改、profile 变化、submodule 更新和交付前运行 `--strict`。strict failure 是需要处理的 gate，不应通过关闭校验来绕过。

典型检查包括：

- profile schema 和 project identity；
- root 是否缺失或逃逸项目根目录；
- writable/read-only/forbidden 是否重叠；
- `build.commands` 的 argv 和 cwd；
- 引用的 roles、packs 和 adapter functions；
- command confirmation policy。

### `list`

查看可复用 catalogs：

```bash
python3 "$CLAUDE_KIT_BIN" list roles
python3 "$CLAUDE_KIT_BIN" list packs
python3 "$CLAUDE_KIT_BIN" list skills
python3 "$CLAUDE_KIT_BIN" list workflows

python3 "$CLAUDE_KIT_BIN" list skills --json
```

文本输出适合人工阅读，JSON 适合脚本和让 Claude Code 根据精确 catalog 做选择。

### `plan`

把任务路由到最小的可复用 workflow，不执行项目命令，也不修改文件：

```bash
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --task "Add an APB wait-state negative test for the hardware under hw/" \
  --json
```

已知任务类型时可以显式指定：

```bash
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --workflow dv-change \
  --role dv-engineer \
  --pack protocols.apb \
  --task "Add an APB wait-state negative test"
```

结果可能包含：

- workflow、roles、skills、packs；
- guidance 的源路径和 hash；
- profile 中可用或缺失的命令；
- target、test selector、simulator、source revision 等缺失事实；
- writable/read-only/forbidden 权限；
- artifact 位置和 evidence 要求；
- warnings 和完成 gate。

`missing_facts`、`missing_commands` 和 `warnings` 必须被补齐，或在执行前明确记录为 blocked/skipped。

### `context`

从 profile 和选定的 guidance 生成紧凑的 Markdown context：

```bash
python3 "$CLAUDE_KIT_BIN" context \
  --project-root . \
  --role rtl-designer \
  --pack common \
  --pack protocols.axi4 \
  --skill rtl-design \
  --skill rtl-dv-context \
  --task "Fix AXI4 response-channel backpressure in hw/" \
  --output out/claude/context.md \
  --manifest out/claude/context-manifest.json
```

roles 和 packs 可以重复指定。不指定时使用 profile defaults。skills 是显式选择的，避免整个 skill library 无差别进入 prompt；一般应使用 `plan` 推荐的最小集合。

### `manifest`

只输出 resolved context 的机器可读 manifest：

```bash
python3 "$CLAUDE_KIT_BIN" manifest \
  --project-root . \
  --role reviewer \
  --pack common \
  --skill rtl-dv-review \
  --task "Review the current hardware change"
```

manifest 记录 project、profile、roles、packs、skills、task、源路径和 hash，不应包含 secret 或完整项目源代码。

### `inspect`

对 `[roots]` 中声明的项目目录做只读文件和扩展名统计：

```bash
python3 "$CLAUDE_KIT_BIN" inspect --project-root . --json
```

适合确认 `hw/`、`dv/`、`tb/`、logs 等目录是否存在。它不解析 SystemVerilog、不运行 simulator，也不读取项目根目录外的路径。

如果 profile 的 `[roots]` 没有 `hw = ["hw"]`，即使 `permissions.writable` 包含 `hw/**`，`inspect` 也不会把它报告为配置的 hardware group。

### `artifact read`

读取项目根目录内有大小限制的 UTF-8 日志、报告或 evidence：

```bash
python3 "$CLAUDE_KIT_BIN" artifact read \
  --project-root . \
  --file out/logs/smoke.log \
  --max-bytes 100000 \
  --json
```

默认上限是 100 KiB，硬上限是 1 MiB。结果会报告原始字节数和是否截断。路径必须留在项目根目录内。

### `evidence template`

生成 evidence 模板：

```bash
python3 "$CLAUDE_KIT_BIN" evidence template \
  --project-root . \
  --output out/evidence.json
```

### `evidence check`

根据 profile 和权限策略校验证据：

```bash
python3 "$CLAUDE_KIT_BIN" evidence check \
  --project-root . \
  --file out/evidence.json \
  --strict \
  --json
```

strict 会把 warning 当作 failure，并检查 passed check 是否有 command evidence、artifact 路径是否有效、changed paths 是否允许。像 `hw/rtl/foo.sv` 这样的修改，只有 profile 在 `permissions.writable` 声明 `hw/**` 且没有被 read-only/forbidden 覆盖时才会通过。审计删除必须使用带 `operation = "delete"` 的对象，并匹配 `permissions.deletable`（或已有 writable pattern）；read-only/forbidden 仍然优先。

### `check`

执行 profile `[build.commands]` 中声明的一个项目命令：

```bash
python3 "$CLAUDE_KIT_BIN" check inspect --project-root .
python3 "$CLAUDE_KIT_BIN" check lint --project-root . --confirm
python3 "$CLAUDE_KIT_BIN" check compile --project-root . --confirm --timeout 7200
```

kit 会：

- 使用声明的 argv，不拼接 shell 字符串；
- 保证 cwd 在项目根目录内；
- 拒绝未声明的命令名；
- 对 `confirmation = "required"` 强制要求 `--confirm`；
- 返回 status、argv、cwd、exit code、stdout、stderr 以及 timeout/launch error。

不要在 CLI 中自行拼 simulator 参数。项目专有行为应该放在项目 wrapper 中，并在 profile 中声明。

### `checks` 和 `check-batch`

RTL/DV 改动完成后，先使用 `checks` 查看项目定义的完整选择菜单；该命令
只读，不会执行任何 workload：

```bash
python3 "$CLAUDE_KIT_BIN" checks --project-root .
python3 "$CLAUDE_KIT_BIN" checks --project-root . --json
```

每项会显示标准化 `category`、`selection` policy、是否 `recommended`，以及
是否需要显式确认。profile 中声明的 `syntax`、`lint`、`compile`、`inspect`、
`filelist` 通常会被标为 suggested；`simulation`、`regression`、`coverage`、
`synthesis`、`cdc` 只作为 engineer 的 explicit choice，不会被 kit 自动选中。
category 可以来自 command 的可选 `category`、`kind` 或项目命令名；kit 不需要
知道某个项目 wrapper 的具体命名。如果 check 由 MCP server 提供，则在 profile
中使用 `mcp_server` 和 `mcp_tool` 代替 `argv`。menu 会显示 MCP endpoint；
工程师选择后由 Claude Code 调用项目 server，kit CLI 不会通过 shell 启动 MCP。

工程师完成多选后，使用 `check-batch` 按选择顺序执行，并返回每项 report 和
aggregate counts。默认某项失败后仍继续；需要 fail-fast 时加
`--stop-on-error`。`--report` 会在项目根目录内保存同样的 JSON：

```bash
python3 "$CLAUDE_KIT_BIN" check-batch \
  --project-root . \
  --check lint \
  --check compile \
  --confirm \
  --report out/check-batch.json
```

除非 engineer 已明确批准，不要把 simulation 或 regression 加入选择列表。
Bazel、simulator、license、远程 runner 和 artifact 的细节仍由项目 wrapper
负责。

### `adapter check`

只校验可选 adapter，不调用其项目行为：

```bash
python3 "$CLAUDE_KIT_BIN" adapter check --project-root . --json
```

它检查 adapter 是否能 import、required functions 是否存在、已知函数签名是否接受参数；不会自动 resolve target、启动 test、连接 VIP 或收集 artifact。

### `mcp serve`

通过 stdio 启动薄 MCP bridge。Claude Code 通常由 `.mcp.json` 自动启动；手工执行只适合 bridge 诊断：

```bash
python3 "$CLAUDE_KIT_BIN" mcp serve \
  --project-root . \
  --profile .ai/project.toml
```

默认 bridge 是只读的。除非项目 owner 明确要求，不要加 `--allow-exec`。

## 5. MCP tool 参考

下面的名称就是 Claude Code 应调用的 MCP tools。正常使用时只需要用自然语言描述任务，不需要手写 JSON-RPC。这里的 JSON 是 tool arguments 的结构示例。

### `get_project_profile`

功能：返回经过校验并脱敏的项目 profile 和 validation status。

参数：

```json
{}
```

适用场景：首先确认项目 roots、`hw/` 范围、build commands、artifacts、policies 和当前 validation issues。它不修改文件、不执行命令。

典型 Claude Code prompt：

```text
先调用 get_project_profile。总结 hw、RTL、DV、testbench roots，writable/read-only/forbidden 路径，可用项目命令和 validation issues。不要修改文件。
```

### `list_roles`

功能：列出可复用的工程视角，例如 RTL designer、DV engineer、reviewer、debugger、waveform debugger、VIP integrator 和 evidence reviewer。

参数：

```json
{}
```

返回结果包括 role ID、summary、version 和 source path。适合在任务不明确时选择 role，或在 `plan_task`/`resolve_context` 前确认可选 role。

典型 prompt：

```text
调用 list_roles，为 hw/ 下的 RTL review 和修改推荐最小 role 集合，并解释每个 role 的必要性。
```

### `list_packs`

功能：列出 common、protocol 和 VIP guidance。

参数：

```json
{}
```

可以发现 `protocols.axi4`、`protocols.apb`、`protocols.ethernet`、`vip.generic` 等 ID。pack 提供 review 和 verification guidance，不替代项目真实的 interface、VIP 或 simulator 配置。

典型 prompt：

```text
调用 list_packs。根据项目 profile 中实际存在的协议，为 hw/ 下的任务推荐相关 pack。不要凭空推断协议。
```

### `list_skills`

功能：列出可复用的 Claude Code RTL/DV skill instructions。

参数：

```json
{}
```

skill 是指导内容，不是 executable tool。应该先发现 ID，再按当前任务选择最小集合，不要把所有 skills 都加载进 prompt。

典型 prompt：

```text
调用 list_skills，分别为 RTL change、DV change 和 waveform/debugging 任务推荐最小 skill 集合。不要加载全部 skill。
```

### `list_workflows`

功能：列出任务路由 workflow 及其 routing hints。

参数：

```json
{}
```

当前主要 workflow 包括 `rtl-change`、`dv-change`、`debug`、`protocol-vip`、`review` 和 `handoff`。返回结果还包含默认 roles、skills、preferred commands、keywords 和 protocol hints。

典型 prompt：

```text
调用 list_workflows，说明 hw/ 下的 RTL change 和失败的 DV regression 分别适合哪个 workflow。暂时不要执行。
```

### `plan_task`

功能：把任务路由到 roles、skills、packs、项目检查和 evidence gates，不执行命令。

参数：

```json
{
  "task": "Fix an AXI4 response-channel backpressure timeout in hw/",
  "workflow": "auto",
  "roles": ["rtl-designer", "reviewer"],
  "packs": ["protocols.axi4"]
}
```

只有 `task` 必填。`workflow` 默认是 `auto`；传入 `roles` 或 `packs` 时会覆盖 profile/workflow defaults。`plan_task` 不接受 `skills` 参数，应使用其结果中的 skills 再调用 `resolve_context`。

重点查看返回字段：

- `workflow`：选定 route 和 completion criteria；
- `roles`、`skills`、`packs`：选定的 reusable guidance；
- `check_plan`：profile command 是否 available；
- `check_selection`：engineer-selects、多选和按序返回 report 的策略；
- `missing_facts`：仍缺少的 target、test selector、simulator、source revision 等事实；
- `permissions`：`hw/**` 等路径是否可写；
- `artifacts`、`evidence`：结果位置和证据要求；
- `warnings`：必须解决或明确记录的 gate。

典型 prompt：

```text
使用 plan_task 规划下面的任务：

“修改 hw/ 下最小范围的 RTL，修复 response-channel timeout，
并补充或更新对应的 DV check。”

使用 workflow=auto，只选择 profile 支持的 role 和 protocol pack。
不要运行命令或修改文件。返回 plan、missing facts、权限 gate、evidence 要求，
以及下一步应该加载的具体 skills。
```

### `resolve_context`

功能：根据 profile 和显式选择的 roles、packs、skills，生成任务级 Markdown context 和 source manifest。

参数：

```json
{
  "task": "Review the APB register interface under hw/",
  "roles": ["reviewer"],
  "packs": ["protocols.apb"],
  "skills": ["rtl-dv-context", "rtl-dv-review"]
}
```

所有字段都是可选的。不传 roles/packs 时使用 profile defaults；不传 skills 时不加载 skill guidance，这是为了控制 context 大小。

返回值包含 `context` 和 `manifest`。manifest 记录所选 role、pack、skill 的源路径和 SHA-256 hash。

典型 prompt：

```text
为 hw/ 下的 RTL review 调用 resolve_context。使用 reviewer role、
profile 选定的协议 pack，以及上一轮 plan_task 推荐的最小 skills。
先总结 resolved context，再检查源文件。不要修改任何内容。
```

### `inspect_design`

功能：对 profile `[roots]` 中声明的目录进行只读文件和扩展名统计。

参数：

```json
{}
```

它是有上限的 inventory，不是 RTL parser。结果会报告 `hw`、`rtl`、`dv`、`testbench`、`vendor`、`generated`、`docs` 等 group 的缺失状态、文件数、扩展名、扫描数量和是否截断。

典型 prompt：

```text
调用 inspect_design，报告配置的 hw/ 文件数、扩展名、缺失 roots 和是否截断。
不要读取或修改配置 roots 之外的文件。
```

### `read_artifact`

功能：读取项目根目录内有大小上限的 UTF-8 artifact，例如日志、报告或 evidence。

参数：

```json
{
  "path": "out/logs/smoke.log",
  "max_bytes": 100000
}
```

`path` 必填；`max_bytes` 默认 100,000，最大 1,000,000。返回项目相对路径、原始字节数、是否截断和解码后的文本。逃逸项目根目录或通过不安全 symlink 的路径会被拒绝。

典型 prompt：

```text
使用 read_artifact 读取 out/logs/smoke.log，max_bytes=100000。
提取第一个 failure、最早的相关 warning、可能的阶段和下一步证据。
不要重新运行 workload，也不要修改 artifact。
```

### `review_evidence`

功能：根据 profile 和权限策略校验项目相对路径的 evidence JSON。

参数：

```json
{
  "path": "out/evidence.json",
  "strict": true
}
```

`path` 必填；`strict=true` 会把 warnings 转成 failures。它检查 project identity、task、check status、command evidence、artifact 路径、skipped、risks 和 changed paths。`hw/**` 只有在 writable 且未被 read-only/forbidden 覆盖时才会通过。

典型 prompt：

```text
使用 review_evidence 校验 out/evidence.json，strict=true。
报告每个 issue，包括缺少 command evidence、无效 artifact 和超出 writable scope 的路径。
不要修改 evidence 文件。
```

### `run_check`

功能：通过 profile allowlist 执行一个项目声明的命令。

可用性：默认 MCP bridge 不提供此 tool；只有使用 `--allow-exec` 启动 server 时才会暴露。

参数：

```json
{
  "name": "inspect",
  "confirm": true
}
```

`name` 必须存在于 `[build.commands]`，并且必须传 `confirm=true`。命令自身的 confirmation policy 也仍然生效。优先使用只读的 `inspect`；compile、simulation、regression 和 licensed workload 应继续走项目 wrapper/runner 流程。

典型审批 gate：

```text
暂时不要调用 run_check。先展示 profile 中名为 inspect 的命令定义、cwd、argv、
confirmation policy、预期 artifact，以及为什么它是安全的。等待我的明确批准。
```

### `list_checks`

功能：返回和 CLI `checks` 相同的只读 check menu，供 engineer 选择。

参数：

```json
{}
```

在 RTL 或 DV environment 改动完成后使用它展示菜单，然后询问 engineer 需要
选择哪些 names。`recommended` 只是建议，不是自动执行授权；simulation、
regression、coverage、synthesis、CDC 也不能因为出现在菜单中就自动加入。

### `run_checks`

功能：按 engineer 选择的顺序执行多个 profile command，并返回每项 report 与
aggregate counts。

可用性：默认 MCP bridge 不提供此 tool；只有使用 `--allow-exec` 启动 server
时才会暴露。

参数：

```json
{
  "names": ["lint", "compile"],
  "confirm": true,
  "timeout": 3600,
  "stop_on_error": false
}
```

`names` 必须是 `[build.commands]` 中已登记且不重复的命令名。返回结果保留选择
顺序，并统计 `passed`、`failed`、`blocked`、`not_run`。`confirm=true` 表示确认
执行这一批；simulation 和 regression 仍有各自的显式确认 gate。加入 expensive
workload 前先询问，或在获得明确委托后交给项目批准的 `commander` 流程。MCP-backed
entry 由 CLI 标为 blocked，因为实际 tool call 应由 Claude Code 完成；请使用
`list_checks` 返回的 server/tool。

## 6. Claude Code 常用 prompt

### 验证连接和 catalogs

在消费项目根目录启动 Claude Code 后粘贴：

```text
使用 claude-kit MCP，不要只使用 shell inspection。

1. 调用 get_project_profile。
2. 调用 list_roles、list_packs、list_skills、list_workflows。
3. 确认 hw/ 是否是配置的 root，以及 hw/** 是否 writable。
4. 为 hw/ 下的 RTL change 推荐最小 role、skill、pack 集合。
5. 列出本轮实际调用的 MCP tools 和 profile issue。

这是只读 discovery 任务。不要修改文件，也不要运行 build、compile、simulation、
regression 或 licensed command。
```

### 在 `hw/` RTL 修改前规划

```text
先调用 get_project_profile 和 inspect_design。
然后使用 plan_task 规划：

“实现 hw/ 下请求的 RTL 行为，识别对应的 DV coverage/check 变化，
并保持现有 protocol contract。”

只使用 kit 返回的 roles、skills 和 packs。暂时不要编辑文件。
返回实际作用范围、missing facts、允许的命令、evidence 要求和最小安全下一步。
```

### 为协议 review 解析 context

```text
使用 list_packs 找到项目实际相关的 protocol pack。
使用 resolve_context 加载 reviewer、该 protocol pack 和最小的 review/context skills。
然后只检查配置的 hw/ root 下的文件，并用文件路径和行号报告 findings。

不要修改文件，也不要推断 profile 或源码中不存在的协议。
```

### Review 已完成的 check

```text
使用 read_artifact 读取项目日志，使用 review_evidence 校验证据 JSON。
总结 passed、failed、skipped、blocked、warnings、可能的 root cause 和未解决风险。
每个结论都要绑定到 artifact 或 command result。不要重新运行 workload，
不要修改 source、log 或 evidence。
```

### 从 plan 安全进入修改

```text
plan 已批准。修改前：

1. 重新确认 profile 和 writable scope。
2. RTL implementation 变化保持在 hw/**，除非 profile 明确授权其他路径。
3. 只使用已选择的 RTL/DV skills 和 protocol pack。
4. 先展示准备修改的文件列表和 patch 摘要。
5. 修改后 review diff，并为每个 check 生成 evidence。

不要修改 vendor、generated、build、.git、secret 或 read-only 路径。
```

## 7. `hw/` 的 profile 配置

如果项目的 implementation 位于 `hw/`，至少应有：

```toml
[roots]
hw = ["hw"]
dv = ["dv"]
testbench = ["tb"]
docs = ["docs"]
vendor = ["third_party_vip"]
generated = ["generated", "out"]

[permissions]
writable = ["hw/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]
```

如果项目还保留独立的 `rtl/`，再加入 `rtl = ["rtl"]` 和 `rtl/**`。不要因为某个目录存在就扩大 writable scope。

校验：

```bash
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json
python3 "$CLAUDE_KIT_BIN" inspect --project-root . --json
```

如果 strict evidence 报告 `hw/... is outside the writable scope`，检查配置而不是绕过校验：

1. 需要被 inspect 时，`[roots]` 下是否有 `hw = ["hw"]`？
2. `permissions.writable` 中是否有 `hw/**`？
3. 是否有更宽或更窄的 pattern 把同一路径放进 `read_only` 或 `forbidden`？
4. 路径是否确实位于项目根目录内，并且不是逃逸 symlink？

## 8. Claude Code 的 MCP 配置

生成的 `.mcp.json` entry：

```json
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
```

它只负责连接 bridge。profile、adapter、项目 commands、simulator setup、远程 runner 和 evidence 位置仍然由项目负责。

在 Claude Code 中使用客户端的 MCP status view，或在支持时输入 `/mcp` 检查连接。如果 server 没有出现：

```bash
python3 third_party/claude_kit/bin/claude-kit doctor \
  --project-root . \
  --profile .ai/project.toml \
  --strict \
  --json
```

然后检查 `.mcp.json`、submodule 路径和 MCP 配置使用的 Python。正常运行 kit 不需要额外安装 Python MCP SDK，bridge 已经包含 stdio framing 支持。

## 9. 常见问题

### Claude Code 没有调用 kit tool

从项目根目录启动 Claude Code，确认 `claude-kit` server 已连接。明确要求调用 `get_project_profile` 或 `list_skills`，并要求输出实际调用的 tool。只出现 shell 命令不代表 MCP 已被使用。

### `bin/claude-kit` 报 permission error

使用：

```bash
python3 third_party/claude_kit/bin/claude-kit version
```

wrapper 虽然有 Python shebang，但 checkout 可能没有 executable bit；使用 `python3` 最稳定。

### `doctor` 找不到 profile

从消费项目根目录执行，或同时指定两个路径：

```bash
python3 "$CLAUDE_KIT_BIN" doctor \
  --project-root /path/to/consumer-project \
  --profile .ai/project.toml \
  --strict
```

### `inspect_design` 没有显示 `hw`

`permissions.writable` 和 `[roots]` 是两套配置。添加 `hw = ["hw"]` 后重新运行 `doctor` 和 `inspect`。

### `hw/` 下的改动被拒绝

把 `hw/**` 加入 `permissions.writable`，删除与 `read_only` 或 `forbidden` 的重叠，然后重新 strict 校验。不要通过弱化 evidence 校验解决 profile 错误。

### `plan_task` 报告 missing commands 或 missing facts

planner 不会猜测 target、simulator、test selector、source revision 或项目 wrapper。把事实写入 `.ai/project.toml`，实现项目自己的 adapter/wrapper，或者将其明确记录为 blocked/skipped 并给出原因。

### `resolve_context` 中没有 skill 内容

skills 是显式选择的。给 MCP `resolve_context` 传 `skills` array，或者 CLI `context` 使用 `--skill <id>`。先加载最小相关集合。

### `read_artifact` 拒绝路径或输出被截断

使用项目根目录内的项目相对路径。大日志应分段读取，或把 `max_bytes` 提高到不超过 1,000,000。工具会有意拒绝项目根目录之外的路径。

### `check` 或 `run_check` 被拒绝

确认命令存在于 `[build.commands]`、cwd 存在，并满足 confirmation policy。
`kind = "simulation"` 或 `kind = "regression"` 的命令无论 profile 中是否为
optional，都必须使用 `--confirm`（`run_check` 使用 `confirm=true`）。默认 MCP
bridge 不暴露 `run_check`，这是有意的安全边界。

### MCP startup timeout

检查 MCP command 使用的是固定 submodule 路径、`python3`、正确的项目 root 和 `.ai/project.toml`。单独运行 `doctor` 检查 profile。手工执行 `mcp serve` 只用于收集 bridge diagnostics，不是日常工作流。

## 10. 源码和扩展入口

最有用的实现和文档文件：

```text
README.md
README.zh-CN.md
docs/command-reference.md
docs/command-reference.zh-CN.md
src/claude_kit/cli.py
src/claude_kit/mcp_server.py
src/claude_kit/core.py
src/claude_kit/resources/templates/project.toml
src/claude_kit/resources/templates/SKILL.md
src/claude_kit/resources/claude/CLAUDE.md
src/claude_kit/resources/roles/
src/claude_kit/resources/skills/
src/claude_kit/resources/packs/
src/claude_kit/resources/workflows/catalog.json
tests/test_cli.py
tests/test_mcp.py
tests/test_core.py
```

MCP schema 在 `src/claude_kit/mcp_server.py`；profile、路径、planner、artifact、command 和 evidence 的具体行为在 `src/claude_kit/core.py`；tests 是可执行的调用示例。公共命令或 tool contract 变化时，应同步更新 tests 和本参考文档。

## 11. 推荐验证循环

普通 RTL/DV 任务可以按以下顺序：

```text
1. 从项目根目录启动 Claude Code。
2. 确认 claude-kit MCP 连接。
3. get_project_profile。
4. inspect_design。
5. plan_task。
6. 用选定的 roles、packs、skills 调用 resolve_context。
7. 检查相关 hw/**、DV 和 testbench 文件。
8. 获得准备修改范围的批准。
9. 只修改 profile 授权的路径。
10. review diff。
11. 只通过项目批准流程运行 profile 声明的 checks。
12. 使用 read_artifact 和 review_evidence。
13. 报告改动、命令、结果、跳过的检查和风险。
```

这套流程让 Claude Code 保持主入口，让 `hw/**` 成为一等工作范围，并保持 kit 通用能力与项目专有 RTL/DV 执行之间的可复现边界。
