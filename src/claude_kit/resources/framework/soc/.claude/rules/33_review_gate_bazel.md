---
paths:
  - ".claude/evidence/**"
  - "docs/reviews/**"
---

# 审查门控

审查不是 pipeline 阶段，永远不写源代码/状态/waiver/EDA artifact。

## 审查模式

| 模式 | 触发 | 范围 |
|---|---|---|
| quick | 只读审计 | 基本一致性检查 |
| normal | merge | 完整证据审计 |
| strict | signoff | 高风险交付审计 |

## 审查结果

- `pass` — 证据充分，无 blocker
- `needs-fix` — 有可操作的修复项
- `needs-validation` — 需要额外验证证据
- `blocked` — 缺少必需的角色或能力

## 审查员约束

审查员 (`soc-reviewer`):
- **可以**: 读取 diff、运行只读 loop checker、比较 state/artifact digest/fingerprint/run ID 与真实证据
- **不可以**: 写源代码/状态/waiver、运行 EDA、批准 waiver、声明 signoff

## 问题报告格式

每个问题包括:
- 严重性: `Blocker | Critical | Major | Minor | Info`
- 置信度: 0-100
- 权威性: `Project Rule | Reference Evidence | Local Evidence`
- 所有者
- 证据 (文件/行)
- 风险
- 修复建议
- 影响范围
- 状态

发现必须指向证据并命名最小的必要修复。
