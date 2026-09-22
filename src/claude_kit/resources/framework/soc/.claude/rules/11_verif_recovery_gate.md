---
paths:
  - "hw/dv/**"
  - "hw/rtl/**/unit_test*"
---

# Verification recovery

Compile, simulation, regression, and coverage use registered `soc-build-bazel`
tools. Follow the **DV check menu** in `.claude/CLAUDE.md`; recovery does not
authorize unselected checks. A successful `soc_sim` already includes compilation.

On failure, inspect the real log first. Before reconstructing known debug context
from raw sources, query the persistent xwiki through `XWIKI_DIR`, following its
index/log/concept hierarchy. Never guess the wiki path, and treat wiki content as
compiled context that must be reconciled with current stable sources and run
evidence. Classify the failure as environment/tool, filelist or elaboration, RTL
behavior, testbench expectation, timeout, or license/resource. Record the failed
check and remediation when pipeline state is in scope, then return to the earliest
affected stage. Do not dispatch downstream work from failed or stale evidence.

When recovery produces a durable conclusion, classify the xwiki candidate as
`env_bug`, `rtl_bug`, or `spec_bug` and return stable conclusions, durable source
citations, transient observations, confidence, contradictions, unknowns, and
next evidence to the parent session. The parent must verify explicit user,
project-rule, or task-scope write authorization before invoking the xwiki skill.
Recovery, dispatch, and check selection do not authorize a wiki write, and a
child agent must not write the external wiki directly.

Verification passes only when the registered run completes, its immutable log
contains the project pass condition, and error/fatal counters are clean. A
timeout, partial/stale log, or appended PASS marker is not evidence.

If verification needs RTL repair, route it to the RTL owner and invalidate stale
evidence. Closure needs a selected simulation on the final source; if simulation
is not selected, report missing validation rather than running automatically.
Invalidate synthesis once after final evidence. Follow the RTL-epoch rule if
synthesis already owns repair.
