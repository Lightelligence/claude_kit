# 精简项目的 MCP、skills 和 plugins

需要明确区分 RTL / DV 日常入口时，使用[精简入口模板与英文示例](rtl-dv-entrypoints.zh-CN.md)。
已有 framework 需要审查迁移，不能直接覆盖 manifest 或把更新 pin 当成入口已经退休。

目标是让日常 DV 工作只看到常用入口，按任务打开其余能力。
`claude_kit` 作为固定版本的 submodule 提供共享指引和检查；项目保留自己的
工具路径、EDA 配置和权限。下面是建议的起点，不是对某个现场环境的验收结果。

| 层 | 建议默认 | 按需增加 |
| --- | --- | --- |
| MCP | kit compact、项目 build、项目 LSP | 分析既有波形/coverage 时选 xverif；生成器和外部服务只在任务需要时选 |
| Skills | rtl-dv-kit、dv-engineering、rtl-dv-debugging、rtl-dv-review | regression、evidence、协议/VIP、formal 等专项指引 |
| Plugins | 项目确实使用、且没有重复提供同一能力的插件 | 插件携带的 skills、MCP、hooks 一起核对 |
| 项目说明 | 稳定的入口、目录约束、工具选择和验证规则 | 模块细节放在对应文件，任务需要时读 |

`rtl-dv-kit` 是入口指引，另外三个是常用工作指引。不把所有 skills 的正文复制进
CLAUDE.md；不让同一份 kit 同时通过全局安装、项目链接和 plugin 重复提供。
有独立职责的 build、LSP、debug server 可以保留，无需为了数量少而合并实现。

## 1. 先看项目配置清单

在消费项目根目录，用 Python >=3.11 执行：

```bash
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --format markdown
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --tools debug
```

默认输出 JSON；`--tools` 只比较已有 task profile 的选择，不启动会话。退出码
`0` 表示清单生成成功（可以有 findings），`2` 表示输入错误。

读取范围：项目 `.mcp.json`、`.claude/tool-profiles.json` 及其指定目录文件、
`.claude/skills/*/SKILL.md`、rules、agents、两个 CLAUDE.md 和项目/local settings。
支持共享 skill 的目录链接，只读入口，不递归读取 references 或执行代码。
报告不输出 MCP 的 command/args/env/URL/headers、hook 命令或文档正文。

报告重点包括：

- `default`：在项目 `.mcp.json` 声明；`on_demand`：只在目录和 task profile 中；
  `unassigned`：目录中有，但尚未被 profile 选中。
- 默认配置与工具目录的差异、完全相同的 MCP 定义、同名/正文相同的 skill 入口。
  相同入口仅为重复候选，支持文件、版本和用途可能不同，不能据此自动删除。
- 插件启用声明、MCP 禁用声明及其文件来源。项目与 local 声明分别保留，
  不推断最终生效状态。
- 文件字节数。这不是实际 token 或上下文占用；front matter 使用 kit 的简易解析器，
  不能替代 Claude 对 YAML 和加载状态的判断。

工具不读取用户/托管设置、CLI 覆盖、同步 skills、旧 commands 目录或插件内部资源。
零条项目配置也不表示会话零工具。最终需在实际 Claude 会话中核对 MCP、skills 和
plugins；连接成功、工具可列出、业务验证成功是三个不同结论。

## 2. 只接入常用 skills

模板位于 submodule 的
`src/claude_kit/resources/templates/kit-attachment.dv-minimal.toml`。
首次接入时将它保存为项目 `.claude/kit-attachment.toml`，调整 `kit_path`。
已有 manifest 时合并所需字段，保留项目别名及必要专项资源，不直接覆盖。

```bash
python third_party/claude_kit/bin/claude-kit attach --project-root . \
  --manifest .claude/kit-attachment.toml --dry-run
python third_party/claude_kit/bin/claude-kit attach --project-root . \
  --manifest .claude/kit-attachment.toml
```

模板仅选择四个 skills，不接入 roles，不管理 MCP 和 project profile。
它不创建项目事实；已有 `.claude/project.toml` 继续由项目维护。
`attach` 会报告 retired resources，**不会删除旧入口**：从完整安装迁移时，
逐项确认旧链接的所有者和用途后再移出原生发现目录，随后重新审计。
仅缩短 manifest 不会自动减少已经存在的 skills，也不会禁用全局插件。

## 3. 按任务选择 MCP

另一个模板为 `src/claude_kit/resources/templates/tool-profiles.dv-minimal.json`。
保存为项目 `.claude/tool-profiles.json`，与已有 profiles 合并，并调整 server 名称。
模板中的 `soc-build-bazel` 等名称只是示例，必须与本项目实际注册名称一致；
不要将 Make/Bazel 后端混用。

完整配置放在项目 `.claude/mcp-catalog.json`，结构仍是 `{"mcpServers": {...}}`。
普通 `.mcp.json` 只保留默认子集，同名定义应一致。保留已有的安全凭证引用；
不要把运行期凭证复制进共享 kit。模板不生成 server 启动配置。

| Profile | 工具选择 | 使用场景 |
| --- | --- | --- |
| daily | kit、build、LSP | DV 修改、定位、指定检查 |
| debug | kit、xverif | 已有日志/波形/coverage 分析；需要修改或重跑时再加 build/LSP |
| closure | kit、build、LSP、xverif | 需求级证据收集与评审 |

```bash
python third_party/claude_kit/bin/claude-kit tool-profiles --project-root .
python third_party/claude_kit/bin/claude-kit session --project-root . --tools debug
```

`session` 生成临时 MCP 子集并启动原生 Claude；它不切换 skills、plugins 或 hooks。
kit MCP 的 `--tool-profile compact` 缩小 kit 的工具表；项目 `--tools debug`
选择 server 集合，两者不是同一层。检查实际会话加载情况后再运行任务。

## 4. 用实际任务判断是否更高效

用同一基线、相同模型和三类代表任务比较精简前后：DV 小修改、已有失败分析、
coverage 缺口评审。记录工具调用次数、重复读文件次数、会话实际上下文、完成耗时、
需要人工纠正的次数及验证结果。工具少只是手段，不能以遗漏必要检查换速度。

原生 skills 默认按描述发现，正文按需加载；手动专用 skill 可按需要设置
`disable-model-invocation: true`，但不建议把核心 DV 指引全部改成手动。
具体行为见 [Claude skills 文档](https://code.claude.com/docs/en/skills)。
MCP 的延迟发现支持情况需以当前客户端和模型网关为准，见
[MCP 文档](https://code.claude.com/docs/en/mcp)；插件可能同时携带多种资源，见
[plugins 文档](https://code.claude.com/docs/en/plugins)。
