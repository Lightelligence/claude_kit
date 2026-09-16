---
name: rtl-dv-kit
description: Resolve missing or stale RTL/DV project context and select the relevant skill or registered tool. Use for onboarding, uncertain scope or routing, not mandatory preflight before every edit.
---

# RTL/DV Claude Kit

This is the single project-context and routing skill.

## Resolve only missing facts

Start with the task and facts already available. Use the configured project
profile (normally `.ai/project.toml`) and applicable project instructions.
Check checkout/root and source identity when ambiguity or stale evidence affects
the decision. A checkout name is not a stable project ID; another checkout's
cached target mapping is not current. Distinguish observed facts from assumptions,
with source/configuration references for consequential claims.

Respect writable, read_only and forbidden paths; permitted `hw/**` is normal
RTL/DV scope, not inherently protected. Identify conflicts with actual tool
availability or user intent; do not silently widen permissions, change backends,
rewrite configuration or install integrations. Continue unaffected analysis.

Prefer registered kit MCP in Claude Code: `get_project_profile` for unknown or
changed configuration; `plan_task` for unclear workflow/check selection. Resolve
relevant validation errors before relying on configuration. Inspect the schema
only when needed. Repo-local CLI is for maintenance, not required daily use.
Do not mandate a doctor/plan/inspect chain or re-read unchanged context.

## Select bounded context and route once

Inspect affected code, interfaces, tests and necessary dependencies, not the
whole repository. Load only guidance relevant to the actual protocol/version:

- DV implementation or test planning: dv-engineering.
- Existing failure diagnosis: rtl-dv-debugging.
- Check-set selection or regression result triage: rtl-dv-regression.
- Code correctness review: rtl-dv-review.
- Claim/artifact audit or requested evidence file: rtl-dv-evidence.

Role names do not imply installed Claude subagents; apply guidance in the current
session when appropriate. In a minimal installation, only this skill may exist.
If a capability is absent, report the limitation and use available instructions
for bounded work; do not pretend invocation succeeded or automatically install it.

Resolve target/test/simulator/seed and artifact mappings from authoritative facts
before the operation that needs them. Do not guess aliases or require a simulation
seed for source-only work. Plans and tool registration do not authorize checks.
Reuse engineer selections already made. In MCP-only projects use registered
project tools without a shell fallback; declared build.commands wrappers are usable
only where project policy permits. No automatic simulation, regression, coverage,
synthesis or CDC after an edit.

## Output and refresh

For context discovery return scope/root, relevant sources and mappings, selected
guidance, revision/dirty state when relevant, assumptions/conflicts and the missing
facts affecting the next action. Default discovery is read-only and runs no EDA.
Create a context file/manifest only for a requested deliverable at a writable
destination. For actual development, report changes and verification proportionally;
do not force formal evidence files for routine questions.

Refresh only facts affected by a changed checkout, profile, tool configuration,
source or requirement. A summary, plan or successful registration is not sign-off.
