# Skill usage documentation checklist / Skill 使用文档更新清单

Use this structure when documenting another skill. This is a maintainer checklist,
not an instruction to load every guide during normal Claude Code work.
Keep the English guide canonical, provide a Chinese companion, and use English
copy-and-paste Claude prompts in both. Omit sections that genuinely do not apply.

后续相似 skills 按以下结构更新；这是维护者清单，不是模型每次执行时必读的文档。
英文为默认版本，中文紧邻，两个版本中的 Claude prompt 均使用英文。

1. **Purpose / 功能与边界:** What task it solves, when to use it, when not to.
2. **Prerequisites / 前置条件:** Deployment/discovery, required inputs and optional
   tools. Separate skill availability from MCP/tool/license availability.
3. **Execution / 执行方式:** Explicitly label Claude prompts versus shell maintenance
   commands. State defaults, reads/writes, EDA use and authorization boundaries.
4. **Examples / 示例:** Minimal request, scoped RTL/DV cases where applicable,
   existing-artifact use and an optional follow-up. Use placeholders, not fixed
   project names, tests, paths or assumed backend mappings.
5. **Output / 输出:** Expected result fields, evidence and failure/blocked statuses.
   Mark illustrative results as examples, not actual verification evidence.
6. **Alternatives / 相近工具区别:** Explain when to choose each; do not add duplicate
   skills or MCP servers merely to document a capability.
7. **Efficiency / 效率:** Narrow scope, reuse evidence and load conditional detail
   only as needed. Do not claim measured token/latency savings without measurement.
8. **Limitations / 限制:** Missing setup, unsupported inputs and actual verification
   level: static review, unit tests, real MCP execution or native Claude behavior.
9. **Navigation / 入口:** Link both languages from README/tool selection. Keep long
   engineer tutorials outside always-loaded instructions; links must resolve.

Before delivery, compare examples with the actual skill/tool contract and check
relative links, placeholders, language parity and side-effect boundaries. Test
behavior when instructions or execution change; documentation-only edits need
proportional checks, not an automatic EDA run. Record untested behavior honestly.

Start from [rtl-dv-review](rtl-dv-review.md) /
[中文示例](rtl-dv-review.zh-CN.md), adapting rather than copying its read-only policy
into a skill whose purpose is authorized implementation or generation.
