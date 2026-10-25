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
| Skill 效果 | 同一模型、相同工具/预算/原始输入，独立会话成对比较旧/新技能或无/有技能；保留完整轨迹和独立评分 | 未测 |
| 修复验证 | 在实际项目的历史 bug 上，对照人工结论，确认原错误失败签名、修复后通过及正常场景保持；错误证据被拒绝 | 项目试点待做；本地合同测试不替代 |
| 同类 bug 搜索 | 已知实例和人工确认的其它实例、相似但正确的反例；记录找到/漏掉的实例、误报及审查成本 | 项目试点待做；候选搜索不等于语义识别 |

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

## 已做的窄范围历史重放

`tests/pilot_p0_history.py` 从本仓库真实历史提交提取 artifact helper，重放
PR #14 中 `fdd1c770` → `59a766bd` 的持久化字节哈希修复。
在所有平台显式将换行持久化为 CRLF；这是受控重放，不宣称在 Windows/VCS 中运行。

```bash
python tests/pilot_p0_history.py --output /tmp/kit-p0-history-new
```

输出目录必须不存在，Git 中须已有上述历史对象。脚本不修改 Git，实际执行八次
小型 Python 检查，保留命令、结果、输入摘要和完整产物：base 的换行复现与多行变体失败，
patched 两者通过；无换行 control 和空输入 regression 两边通过。
`fix-report` 接受这个显式记录集，并拒绝把无关失败签名、不同 seed 或缺失 regression
冒充完整证据。候选搜索同时找到已知文本哈希位置和正确的字节哈希反例，两者仍为待审查。
这证明了部分机械检查能力，不证明真实模型效果或实际 DV 项目的收益。
`summary.json` 显式保留 `skill_effectiveness: not_measured`、
`dv_project_usefulness: not_measured`、`merge_criteria_met: false`。
本轮实际重放的[摘要记录](p0-history-replay.json)随 PR 保存；完整运行记录可通过上述命令重新生成。

## 来源与维护边界

评估方法参考 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)，
修复和同类搜索方法参考 Trail of Bits 的
[post-patch-validation](https://github.com/trailofbits/skills/tree/main/plugins/post-patch-validation) 与
[variant-analysis](https://github.com/trailofbits/skills/tree/main/plugins/variant-analysis)。
本轮独立实现窄范围的标准库 CLI 和合同，不复制上游 prompts、脚本或 runner，不整体安装
其插件。上游原资源继续受其对应许可约束；本 kit 的许可不改变它们的许可。
