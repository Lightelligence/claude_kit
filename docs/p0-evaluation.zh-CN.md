# P0：评估技能效果、验证修复、搜索同类 bug

本轮保持 `dv-test`、`sim-debug`、`dv-review`、`project-context` 四个入口，
不增加默认 MCP、原生 skills 或模型 API 依赖。共享运行环境仍仅需 Python >=3.11。
新命令读取项目 profile、显式输入和结果；既有 runner/原生客户端负责实际执行。

## 合并条件：收益尚未证明

这批改动先以 Draft PR 评审。代码测试只能验证实现合同，不能证明模型更会做 DV。
仓库随附的四个样例都是 synthetic fixtures；它们不是 VCS 实测，也不是实际模型 A/B。
在以下证据形成前，不把 PR 标记为可合并，不开启自动合并：

| 待验证能力 | 需要的证据 | 本轮状态 |
| --- | --- | --- |
| Skill 效果 | 同一模型、相同工具/预算/原始输入，独立会话成对比较旧/新技能或无/有技能；保留完整轨迹和独立评分 | 已做下述小型对照及 OpenTitan 历史 DV 案例；有单例成本信号，质量／人工收益未证明 |
| 修复验证 | 在实际项目的历史 bug 上，对照人工结论，确认原错误失败签名、修复后通过及正常场景保持；错误证据被拒绝 | 已评审真实 OTBN 源码／补丁及上游 VCS/Xcelium 报告；无独立 EDA 或专家计时，helpers 项目效果仍待验证 |
| 同类 bug 搜索 | 已知实例和人工确认的其它实例、相似但正确的反例；记录找到/漏掉的实例、误报及审查成本 | OTBN 局部源码审查能找已有 coverage 遗漏；不代表完整搜索，候选 helper 的项目效果仍待验证 |

建议至少覆盖 DV-only 路由、外部阻塞的正确交接、checker 无效、formal 限制、真实根因定位、
修复后的相邻场景六类任务，每个 case 做三次独立重复。事先固定质量和成本指标，
逐 case 展示结果及方差，不只给总均分。必须没有新增的误报“已验证”或越权 EDA 执行；
若质量没有改善，需用质量保持且成本稳定降低的实测结果说明价值。
差异不清楚时保留“收益未证明”，不把上游宣传或模型自评分当验收。

## Skill 效果评估

以下是维护者/试点工具，普通 DV 修改无需运行。先在项目中保存模板和原始输入：

```bash
python <kit>/bin/claude-kit skill-eval template suite > eval-suite.json
python <kit>/bin/claude-kit skill-eval template run > eval-run.example.json
```

将 kit 的 `src/claude_kit/resources/evals/fixtures/` 复制到项目 `eval-fixtures/`。
模板的 `project` 改为 profile `project.id`；调整 `inputs` 和两个 arm 的 `skill_inputs`。
无技能 baseline 可为空列表；旧/新版本比较时，两边分别填写固定资源树。
只有启用的具体技能及其 references 应进入 skill 输入，避免把无关目录算进基线。
依赖的工具配置/版本锁、原始 fixtures 放入共同 `inputs`。
提示、断言和重复次数均纳入 suite digest；原始文件与技能资源分别计算摘要。

```bash
python <kit>/bin/claude-kit skill-eval snapshot --project-root . --suite eval-suite.json
```

在执行前保存此结果；不能为旧输出补一个新 snapshot。使用你选定的现有客户端/runner
分别执行每个 case、arm、repetition：

- 同一 case 的两边使用相同模型版本、推理设置、工具权限、环境和任务预算。
  `settings_digest` 是这些非技能设置的规范 JSON 摘要；不要保存明文凭证。
- 每次用独立会话、隔离工作目录。baseline 不得自动发现 candidate 的 skills，
  candidate 不能读到上一轮输出、评分、断言答案。只向被测模型提供 prompt 和原始输入，
  不提供带期望答案的完整 suite。随机/交替两边执行顺序，保留超时和失败。
- Collector 从客户端真实轨迹填实际模型、环境 ID、三个 snapshot 摘要、唯一 run ID、
  arm 和重复编号。token、耗时、工具调用数取实际统计；未知写 `null`，不估算成零。
- 保存完整 transcript 和任务输出，记录项目相对路径和持久化文件字节的 SHA-256。
  外部/独立评分者检查轨迹后生成 `observations.json`；不能让被测模型自行填一个
  `eda_executed=false` 或“根因正确”就认为证明成立。需人工判断的根因/语义题应保留
  评分者、依据和原始轨迹，评分可用机器读取，但其真实性仍由评分流程负责。

Run 记录模板定义所有字段。`outputs` 是名称到 `{path, sha256}` 的映射，必须包含
`transcript`。示例断言从 `observations` 的 JSON pointer 读值：
`recommended_checks`、`eda_executed`、`classification`、`blocker_owner`、
`attempted_environment_repair`、`dut_modified`、
`ready_for_review`、`claimed_unbounded`、`claimed_signoff`。
这些是评分输出合同，不要求被测模型按此格式作答。

支持 `json_equals`（空 pointer 指根值，支持 `~0/~1` 转义）、`text_contains` 和
`text_not_contains`。文本检查适合机械输出合同，不能证明根因正确或未执行某个工具。
所有断言资源必须完整可读且摘要一致。文档上限 1 MB，超限明确报错，绝不在截断文本上
判断“没有”。输出引用限项目内且遵守 profile 的 forbidden 路径。

```bash
python <kit>/bin/claude-kit skill-eval report --project-root . --suite eval-suite.json \
  --run out/base-1.json --run out/candidate-1.json --format markdown
```

重复 `--run` 提供完整集合。重复编号、case/arm、run ID 不得冲突。模型/设置/环境不同、
缺失 run、失败执行、摘要过期或输出损坏会产生 gap；通过/失败断言均保留在可比较样本中。
汇总报告明确给出 expected/comparable/gap pairs、两边通过率及差值，成本给配对差值的
样本数、均值和样本标准差。一个样本的标准差为 `null`；缺失指标不参与成本均值。
未产生要求的输出、输出不是合法 JSON 或缺少指定字段，计为质量失败，不从分母删除；
只有声明产物损坏/遗失、缺完整 transcript 等证据问题才成为不可比较的 gap。
报告 `complete` 仅表示对照集合完整，可包含技能退化，不是收益认证或统计显著性结论。

退出码：0 对照完整；1 对照有缺口；2 输入错误。仅收到部分结果时，完整子集的均值可能
有选择偏差，不能据此宣称总体改善。工具不启动模型、不采集客户端秘密，也不伪造行为轨迹。

## 修复验证

```bash
python <kit>/bin/claude-kit dv template fix-plan > fix-plan.json
python <kit>/bin/claude-kit dv template fix-run > fix-run.example.json
python <kit>/bin/claude-kit dv fix-snapshot --project-root . --input rtl --input tb --input spec
```

在 base checkout 和 patched checkout 分别捕获同一声明范围，填入计划的 `base/patched`。
摘要覆盖新增、删除和未提交输入；两个输入摘要必须不同。Git checkout 同时绑定 HEAD，
非 Git 输入可记录 null revision。计划和生成结果留在输入树外。与已有 `dv snapshot`
不同，这里不使用需求计划摘要，**不要互换两个命令生成的 digest**。

计划至少包含三类 checks，每个都要提供两边的实际结果：

| kind | base | patched |
| --- | --- | --- |
| reproducer | 原 bug 的指定 failure_signature | passed |
| control | passed | passed |
| regression | passed | passed |
| variant（发现真实同类问题时添加） | 同类 bug 的指定 failure_signature | passed |

每个 check 固定 test、configuration 和 seed（不适用时为 null）。Run 绑定 fix/check ID、
side、唯一 run ID、实际 argv、工具版本、输入基线、终态、complete 和至少一个产物。
每对使用相同工具版本。`compile_error/infra_error/timeout/inconclusive/skipped` 不能冒充
目标 bug 的失败。License 不足记为 engineer/user 所有的外部阻塞，等待工程师处理，
不修复 license，也不重复重跑；它不是 DUT/TB bug。Collector 应确认指定 assertion/checker 实际执行，并保存其完整结果；
报告只校验声明和文件，不解析所有 EDA 输出，也无法发现被 collector 隐藏的运行。

搜索候选后，在 `variant_review` 保存 `status: reviewed`、reviewer、rationale 和
带摘要的处置记录。没有真实 variant 时可不加 variant check，但需要说明审查范围、
反例和剩余盲点；不是把 `variant_review` 删除或凭零命中直接完成。

```bash
python <kit>/bin/claude-kit dv fix-report --project-root . --plan fix-plan.json \
  --run out/repro-base.json --run out/repro-patched.json \
  --run out/control-base.json --run out/control-patched.json \
  --run out/regression-base.json --run out/regression-patched.json --format markdown
```

当前声明输入和 Git HEAD 必须仍匹配 patched。base 产物按声明的 pinned baseline 校验，
不会重建历史 checkout。重复 check/side 被拒绝；明确选择并保留完整 review set，不能用
换 seed 隐藏失败。退出码 0 `ready_for_review`、1 有 gaps、2 输入错误，signoff 恒为 false。

## 同类 bug 搜索

```bash
python <kit>/bin/claude-kit dv template variant-plan > variants.json
python <kit>/bin/claude-kit dv variant-search --project-root . --plan variants.json \
  --max-files 200 --max-scan-bytes 8000000 --max-matches 100
```

先确认 root cause。首个 literal 必须在已知 path/line 命中，且已知实例位于声明 scope；
随后每个 pattern 扩大一个元素，填写 rationale。最多八个 literal，不执行正则、
CodeQL、Semgrep 或项目代码；HDL 结构/语义分析仍用项目既有 LSP/EDA 工具。

预算覆盖 anchor 和范围扫描的累计扫描字节，anchor 最多扫描 1 MB；全局文件数和命中数
也有上限。输出只保留文件、行、pattern ID、文件完整摘要或扫描缺口。所有命中都是
`unreviewed`；`confirmed_bugs` 为 null。同一个正常 guard 也可能命中，不能批量修改。
符号链接不跟随；forbidden 文件跳过并标出缺口。预算用尽、扫描不完整均返回 exit 1。
目录遍历另限 `max_files × 10` 个目录，防止空目录树绕过文件预算。
exit 0 仅表示声明的 literal 搜索完整，未证明设计中不存在其它 bug。

## 历史重放与测试精简

PR 初稿曾重放本仓库 PR #14 的 `fdd1c770` → `59a766bd` 哈希修复：显式持久化
CRLF 后，八次小型 Python 检查验证了修复前后的差异和部分错误证据拒绝逻辑。
它只证明窄范围机械检查，不能替代真实模型或 DV 项目收益。
一次性重放脚本和摘要保留在 [PR 初始提交](https://github.com/Lightelligence/claude_kit/tree/aa3015aa8a094efbb1ac3fffa7eb42bfe2b48348)，
不再作为长期维护的测试代码随本轮新增。后续以实际模型对照记录评估收益。

新增自动测试由 32 项精简为 24 项，保留证据新鲜度、配对一致性、质量退化/失败分母、
错误复现、正常行为保持、未审查候选和读取范围/预算。模板存在性及固定数量断言、
重复 CLI 格式检查由现有分发与 CLI 测试覆盖。
CI 只在 PR、main push 或手动触发运行；同一 PR 的新提交取消过时任务，保留原平台/Python矩阵。

## 实际模型 A/B：2026-10-25

使用本机已登录的 Codex CLI `0.164.0-alpha.11.1`，请求模型 `gpt-6.1-sol`、medium
推理强度、只读沙箱。关闭插件、外部连接器、网络搜索和自动技能发现；两边显式读取
同名指导，使用相同通用读取工具、原始输入和输出格式。未修改本机全局配置或安装新依赖。
baseline 为 `4f897552` 的 debug/review 指导，candidate 为 `aa3015aa` 的相应指导及
按需参考文件。新确定性 CLI helpers 在两边都不可用，本轮单独测指导效果。

预先固定六类任务、交替先后顺序，每类一对、最多十二个正式会话：正常修复证据、
seed 不一致、输入过期、同类 bug 候选、失败签名不一致、license 外部阻塞。
输入来自本仓库历史 Python 修复与受控元数据变体、少量 RTL/log fixtures；
这是实际模型会话，不是实时 DV 项目、VCS 或 Claude Code 原生发现/兼容性试验。
评分规则在运行前保存，模型看不到评分文件；保存 JSONL 轨迹和实际答案后，由固定规则
评分，并由主会话核对所有答案和尝试执行的命令。没有独立人工领域专家盲评。

| 完整的五对 | baseline | candidate | 差异 |
| --- | --- | --- | --- |
| 任务判断正确 | 5/5 | 5/5 | 没有质量提升 |
| 客户端报告 token 总量 | 332,395 | 343,678 | +3.4% |
| 本机计时总耗时 | 97.79 s | 93.52 s | -4.4% |
| 工具调用 | 18 | 16 | -2 |

第六对的 candidate 会话在读取文件后连接中断，达到 120 秒预算仍无最终答案。
该次轨迹保留为 timeout/gap，未用重跑替换；不把缺失 token 当零，也不将外部连接故障
归因于技能。五对成本均值只反映完整子集，不能代表全部六对。
token 指 native CLI 报告的 input + output，包含缓存输入，不是费用；模型后端构建号
没有独立核实。每类只有一次重复，无法证明统计显著性或稳定耗时改善。
所有已观察命令均为读取/哈希，没有运行 EDA、修复环境或修改文件；两边都把 license
问题交给工程师处理。

最初一批输入意外混入历史汇总报告，存在答案泄漏风险，已整批作废并保留原始记录。
该批启动五次、完成四次；另有两次模型连通预检。正式结果只统计修正输入后启动的
十二次会话，失败和额外成本没有隐去。没有根据本轮答案改指导或只重跑落后的一边。

结论：**目前未证明新增指导有稳定收益，PR 保持 Draft，不合并。**
确定性 helpers 的边界测试通过，也不能填补真实 DV 项目的收益证据。
[机器可读结果](p0-ab-results.json)与[原始证据压缩包](p0-ab-evidence.tar.gz)包含 protocol、
rubric、输入、两边指导、命令/prompt、回答、原始轨迹、用量、评分及作废批次；压缩包
另有逐文件 SHA-256 manifest。解压后，用本 PR 的 Python 包执行其中 `recompute.py`
可重算报告，不调用模型。归档只存实验数据，不作为新的测试框架或 CI 模型任务维护。

## OpenTitan 真实 DV 历史案例

追加的 [OpenTitan 历史 DV 案例](p0-opentitan-ab.zh-CN.md)使用封存协议、两轮共 8 个
native 会话，全部完成；旧／新都能定位故障路径，但未在盲测完整还原 STATUS 延迟机制。
新版总 token 少 31.4%，主要来自根因阶段更少的读取；修复评审 token 增 1.2%。
人工工时未实测，两边都需要运行记录、时序及 coverage 证据。
因此仍保持 Draft，不把单例模型成本信号当成新增修复流程或 helpers 的收益证明。
本次只保留报告和可重算原始证据，没有增加测试、CI 或框架。

## 来源与维护边界

评估方法参考 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)，
修复和同类搜索方法参考 Trail of Bits 的
[post-patch-validation](https://github.com/trailofbits/skills/tree/main/plugins/post-patch-validation) 与
[variant-analysis](https://github.com/trailofbits/skills/tree/main/plugins/variant-analysis)。
本轮独立实现窄范围的标准库 CLI 和合同，不复制上游 prompts、脚本或 runner，不整体安装
其插件。上游原资源继续受其对应许可约束；本 kit 的许可不改变它们的许可。
