# xverif 集成

`xverif` 是一个可选的外部 provider，用于获取确定性的 RTL/DV 证据。kit
只携带 Claude-facing skills 和固定版本的集成契约，不携带 xverif runtime、
EDA 数据库、Verdi/NPI 库或 license 配置。

## 同步内容

provider 记录在
`src/claude_kit/resources/providers/xverif/provider.json`，当前固定到
[BLANK2077/xverif](https://github.com/BLANK2077/xverif) 的
`214e9cc81ba5ffe0010f5f4f2e0d6e4cfae40de6`。

同步了五个 Claude skill：

| Skill | 用途 |
| --- | --- |
| `xverif` | 路由设计、波形、协议、coverage、bit、entry、位置和 SVA 查询。 |
| `xverif-admin` | MCP session 生命周期、direct/LSF backend、transport、timeout、license 和启动排障。 |
| `x-npi` | 获得授权后的 Python NPI 分析和有界 URG/coverage 辅助流程。 |
| `xsimdebug` | 只有 log 或 xdebug 证据不足时，才通过 PTY 调试 VCS UCLI 或 Xcelium/Xrun。 |
| `xwiki` | 获得授权后维护验证项目长期知识。 |

每个 skill 的完整目录都会同步，包括 `references/` 和辅助文件。不能只复制
`SKILL.md`，否则其中的相对引用会断掉。

在 kit checkout 中查询：

```bash
python third_party/claude_kit/bin/claude-kit list providers
python third_party/claude_kit/bin/claude-kit list providers --json
python third_party/claude_kit/bin/claude-kit list skills
```

## 消费项目接入

把 kit 固定为 submodule 后，在项目中 materialize skills。`sync` 可以重复运行；
不加 `--force` 时会保留已有文件。

```bash
git submodule add https://github.com/Lightelligence/claude_kit.git third_party/claude_kit
git -C third_party/claude_kit checkout <reviewed-claude-kit-commit>
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-adapter \
  --with-mcp \
  --no-skills
python third_party/claude_kit/bin/claude-kit sync --project-root .
```

`init --with-mcp` 只增加 `claude-kit` server，不会增加或替换外部的 `xverif`
server。`xverif` 应由消费项目在自己的 `.mcp.json` 中配置，项目在那里提供
licensed checkout、Python 环境、Verdi 安装和 scheduler 参数。

## MCP 契约

上游 server 的启动入口是 `python -m xverif_mcp.server`。项目也可以使用自己的
wrapper，但要保持同一环境和 MCP contract。direct 模式示例：

```json
{
  "mcpServers": {
    "xverif": {
      "type": "stdio",
      "command": "<python-3.11>",
      "args": ["-m", "xverif_mcp.server"],
      "env": {
        "PYTHONPATH": "<xverif-root>/xverif_mcp/src:<xverif-root>",
        "XVERIF_HOME": "<xverif-root>",
        "XVERIF_MCP_BACKEND": "direct",
        "VERDI_HOME": "<licensed-verdi-root>"
      }
    }
  }
}
```

LSF 模式把 `XVERIF_MCP_BACKEND` 设为 `lsf`，并确保项目批准的 LSF/simulation
launcher 把完整的 LSF、Verdi 和 license 环境传给 xverif 进程。不要假设一个
单独启动的 MCP 进程会自动获得 simulation job 后来才加载的变量。不要把真实
凭证或 site-specific 绝对路径放进 `claude_kit`；应放在消费项目未跟踪的本地
配置或批准的 secret 机制中。

### Vendor 环境加载时机和进程边界

普通 Claude Code shell 不需要手工 export `VERDI_HOME` 或 `VCS_HOME`。有些项目
只有在显式选择 simulation、由项目注册的 `simmer` 或 simulation launcher 启动
之后，才会加载这些 vendor 变量。kit 不会为了准备环境而自动运行 simulation。

需要 Verdi/VCS 的 xdebug action 必须运行在同一个已批准的 simulation 环境中启动
的 xverif MCP 进程里，或者运行在能够继承该环境的项目批准 wrapper/LSF launcher
里。单独启动的 `simmer` 进程不能回头更新已经运行的 MCP 子进程。如果 MCP server
早于 vendor 环境启动，应在选择 simulation 后使用项目支持的 MCP reload/restart
路径；不要通过把 site path 或 credential 写进 kit 来绕过这个进程边界。direct
示例中的 `VERDI_HOME`/`VCS_HOME` 只是有环境感知能力的 launcher 的占位符，并不
要求每一次普通 Claude Code 会话都手工设置。

### Native/runtime 版本兼容性 preflight

`XVERIF_HOME` 下的 Python `xverif_mcp` adapter 和 native `xdebug` executable
是一个有版本关系的组合。更新复制到 kit 的 skill 或 Python adapter 并不会自动
重建已有的 native executable。因此，当 native executable 不能提供 canonical
action guide 时，adapter 会 fail closed，避免 Claude Code 根据不完整或过期的
catalog 选择 action。

管理员可以在批准的、已经加载 vendor 环境的环境中，先执行下面这个只读 preflight，
再注册 MCP server：

```bash
printf '%s\n' \
  '{"api_version":"xdebug.v1","action":"actions","args":{"output":{"view":"guide"}}}' \
  | "$XVERIF_HOME/tools/xdebug" --json -
```

兼容的 runtime 应返回 `summary.view` 为 `guide`、非空的 `data.guide`，以及对应
的 guide 字节数和 action 行数。如果命令成功退出，却在收到
`output.view=guide` 后仍返回 compact 的 `data.actions`，说明 native binary
早于 action-guide 契约。应当用 Python MCP checkout 所使用的同一个 upstream source
revision 重建 native `xdebug` target，或者把 `XVERIF_HOME` 指向匹配的已安装 build。
不要放宽 MCP 校验、不要把 vendor binary 复制进本仓库，也不要把 compact action list
当成等价证据。

upstream xdebug 当前文档把 Verdi `V-2023.12-SP2` 列为测试基线，并明确提醒
不同 Verdi release 的 NPI signature 可能不同。应在与 MCP process 相同的、已获
授权的环境中，用完全相同的 source revision 构建：

```bash
cd <xverif-root>
make -C xdebug
```

如果源码编译通过、但链接阶段出现缺少 `npi_fsdb_*` 或 `npi_util_*` symbol，说明
当前安装的 Verdi/NPI release 与该 xdebug revision 不兼容。应选择导出所需 NPI API
的安装，或请 xverif owner 提供经过 review 的兼容性修改。不要把 proprietary library
复制进 `claude_kit`，也不要仅凭 MCP 注册成功或 compact action-list probe 就声称
provider 完全可用。ETX runner 的可选 `isolated-source-build` 模式会先检查 NPI 导出；
找不到兼容的本地 Verdi 时会快速失败，并上传诊断 artifact。

如果希望 profile 显示 provider 关系，可以加：

```toml
[providers.xverif]
enabled = true
server = "xverif"
backend = "direct"
skills = ["xverif", "xverif-admin"]
required_tools = [
  "xverif_tools",
  "xverif_debug_get_schema",
  "xverif_debug_query"
]
```

这段只是 metadata 和 validation，不会启动 MCP server，也不代表当前一定有
license 或 xverif checkout。

## Claude Code 使用流程

注册 `xverif` MCP server 后，在 Claude Code 中按以下顺序使用：

1. xdebug 任务先调用一次 `xverif_tools`，读取完整 action guide。
2. 对选中的 action 调用 `xverif_debug_get_schema`，不要猜字段，也不要把 native
   JSON envelope 直接塞进 MCP 参数。
3. 对需要 daidir/FSDB 资源的查询先打开 managed session。
4. 先执行能够区分当前假设的最小 `xverif_debug_query`，有证据后再扩大范围。
5. 保存需要的 export/evidence 后关闭 session。
6. 报告 action/tool、signal 或 interface、time/range、source evidence、完整性字段、
   unknowns 和 artifact 路径。

启动、transport、timeout、session 或 LSF 问题使用 `xverif-admin`。不要静默 retry、
reopen、切换 backend 或换数据源。只有确实需要 live simulator session，且 log/xdebug
事实无法回答问题时，才使用 `xsimdebug`。

## 与项目 check 的关系

xverif 是诊断/evidence provider，不替代项目注册的 build/DV MCP tools。项目可以把
逻辑 check 映射到已有 xverif MCP tool：

```toml
[build.commands.waveform_debug]
category = "inspect"
mcp_server = "xverif"
mcp_tool = "xverif_debug_query"
```

映射必须符合真实项目 contract；不能用泛化的 `waveform_debug` 去发明 action、session
或 signal，也不能用 xverif 代替项目的 build/compile/simulation。`claude-kit checks`
仍负责项目 check menu；simulation、regression、coverage、synthesis 和 CDC 仍是显式选择。

## 更新和 provenance

上游变化时，要同时更新 skill 目录和 provider manifest，记录精确 commit、同步路径和
本地验证结果。不要只把 manifest 改成 `master` 而不固定 commit。

消费项目更新 submodule 前执行：

```bash
python third_party/claude_kit/bin/claude-kit list providers --json
python third_party/claude_kit/bin/claude-kit doctor --project-root . --strict
python third_party/claude_kit/bin/claude-kit sync --project-root . --force
python third_party/claude_kit/bin/claude-kit context \
  --project-root . \
  --skill xverif \
  --task "规划确定性的波形证据，不运行 simulation"
```

然后通过项目已有的 MCP smoke/validation 路径测试真实 xverif server。如果 validation
包含依赖 vendor 的 xdebug action，应当在启动 MCP 进程的同一个批准的
simulation/simmer 环境中执行 probe。kit-only pass 只能证明 metadata、skill
materialization 和 profile contract 正确，不能证明 Verdi/NPI 或 licensed waveform
access 可用。
