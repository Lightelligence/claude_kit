# RTL / DV 精简入口

[English](rtl-dv-entrypoints.md)

先按任务选择入口，不要求工程师记住全部 server。两个可选模板分别提供四个原生
Claude skills；底层指导继续共用，不改 MCP server/tool ID，也不新增后台服务。

| 工作 | RTL 模板 | DV 模板 | 边界 |
| --- | --- | --- | --- |
| 实现 | `rtl-design` | `dv-test` | 指定范围修改，不默认仿真 |
| 审查 | `rtl-review` | `dv-review` | 只读；分别关注 RTL 逻辑与激励/checker/coverage |
| 故障分析 | `sim-debug` | `sim-debug` | 先看已有编译/仿真证据，不自动重跑 |
| 项目事实 | `project-context` | `project-context` | 只补缺失信息，不做每次任务必跑的启动流程 |

`dv-test` 包括 UVM env、sequence、test、scoreboard、checker，不仅是新建 test 文件。
两个 review 入口共用 `rtl-dv-review`，但有独立的发现描述和任务范围。
原 catalog ID 及旧 CLI/MCP 请求不变。这些新名称必须实际接入后才能在 Claude 中使用；
更新 submodule 不会自动给已有项目安装新入口。

## 接入与迁移

模板位于 `src/claude_kit/resources/templates/`：

- `kit-attachment.rtl-focused.toml`
- `kit-attachment.dv-focused.toml`

新建/选择性接入时，把选定模板保存为 `.claude/kit-attachment.toml` 并调整 `kit_path`。
模板不管理 MCP、project profile 或权限，也不创建 agents。
已有 manifest 需要合并选择，不能直接覆盖，尤其不能丢掉 `framework = "soc"`、
排除项、项目别名、规则和运行脚本。

```bash
python third_party/claude_kit/bin/claude-kit attach --project-root . \
  --manifest .claude/kit-attachment.toml --dry-run
```

核对冲突和 retired paths 后，才在空闲 checkout 应用。`attach` 不删除旧文件；
只缩短 manifest 不会让已有 30 多个 skills 自动变成 4 个。迁移时逐项核对旧入口的
所有者、用户改动和引用，用 Git 保留可恢复记录。不要对共享链接执行 `sync --force`。

新增的别名写法仍兼容原来的字符串形式：

```toml
[aliases.skills.dv-review]
resource = "rtl-dv-review"
description = "Read-only DV review of stimulus, checkers and coverage."
scope = "Review the requested DV changes; consult RTL only as context. Do not run EDA."
```

`description` 用于原生发现，`scope` 限定读取共享指导后的任务范围；二者都不增加权限，
也不是安全沙箱。这是指导包装，不完整继承源 skill 的执行元数据。
随附模板引用的技能没有独立的原生执行元数据；带特殊调用设置的其它技能应保留原入口。

## 不要把 skill 分组当成 MCP 工具隔离

- `rtl`、`dv` 使用同一个 build/LSP server 可以是合理复用，但同样的 server 集合不会自动过滤其内部工具。
- `session --tools <profile>` 只选 MCP servers，不选 skills、plugins 或 hooks。
- RTL lint 只检查 RTL；DV 编译负责 TB syntax/elaboration，不等于仿真。
- 单次仿真、regression、coverage、综合、CDC 和生成器，继续按工程师明确选择执行。
- 不为改名字注册两套相同 MCP；Make/Bazel、RTL top 生成/构建图查询的不同语义不应混合。

检查菜单支持 `list_checks({"scope":"dv"})` 或
`list_catalog({"category":"checks","scope":"dv"})`，也可选择 `rtl`、`rtl-dv`。
`scope` 按命令的 `applies_to` 调整推荐，保留全部命令供明确选择，不改变执行权限和确认要求。
省略 `scope` 保留原菜单；只有 checks catalog 接受此参数。

## 审计与验收

```bash
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --format markdown
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --tools dv
```

审计同时列出项目/local settings 的启用与禁用声明及来源，不推断最终加载状态。
新增提示覆盖相同的 server profiles、选择与禁用冲突、项目清单中找不到的名称、
旧兼容入口和 Make/Bazel 双入口。两个不同范围的 review 包装共用同一份指导是合理的，
同源提示只是人工审查候选，不自动删文件。

最后需要在指定 Claude 版本核对原生 skill 发现和 `/mcp`。文件字节数、入口数量，
都不能代替 token、耗时或业务质量的实测。

## Claude 对话示例

```text
/rtl-review Review only the reset and ready/valid changes in <RTL paths>.
Use the specification and relevant test evidence. Do not modify files or run EDA.
```

```text
/dv-test Add <scenario> using the existing sequence and scoreboard APIs.
Do not simulate. Show relevant validation choices; do not add RTL lint for a DV-only edit.
```

```text
/dv-review Review <DV diff> for stimulus gaps, checker validity and coverage.
Consult RTL only where needed to establish expected behavior. Do not run EDA.
```

```text
/sim-debug Investigate this existing failure: <run and bounded log path>.
Separate observed facts from hypotheses. Do not rerun simulation without my selection.
```
