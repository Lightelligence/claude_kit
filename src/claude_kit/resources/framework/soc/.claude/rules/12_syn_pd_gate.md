---
paths:
  - "hw/pd/**"
---

# Synthesis and PD gate

Follow the **DV check menu** in `.claude/CLAUDE.md`: synthesis and PD execution
require explicit selection, not just a stale stage or delivery mode.
Synthesis prefers registered `soc-build-bazel.soc_syn_pr` for a validated
`hw/pd/syn_pr/<block>` Flowkit block. The existing `soc-build-bazel.soc_syn`
remains the Bazel/DC compatibility route. An explicit synthesis selection must
identify the backend; never run or substitute both silently. Close `syn` only
with immutable run evidence and non-empty log/netlist artifacts compatible with
the state validator. `soc_syn_pr` reports fresh timestamped artifacts but does
not currently emit pipeline-compatible `loop_evidence`, so its PASS alone must
not close the stage. Structural synthesis is not timing closure; claim timing
only from a real STA report with WNS/TNS.

If synthesis repairs RTL, complete the final synthesis and invalidate
verification once. Follow the RTL-epoch rule if verification already owns
repair.

Physical design uses `soc-openroad_init`, `soc_openroad_run`, and
`soc_openroad_status`. Design-owned handoff files live under `pd/openroad/`;
external ORFS/OpenROAD trees remain separate. Require `de/run/rtl.f` as the RTL
handoff source and do not add a `pd` pipeline stage. Tool or report absence is a
blocker, never a shell fallback or estimated result.
