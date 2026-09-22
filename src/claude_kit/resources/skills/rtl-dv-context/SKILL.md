---
name: rtl-dv-context
description: Compatibility entrypoint for rtl-dv-kit; use the canonical skill for project context and workflow selection.
---

# RTL/DV Context (compatibility)

Follow [rtl-dv-kit](../rtl-dv-kit/SKILL.md) for missing project facts and
workflow selection. Do not load both skills. New installations expose only
`rtl-dv-kit`; old CLI/MCP requests for `rtl-dv-context` resolve to that skill.
If this is a standalone old project copy without the sibling skill, request
`resolve_context` with `skills=["rtl-dv-kit"]`, `roles=[]`, `packs=[]` from
the updated kit, or reattach the reviewed installation.
