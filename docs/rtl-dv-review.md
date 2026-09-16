# Using rtl-dv-review in Claude Code

[English] | [简体中文](rtl-dv-review.zh-CN.md)

## Purpose and prerequisites

Use this skill to review a diff, branch, module or DV environment for functional
defects and verification blind spots. It is not an implementation, simulation or
sign-off command. The model reads relevant code, specifications and available
evidence; it does not merely judge isolated snippets.

Open Claude Code in the consumer project. Its `.claude/skills/rtl-dv-review/`
must contain this version of `SKILL.md` and all three `references/` files, either
as deployed files or through the project's managed link. Updating a kit checkout
alone does not update copies already deployed in a consumer project.

Enter the examples below in **Claude Code**, not a shell. No Python command is
needed for everyday review. Replace placeholders with actual paths/refs. If the
skill is missing, have the maintainer check the project's deployed skill path,
selected kit revision and existing deployment mechanism; start a new Claude Code
session after updating. See [skill synchronization](command-reference.md#sync).
The CLI is for integration maintenance, not a prerequisite for each review.
Do not force-sync over project customizations or replace managed links blindly.

## Static review versus EDA validation

By default the skill uses read-only source inspection and may read supplied logs
or reports. It does not automatically compile, simulate, run regression, generate
coverage, synthesize or run CDC. Existing-report analysis is not a new EDA run.
No source edits, report-file writes or PR/MR comments are implied by a review.

| Need | Choose | What it establishes |
| --- | --- | --- |
| Find logic bugs or verification blind spots | `rtl-dv-review` | Evidence-backed static findings, not tool validation |
| Check RTL with the project's VCS-only lint lane | Registered Bazel `soc_lint` | RTL compile/elaboration and lint results; not DV testbench validation |
| Check a DV environment/target compiles | Registered Bazel `soc_comp` | Selected testbench compile/elaboration; not runtime correctness |
| Exercise a specific runtime scenario | Registered `soc_sim`, after selection | Results for that test/configuration/seed, not complete coverage |
| Investigate an existing failure | `rtl-dv-debugging` and relevant debug tools | Failure diagnosis using bounded evidence |
| Check delivery claims and artifacts | `rtl-dv-evidence` | Evidence consistency/completeness, not new design proof |

Tool names above describe the project's Bazel contract. Inspect the enabled
server/schema and target mapping; similarly named Make tools are not interchangeable.
EDA execution follows project authorization and registered MCP tools. Selecting a
skill does not grant execution authority or remove missing tool/license prerequisites.

## Copy-and-paste examples

### Uncommitted changes

```text
/rtl-dv-review Review my uncommitted RTL and DV changes, including relevant untracked files. Focus on functional bugs and verification blind spots. Do not modify files or run EDA tools.
```

### Branch changes

Use the actual target ref; it might be `github/main` rather than `origin/main`.
This reviews committed changes, not automatically the dirty working tree.

```text
/rtl-dv-review Review changes from the merge-base of <base-ref> and HEAD to HEAD. Record both revisions. Separate newly introduced defects from pre-existing issues. Inspect relevant dependencies as needed. Do not run EDA tools.
```

### RTL module

```text
/rtl-dv-review Review <rtl-module-path> against <spec-path>. Focus on backpressure, simultaneous FIFO push/pop, supported parameter boundaries, and reset or flush with outstanding transactions. Report concrete failure scenarios rather than style preferences. Keep the review read-only; do not run EDA tools.
```

### DV environment

```text
/rtl-dv-review Review <dv-env-path>. Focus on monitor sampling, transaction ownership, scoreboard matching, reset handling, TLM connections, and test completion. Follow affected dependencies only as needed. Separate confirmed defects from missing validation. Do not edit files or run EDA tools.
```

### Assertions and coverage with existing evidence

```text
/rtl-dv-review Review <assertion-or-coverage-file> using <spec-path> and the existing report at <report-path>. Check sampling, reset gating, assertion activation and coverage meaning. Verify the report's source/configuration identity. Missing activation evidence is not proof of vacuity. Do not run simulation or modify exclusions.
```

### Select validation after review

```text
List numbered, targeted validation options for the findings. For each, show the finding addressed, registered MCP tool, exact target/test/configuration, expected evidence and any known runtime or prerequisite. Allow multiple selections. Do not execute anything yet.
```

After reading the actual options, for example:

```text
Run only options 1 and 3 through the registered MCP tools with the listed targets and configuration. Do not add other checks. Report each option separately with status, source revision, tool/target/test/seed where applicable, artifact paths and remaining limitations.
```

Numbers refer to that response, not fixed tool numbers. Resolve missing required
inputs before the affected run; do not invent a target, seed or runtime estimate.
Regression, coverage, synthesis and CDC are separate choices, never implied by DV review.

## What a useful report looks like

Findings come first, ordered by severity. Each includes priority, `path:line`,
trigger/preconditions, evidence, incorrect outcome, impact and a correction direction.
The remainder identifies scope/revisions, assumptions, executed checks and material
unverified items. Example format (illustrative, not an actual project finding):

```text
[P1] <scoreboard-file>:<line>
Trigger: the producer reuses a transaction before the queued handle is compared.
Evidence: the queue retains the same handle that the next sample mutates.
Impact: earlier observations are overwritten, masking or inventing mismatches.
Correction: preserve transaction ownership or snapshot retained data.
Validation: a directed two-transaction test; not executed during this review.
```

No cloning issue should be reported merely because a synchronous subscriber
consumes data immediately without retaining the object. Likewise, unreset invalid
data or a legal legacy coding style is not automatically a defect.
"No actionable findings" means none found within the stated scope; neither that
statement nor successful compilation is sign-off. AI can miss bugs or produce
false positives; engineers should inspect evidence before applying fixes.

## Efficient use and current validation limits

Prefer a diff or named module plus relevant requirements over a full-repository
request. Supply known reports and configuration once. The skill loads RTL,
DV/UVM and assertion/coverage references only when relevant. Review first, then
select the smallest checks resolving specific uncertainty.

Local core tests cover catalog/deployment behavior and reference integrity. The
enhanced instructions have not yet been benchmarked in native ETX Claude Code;
there is no measured detection-rate, false-positive-rate or token-saving claim.

For documentation of other skills, use the
[skill usage documentation checklist](skill-usage-documentation.md).
