# 可复用的 AI assistant DV flow

本轮基于 `claude_kit` 的 `b5f0105`，延续「评估AI提升设计验证效率」的讨论。
目标是让 AI 能完成有边界、有工具反馈、有证据的小任务，成果能够累计到需求评审。
claude_kit 作为所有 DV 项目的固定版本 submodule；项目数据和运行状态留在消费项目。

## 评估结论（2026-09-27）

| 来源 | 本次确认 | 借鉴与落点 | 暂不引入 |
| --- | --- | --- | --- |
| [OpenTitan 方法论](https://opentitan.org/book/doc/contributing/dv/methodology/index.html) | 机器可读 testplan、验证阶段、UVM 与结果关联 | 需求 ID、场景、配置、checker、覆盖目标及阶段评审 | 整套 DVSim、其 SoC/IP 依赖 |
| [OpenTitan testplanner](https://opentitan.org/book/util/dvsim/doc/testplanner.html) | testpoint 可关联多个实际测试；coverage plan 单独表达 | 每个需求可有多个必验 case；逐配置查缺口，不能一个 test pass 关闭整条需求 | 将 test pass 或 coverage 百分比当成正确性证明 |
| [HAVEN](https://github.com/mcc311/haven) | 结构模板、场景 DSL、VCS/URG 反馈；公开 README 的 coverage 是 best-of-3 | 场景卡先表达意图，再复用既有 sequence API 和稳定结构，设修复预算 | 新的 LangGraph runner、OpenAI API 依赖、整套环境生成器 |
| [HAVEN schema](https://github.com/mcc311/haven/blob/main/src/haven/dsl/schema.py) / [codegen](https://github.com/mcc311/haven/blob/main/src/haven/dsl/codegen.py) | 结构化操作与确定性生成分离，代码含约束过滤和映射回退 | 采用结构/意图分离；项目不支持的 API 或约束明确报缺口 | 静默删约束、猜 mapping；模板生成不等于协议语义已证明 |
| [vibe_soc](https://github.com/siliconpeasant/vibe_soc) | kit 已有固定快照 `0b0ae36846cd3a5e7be39ea90eb57bf5dbb3b026` 及适配补丁 | 保留执行入口、工具资源和审查边界 | 第二套调度、运行状态和全量 vendoring |
| [xverif](https://github.com/BLANK2077/xverif) | kit provider 固定到 `214e9cc81ba5ffe0010f5f4f2e0d6e4cfae40de6`，只集成 skills/契约，运行时由项目提供 | 继续用于源码/波形/coverage/SVA 取证；先读实际 action schema | 假定本机已装 runtime，或猜测新版本 API |

当前 main 中没有找到 HAVEN 直接集成，也没有 OpenTitan testplan 的可执行集成。
vendored vibe_soc 中出现的 OpenTitan 路径是仓库卫生检查规则，不能据此认为方法论已经接通。
已有 `evidence check` 只检查任务记录格式、身份、命令与路径，不做需求级完整性判定。

本轮是独立实现方法，不复制 OpenTitan/HAVEN 源码，也不新增它们的运行依赖。
上游公开结果不是本项目的复现结果；尚未在真实 VCS/Verdi/VC Formal 项目测量收益。

## 从需求到 signoff 的完整工作链

```text
项目工具能力验收 + spec/配置/版本
  -> 原子需求、歧义与决策记录
  -> 需求 × 配置 × 场景：checker / stimulus / coverage / formal 分工
  -> AI 复用项目模板做最小实现
  -> 既有 runner 编译和目标运行，xverif 查询实际结果
  -> 失败调查或 coverage hole 闭环
  -> dv report 聚合当前证据与缺口
  -> 人工语义评审、项目 regression 和阶段 signoff
```

1. **能力验收**：源码查询、已知波形时间点、已知 coverage hole、smoke 提交和结束状态各验证一次。
   标注“已实测／已配置未验证／缺失”。license、队列、编译错误与 DUT failure 分开记录。
2. **需求澄清**：附 spec 章节、适用配置、reset/clock/周期语义、未决问题。AI 可提出候选解释，
   有歧义就保留；不默默决定 reset/completion 优先级。先选一个 block 的 5–10 条需求。
3. **策略与实现**：局部不变量可用 formal，长事务/系统交互用仿真；两者必要时建成两个必验 case。
   预期结果来自规范。复用 driver/monitor/base sequence；关键 checker 用受控错误或已知 bug 验证。
4. **执行**：使用项目已选入口与预算。建议起点是两次编译修复、三次目标仿真、并发一项，
   不是全局强制值。保存真实命令、test、seed、工具版本、输入快照、终态和产物引用。
5. **Debug**：事实 → 至多三个候选原因 → 支持/反对证据 → 最小区分实验 → 已确认或未确认。
   首轮可设十次查询预算，避免不停重查整块波形。修复后重现原失败并检查相关场景。
6. **Coverage**：先区分刺激缺失、约束错误、采样错误、DUT 异常、配置不适用、疑似不可达。
   目标 hit 与 checker 有效分别证明。不可达证明、exclusion 和 waiver 仍由项目流程评审。
7. **阶段评审**：可以采用 OpenTitan 风格的 bring-up、功能完成、coverage/压力场景、最终评审阶段，
   但不自动宣称满足其 V1/V2/V2S/V3。各项目保留自己的 checklist、bug/waiver 审查和签核责任。

## 本轮交付与边界

- `dv template plan/run`：项目自有的需求映射和运行记录模板。
- `dv snapshot`：对计划及其声明的文件/目录生成 SHA-256 输入快照，包含未提交和新增输入文件。
- `dv report`：只读关联需求、配置、case 和显式提供的 run；输出 JSON/Markdown，适合 review/CI。
- 现有 DV、debug、evidence skills 加入场景卡、查询/运行预算、formal 和证据闭环指导。
- 运行时仍仅需 Python >=3.11 标准库。无新服务、数据库、模型 API 或 EDA 调度。

第一版保守处理：声明范围中的任何源码、规范、TB、配置或计划变化，会使整个计划的旧证据过期。
Git HEAD 变化也会使旧证据过期；这会多跑一些测试，但不会猜测哪些变更“无关”。
未来只有试点证明需要时，再加精确依赖分析、runner 专用自动导出和 regression 优化。

证据检查只能验证**声明的范围、提供的 run、文件完整性与字段一致性**。
它不能判断 adapter 提取的 checker/coverage 事实是否真实，不能发现被省略的需求或失败 run，
也不能证明 checker 实现与 spec 一致。因此状态最高为 `ready_for_review`，`signoff` 始终为 `false`。

## 作为 submodule 接入

使用项目固定版本的 kit 和已批准 Python，下面的 `<kit>` 指实际 submodule 路径。
已有项目沿用其 `.claude/project.toml` 或 `.ai/project.toml`，无需重新 init。

```bash
python <kit>/bin/claude-kit doctor --project-root . --strict
python <kit>/bin/claude-kit dv template plan > dv-plan.json
python <kit>/bin/claude-kit dv template run > dv-run.example.json
```

填写真实 `project`、输入目录和需求。输入只包含 spec/RTL/TB/约束/配置/项目 adapter 等源文件；
输出目录、运行记录和 snapshot 必须放在输入树之外。受影响的 VIP、生成源或 kit 版本也应
纳入项目基线：例如把描述它们版本的锁定文件列入 `inputs`。远程/不可读依赖由 adapter
生成实际版本和内容摘要的锁定文件；不能只写未经核实的版本字符串。

有既有 Hjson/CSV testplan 时，通过项目 adapter **导出**本格式，继续以原计划为唯一权威来源。
新增原生 JSON plan 可直接维护；工具不会解析 Hjson，也不会生成第二套手工状态表。

```bash
# 在最终编辑完成后、既有 runner 提交之前捕获；输出位置应在 inputs 外。
python <kit>/bin/claude-kit dv snapshot --project-root . \
  --plan dv-plan.json > out/baseline.json

# 由既有 runner 执行；其 collector 读取真实报告并导出 run JSON。
# 对明确的完整 review set 逐个传 --run，不扫描“最新”目录。
python <kit>/bin/claude-kit dv report --project-root . --plan dv-plan.json \
  --run out/run-001.json --run out/run-002.json
python <kit>/bin/claude-kit dv report --project-root . --plan dv-plan.json \
  --run out/run-001.json --format markdown > out/readiness.md
```

命令本身不写文件；示例重定向由调用方控制。退出码：`0` 证据可评审，`1` 有缺口，`2` 输入错误。
无 run 时输出缺口报告。`evidence check` 继续用于任务级移交，`dv report` 补充需求级检查。

更新 submodule 后，按现有 `sync` 流程同步 skills 和引用文件；有本地修改时保留并合并，
不要为了更新本轮指导而盲目 `--force`。当前实现不改项目 profile，不引入新的 MCP server。

## 最小 adapter 数据契约

模板位于 `src/claude_kit/resources/templates/dv-{plan,run}.json`，
字段结构见同级 `schemas/dv-{plan,run}.schema.json`；CLI 还做跨记录与文件完整性检查。

Plan 每条需求包含 `id/statement/spec_ref/configurations/open_questions/open_bugs/cases`。
每个 case 固定 `id/method/test/checkers/coverage_targets/require_negative_control`。
每个 case 都适用于该需求的全部配置；若适用范围不同，拆分需求。
`checkers` 与 `coverage_targets` 是真实工具报告中的稳定 ID；不解析 SV 源码去猜它们。
空映射合法但会产生缺口。`spec_ref` 是评审引用，工具不联网验证语义。

Run 包含身份、`baseline`、实际 argv、工具版本、simulation seed、结果终态和产物。
同一物理 run 可关联多个 case；其 `(run_id, requirement_id, case_id, configuration)` 不可重复。
同一 case 的完整 checker 与 target 证据须在一个 run 内成立，不能拼接几个不完整 run 宣称完成。

```json
{
  "checkers": [{
    "id": "sb_reset_cancel", "active": true, "status": "passed",
    "artifacts": [{"path": "out/checker-summary.json", "sha256": "<actual 64-char sha256>"}],
    "negative_control": {
      "detected": true,
      "artifacts": [{"path": "out/injection-result.json", "sha256": "<actual sha256>"}]
    }
  }],
  "coverage": [{
    "id": "reset_x_outstanding.nonzero", "hit": true, "complete": true,
    "artifacts": [{"path": "regression:run-001/coverage-query.json", "sha256": "<actual sha256>"}]
  }]
}
```

`regression:` 限定在 profile 的 `artifacts.regression.root`；本地引用限项目根目录。
artifact 必须是文件，不能只指向 FSDB/VDB 目录。大日志可引用持久化的查询/summary 文件，
其中应保留原始日志位置、run ID、query ID、工具版本和截断状态；不要每次哈希数 GB 波形。
摘要是项目 collector 的信任边界，不能由 AI 把猜测写成已验证事实。

Simulation 成功为 `status=passed`、`complete=true`；checker 同为 `passed` 且 `active=true`。
Formal 成功为 `proven`，checker 同为 `proven`，并补充：

```json
{
  "formal": {
    "scope": "module/parameters/clocks/reset/property set",
    "assumptions_reviewed": true,
    "nonvacuous": true,
    "unbounded": true,
    "artifacts": [{"path": "out/proof-and-assumption-review.json", "sha256": "<actual sha256>"}]
  }
}
```

覆盖查询必须完整且目标 hit。`failed/counterexample/inconclusive/compile_error/timeout/infra_error/
running/skipped/unknown` 都不成为成功证据。当前基线任一不成功 run、缺失或损坏证据都会
阻止该 case ready，不能用另一颗通过的 seed 覆盖。旧基线 run 保留在 `stale_runs`。
同基线历史失败解决后，由工程师明确选择和记录新的完整 review set；工具不会自动删除失败。

Collector 在执行前捕获快照，执行后确认实际输入未变，并绑定到 runner 的 build/run ID。
远程 source staging 必须核对相同摘要；运行时还在修改源文件的结果不能标为 complete。
不能对旧 run 执行一次新的 snapshot 后套入新摘要“刷新”证据。

## 一周试点与后续顺序

| 时间/范围 | 交付 | 验收 |
| --- | --- | --- |
| 第一天，一个现有 block | 五项工具验收、5–10 条需求、一个 run collector 导出 | 与人工检查的命令、日志、波形和 coverage 一致 |
| 第二天，三个已知历史失败 | RTL/TB/环境问题的盲测调查 | 根因正确率、错误归因、人工纠正时间 |
| 第三天，一个真实 coverage hole | 场景卡、最小 sequence、目标与 checker 证据 | 目标到达，关键 checker 抓住受控错误 |
| 第四天，一个变更和 formal 小例 | 旧证据失效；已有 harness 才做 formal | bounded/vacuous 不误判 proven，所有配置有结论 |
| 第五天，项目回顾 | 需求缺口报告与成本对比 | 人工总工时、返工、仿真/license 时间、模型成本 |

时间是建议工程安排，不含长回归等待。没有现成 formal harness 时先完成 simulation 试点。
优先级：先实际接通 collector，再扩大需求范围；有收益后再做自动 nightly 汇总、失败聚类、
coverage grading 和更细的失效范围。暂不引入 OpenSpec/Spec Kit、全量 RAG 或多 agent 调度。

下一次真实项目接入只需要：现有 profile、一个 smoke/regression 的提交与查询接口、一个完整
run 的脱敏结果样例，以及试点 block 的 testplan/sequence/checker 引用。本轮本地 fixture
验证的是工具契约与失效逻辑，不是硅片正确性或真实 EDA 能力验收。
