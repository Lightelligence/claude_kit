---
paths:
  - "hw/**"
  - "docs/architecture*.md"
  - "docs/design/**"
---

# Design knowledge-base contract

Before material architecture, documentation, RTL/DV, integration, lint,
synthesis, CDC/RDC or physical-design decisions, query `soc-ai-kb` if registered.
Use the relevant domain, diagnostic or rule name. Reuse unchanged evidence;
record influential sources in the design/evidence. Missing capability or
insufficient evidence does not block a fresh clone: record the limitation,
local evidence and engineering assumptions rather than inventing guidance.

Implement approved documents and applicable coding/tool guidance. Verification
uses relevant scoreboard, coverage, assertion and error-injection methodology.
Domain-specific designs need evidence before scope, interface or architecture
decisions. Do not add protocols, autonomous DMA, cache hierarchy, generated
clocks/resets, safety mechanisms, DFT wrappers, SRAM macros or physical-design
assumptions without explicit architecture/doc approval and supporting evidence
or a documented evidence gap.

Split unwieldy RTL into focused modules with clear ownership. Update the owning
Bazel target sources/dependencies and regenerate filelists; never hand-maintain
`de/rtl/filelist.f`. Each module retains the `doc -> rtl -> {verif, syn}` pipeline
and engineer-selected registered checks.

For review, precedence is active project, IP/subsystem, company, then general
rules. Cite ID, source, version and scope. Only knowledge-base sources under
`soc/review/rule_library/` have project-rule authority. Other sources are
reference evidence: they cannot independently establish violations, Blocker or
Critical severity, or waivers. Missing rules and heading-only placeholders mean
`Need Human Confirmation`; never invent authoritative requirements.
