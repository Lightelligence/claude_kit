# 工具验证快照

[English](tool-verification.md) · [功能、区别与英文 prompts](tool-selection.zh-CN.md)

本页按需查阅，不加入每次 Claude 启动上下文。2026-09-14 的实际快照
`34810635715` 对应 consumer `2e6e585`、功能版 kit `164fe15`。
验收只覆盖明确记录的用例，不代表每个参数、所有设计或所有 agent 工作流通过。

用户要求停止新增测试后直接交付。本轮最终指令修改没有再做原生 Claude 行为验证。
此前中间候选的核心 39 项、MCP 3 项、适配 6 项检查通过，不是最终 consumer 的端到端
验收。此次指令修改没有新增仿真或外部数据写操作。

## 当前清单与可用范围

完整 catalog 有 **17 个 MCP servers**；默认只启用 **3 个、23 个 tools**。
历史 218-tool 清单包含可选 stdio 服务，不是默认上下文。schema 字节数不是 token 数。

| Server | 默认 | 功能与实际验收范围 |
| --- | --- | --- |
| `claude-kit` | 是 | 项目上下文、证据和目录查询；原生 Claude 实际调用通过。紧凑版 9 tools、2,523 schema 字节 |
| `soc-build-bazel` | 是 | Bazel 执行；实际 RTL-only VCS lint 完成编译链接，报告 21 条设计 warning，因此检查失败，不是设计通过。DV 编译和仿真是不同操作 |
| `soc-lsp` | 是 | 4 个文件导航工具，两个 workspace 的 8 次调用通过；不是编译器 |
| `soc-integrate-bazel` | 否 | 7 项只读构建图/vendor 操作；解析 24 个 vendor repo，仍缺 3 个项目 IP 路径 |
| `silicon-crew:soc-build` | 否 | Make 项目：10 项实际用例通过，包含生成 wrapper 的 VCS 编译；不替代 Bazel |
| `silicon-crew:soc-integrate` | 否 | 10 tools、15 项生命周期/反例通过，参数化 wrapper 编译通过；不是完整 SV 或全芯片 signoff |
| `silicon-crew:yml2reg` | 否 | 13 个入口生成产物；随附 APB/AHB/DAB RTL 编译通过；RAL 暂缓 |
| `silicon-crew:gen-asic-memmap` | 否 | 地址图实际生成，适用格式可解析；不等于项目地址空间 signoff |
| `silicon-crew:gen-memwrap` | 否 | 现有 consumer 生成器的 96×24→128×32 定向 HDL 用例通过；新版导出适配器另外依赖 ORFS，不能自动替换 |
| `silicon-crew:excel-yml-gen` | 否 | Excel 转换实际生成产物；不等于总线语义验证 |
| `silicon-crew:crg-req-to-design` | 否 | 需求到设计表实际生成；PLL/时钟架构仍需工程师审核 |
| `silicon-crew:crg-gen` | 否 | 共享 CSR：205 个连接/端口一致，VCS 编译展开和 AHB 错误传播通过；完整 CRG 暂缓 |
| `silicon-crew:cr-tree-diag-gen` | 否 | 本地图形生成、Draw.io XML/Excalidraw JSON 解析通过；未验视觉布局，不是远端 HTTP 绘图服务 |
| `silicon-crew:soc-openroad` | 否 | 隔离 config/SDC 生成和 status 通过；缺少 ORFS，综合未通过 |
| `xverif` | 否 | bit、SVA、entry、日志定位、FSDB 定向查询通过；原生 NPI 打开 coverage DB 失败，隔离 parser 修复未部署共享安装 |
| `atlassian-dc` | 否 | 98 tools、115,008 compact-JSON UTF-8 schema 字节；本人 profile 实际查询通过（`34810934608`），不证明其它操作通过 |
| `drawio` | 否 | 用户已要求停止处理。保留证据：HTTP 403，隔离原生 Claude 启动 150 秒超时（`34811483486`）；无业务调用成功证据 |

详细历史证据见[能力矩阵](tool-selection.zh-CN.md#etx-验证范围更新于-2026-09-14)。
原始工具/厂商日志及服务响应保留在私有 ETX 隔离目录，不放入本仓库。

## Skills、Agents 和脚本

同一快照含 **30 个 skills、9 个 agents**。检查到的指令/工程师文档中的本地
Markdown 链接均在真实 checkout 存在；这不证明自动选择、行为质量或全部工作流。
项目专有清单和约定保留在 `.claude/docs/SKILLS.md`，不复制进通用 kit 启动规则。

- Skill 是工作方法，MCP tool 是执行接口，agent 是分工，script 是实现或维护入口。
- Make/Bazel、RTL 集成/构建图、离线波形/运行时控制语义不同，应保留清晰路由。
- `xwiki`、`lib-db-gen` 不是额外 MCP。Library 的 7 个实际 `--no-run` 准备用例通过，
  `.db` 编译仍需真实 compiler/license。
- 共享 xwiki `cc839de` 的实际 helpers 通过 7 项隔离用例（`34811483486`）：
  未提供路径时报错、dry-run 不写入、生成 15 个有效骨架文件、保留已有文件、
  拒绝无效 object_type、拒绝断链、恢复后校验通过。未 ingest 项目或修改真实 wiki。
- 7 个项目 Claude helpers 已迁移到 `.claude/scripts/`，旧根目录入口仅作兼容；
  通用构建工具不随意迁移。

## 未通过、未测与暂缓

**用户要求暂缓：** RAL adapter/可移植性、完整 CRG top 的真实单元集成。
本轮文档收尾和其它工具验收不再修这两项。CSR 编译通过不能写成完整 CRG 通过。

**外部条件或有意未执行：** 原生 NPI 数据库打开崩溃、ORFS 缺失、3 个 IP 路径缺失、
库编译器/license、运行中模拟器控制、Jira/Confluence 写操作、
图形视觉检查、完整项目语义和无限制 agent 工作流。没有换后端、补假单元、
启动仿真、创建工单或更改凭据来制造“通过”。
Draw.io、gen-memwrap、xsimdebug、lib-db-gen、rtl-design 已按用户要求排除，
不再重试或修复；已发现的相关指令问题保留未解决状态。
新发现的 gen-memwrap skill YAML 问题保留未修；之前的生成器定向测试不能证明 skill 加载成功。

[xverif PR 2](https://github.com/Lightelligence/xverif/pull/2) 和
[PR 3](https://github.com/Lightelligence/xverif/pull/3) 的独立源修复仍待审，
更新 kit pin 不等于部署这些修复。

## 怎样高效使用

日常直接启动 Claude Code，保持默认三个 servers；debug、生成器或协作需求才选择
对应 profile，用 `/mcp` 确认。只查相关 schema，限制查询范围、批量读取，复用已验证
上下文。普通 RTL/DV 编辑不要加载 98 个 Atlassian tools。

以下是 Claude 对话 prompts，不是终端命令：

```text
Explain which currently registered tool can answer <question>.
Show its required inputs and one minimal example. Do not execute it yet.
```

```text
Use dv-engineering to implement <scenario> in <testbench>.
Do not simulate. Show applicable validation choices, accept my selected subset,
and report each selected result separately without adding unselected checks.
```

Jira 截图上传必须确认实际注册的 **Jira attachment** 能力；Confluence 附件针对另一个
资源，不能作为替代。缺少 Jira 上传工具时明确告知，由工程师在 Jira 界面上传。
profile 查询通过不代表获得创建或修改工单的授权。
