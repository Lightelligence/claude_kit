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

LSF 模式把 `XVERIF_MCP_BACKEND` 设为 `lsf`，并提供项目完整的 LSF、Verdi 和
license 环境。不要把真实凭证或 site-specific 绝对路径放进 `claude_kit`。

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

然后通过项目已有的 MCP smoke/validation 路径测试真实 xverif server。kit-only pass
只能证明 metadata、skill materialization 和 profile contract 正确，不能证明 Verdi/NPI
或 licensed waveform access 可用。
