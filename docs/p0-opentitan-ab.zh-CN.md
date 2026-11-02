# OpenTitan 历史 DV bug：旧版／新版指导对照

此页记录未启用 helpers 的指导试验。最新的 [helpers 实际启用对照](p0-helper-ab.zh-CN.md)
已验证真实调用，但仍未观察到漏检或模拟介入减少。

**本案例观察到 token 和读取调用减少，但没有根因或修复判断的质量提升，也未测得人工节省。
PR #20 继续保持 Draft，不合并。** 本次只增加实验记录，没有扩展框架、入口、自动测试或 CI。

## 案例与证据边界

选择真实的 [OpenTitan OTBN WFI coverage 故障，PR #31507](https://github.com/lowRISC/opentitan/pull/31507)。
coverage 开启时，`otbn_wfi_smoke`／`otbn_wfi_back_to_back` 在第一次 RESUME 报：

```text
model_status == 1 (5 vs 1): Saw instruction when not in BUSY_EXECUTE operational state.
```

另一个 `otbn_wfi_sec_wipe` 会触发 `wfi` 的 pairwise illegal bin。
真实修复涉及 scoreboard 对 PAUSED 时退休指令的有界处理、WFI mnemonic／encoding coverage，
以及跨 pause/resume 的指令对跟踪。它修复 DV 检查／采样，不靠关闭 coverage 消除失败。

上游作者报告 VCS 原始 15 次运行仅 1 次通过，修复后 15 次及每个测试额外 20 seeds 通过；
正常 smoke／single／multi 同 seeds 的结果和 coverage 保持。
复核者的 [Xcelium 15/15 对照](https://github.com/lowRISC/opentitan/pull/31507#discussion_r4141290550)
针对初版修复上的 pair tracking 增量：两边都通过，命中的 WFI pairs 从 3 增至 6/132。
它不是原始坏版本／最终补丁的 Xcelium 对照。
[作者随后确认 VCS 的新增 pair 命中](https://github.com/lowRISC/opentitan/pull/31507#discussion_r4146957974)。

这些是公开作者／复核者报告；没有取得完整仿真日志、逐次 seeds、版本和 coverage 数据库。
**本机没有执行 VCS／Xcelium，也没有独立证明补丁通过仿真。**

## 预先固定的对照

- OpenTitan 修复前：`2c36b23a1e0204b20a1d41da7172a0756204b1c8`；修复后：`de113e396ac850d6a5a89841b118771d51ba95dd`。
  保存 17 份原始文件、3 份修复后文件及差异，原始 LICENSE 和 NOTICE 随证据保留。
- kit 旧版：`4f897552`；新版：`22b9442`。只显式激活 debug／review 指导和按需参考文件；
  两边均不提供新 CLI helpers，本次不能证明 helpers 的项目效果。
- 本机 Codex CLI `0.164.0-alpha.11.1`，请求同一 `gpt-6.1-sol`、medium、只读工具；
  关闭插件、外部连接器、检索、自动技能发现及多 agent。模型后端构建号没有独立核实。
- 一个 bug、两次独立重复；每边先盲根因分析，再评审实际补丁和上游测试报告，共 8 个会话。
  每阶段最多 12 次命令、240 秒；交替两边先后顺序，失败不替换重跑。
- 根因阶段仅提供旧源码和故障现象，工作目录无 PR 标识，隔离补丁、PR 叙述、评分和其他输出。
  评审阶段收到本边未经纠正的前次答案；这个下游上下文差异属于处理效果，不是完全相同的文本输入。

Protocol、rubric、输入／指导 manifest 和 dispatcher 哈希均在第一次模型执行前封存。
8 个会话全部完成，没有超时或额外模型预检／重跑；所有观察到的命令均在声明范围内读取，
工作目录前后摘要一致。每阶段实际使用 6–10 次命令。
这是显式指导试验，不是 Claude Code 原生发现／兼容性或全仓库语义搜索试验。

## 根因与修复判断

评分由主会话 AI 按封存 rubric 检查答案、源码依据和全部命令，不是独立领域专家盲评。

| 观察项（每边两次） | 旧版 | 新版 |
| --- | --- | --- |
| 定位 scoreboard 时序路径、提出待证假设 | 2/2 | 2/2 |
| 找到 WFI mnemonic／encoding 缺失 | 2/2 | 2/2 |
| 从旧源码独立还原完整 STATUS 延迟／WFI 退休机制 | 0/2 | 0/2 |
| 看补丁前明确指出 pair history 被状态变化清空 | 0/2 | 0/2 |
| 识别补丁的有界检查、正常控制和负向检查需求 | 2/2 | 2/2 |
| 区分上游报告、Xcelium 增量对照和独立执行证据 | 2/2 | 2/2 |

完整机制一行是审阅答案后补充的描述性观察，没有改动封存的最低门槛或据此重算总分。

两边最初均偏向 posedge／negedge 导致的缓存状态滞后，没有完整推导
“合法 WFI 退休时 live STATUS 本身仍可为 PAUSED”的流水延迟机制。
都明确保留了不确定性并要求时序证据。**最低 rubric 通过不表示根因已完整确认；
读到补丁后解释正确，也不回填成盲根因分析得分。**

两边都能审查 WFI-first、最多再允许一条指令、其他状态仍保留原检查，以及 pair tracking
跨暂停保留／结束时清空。两边均提出非 WFI 首条、第三条指令的负向检查及正常控制。
都把缺少 PAUSED operational-state 映射作为已有 coverage 问题；第二轮都发现已有 CmdResume
bin 缺失，没有误标为本补丁引入的回归。这不是独立重现的 DUT bug，也不是完整同类 bug 搜索。

## 模型成本

| 完整工作流 | 旧版 token | 新版 token | 旧／新耗时 | 旧／新调用 |
| --- | ---: | ---: | ---: | ---: |
| 第一轮 | 533,613 | 400,258（−25.0%） | 144.04／142.73 s | 17／14 |
| 第二轮 | 584,861 | 366,870（−37.3%） | 140.78／132.76 s | 16／13 |
| 合计 | 1,118,474 | 767,128（−31.4%） | 284.82／275.49 s（−3.3%） | 33／27 |

token 是 native CLI 的 input + output，包含缓存输入，不是费用。
调用数统计 native `command_execution`；一次调用可以包含多条读取命令。
两边缓存输入分别为 878,208／578,816；扣掉缓存后的 input + output 为
240,266／188,312（−21.6%），同样不等于计费金额。耗时是模型会话本机墙钟时间，不是工程师工时。

| 阶段合计 | 旧版 token | 新版 token | 耗时变化 | 调用变化 |
| --- | ---: | ---: | ---: | ---: |
| 盲根因分析 | 745,209 | 389,510（−47.7%） | +2.2% | 19 → 14 |
| 修复评审 | 373,265 | 377,618（+1.2%） | −9.6% | 14 → 13 |

成本下降主要来自根因阶段更少的读取调用和上下文重复输入。
该阶段没有读取新增 fix-validation 参考文件；修复评审阶段没有 token 收益。
因此不能将整体 −31.4% 直接归因于新增修复验证流程或 helpers。
两次重复属于同一个 bug，不能当作多个独立项目或稳定统计收益。
公开案例也不能排除模型既有知识的影响。

## 人工介入与结论

两边都仍需要工程师提供／审核三类证据：原始与最终版本的配对运行记录、RESUME 时序、
coverage 明细与剩余缺口。主会话未发现需要额外纠正的最终误报“已验证”结论；
这不代表无需工程师审阅。没有领域专家实际操作和计时，人工分钟数为 `null`。

不能用 JSON `additional_requests` 数组长度代替人工成本：新版第二轮把补证要求写在
`verification_plan`，数组为空，所需工作仍然存在。两边均无交互式纠正或等待用户的模型轮次，
也不能据此宣称节省了人工时间。

本案例支持“新版指导可能减少读取和上下文用量”的窄结论；未证明根因更准确、
修复验证更可靠、同类搜索更完整或人工工作减少。确定性 helpers 的真实项目执行效果仍未测。
**现有证据不足以解除 PR #20 的 Draft／不合并限制；本轮不继续扩展框架。**

## 重算与原始记录

[结果 JSON](p0-opentitan-ab-results.json)保留逐会话／逐轮成本及明确的判断局限。
[证据压缩包](p0-opentitan-ab-evidence.tar.gz)保留封存协议、输入、指导、实际命令／prompt、
答案、完整 native JSONL、stderr、用量、主会话评分及上游来源；共享源码与每阶段实际
workspace manifest 可重建输入范围，无需复制所有工作目录。

解压后执行包内 `recompute.py`，仅用 Python 标准库即可校验逐文件 SHA-256、封存摘要、
每阶段输入和 native 用量，重算并比较保存结果，不调用模型。
评分语义仍须读原答案／依据复核，脚本不能认证评分正确或人工收益。

压缩包 SHA-256：`252a421075145d4621b3b7e3e59899aff8bdc23c7a055d8ae38ab162bdd95bc3`。
