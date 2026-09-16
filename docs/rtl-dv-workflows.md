# RTL/DV workflow skills: engineer guide

[English] | [简体中文](rtl-dv-workflows.zh-CN.md)

This is a bounded guide for engineers using the kit in a consumer RTL/DV
repository. It explains the five distinct capabilities and the separate
<code>rtl-dv-review</code> skill. It is an engineer-facing companion to the
short deployed skill instructions, not an exhaustive tutorial.

## At a glance

The six requested entries are consolidated into five visible capabilities.
There is no duplicate context slash command. These are composable entry points,
not a mandatory chain. The thin
<code>rtl-dv-kit</code> entry handles discovery, configuration facts, bounded
task facts and routing; it does not require
<code>doctor → plan → context → check</code> before every task. The wider kit
may contain other skills that are outside this guide.

| Entry | Status | Use it for | Normal boundary |
| --- | --- | --- | --- |
| [rtl-dv-kit](#rtl-dv-kit) | Canonical | Onboarding, configuration discovery, bounded task-fact resolution and routing | Read only what is missing or stale; no profile mutation, install, extra server or automatic EDA |
| [dv-engineering](#dv-engineering) | Canonical | Scoped DV test, sequence, checker or environment planning and implementation | Source changes are task-scoped; validation is an engineer-selected menu or an explicit delegation |
| [rtl-dv-evidence](#rtl-dv-evidence) | Canonical | Auditing verification claims or preparing a requested evidence file | Audits are read-only; file creation needs an explicit deliverable and writable destination |
| [rtl-dv-regression](#rtl-dv-regression) | Canonical | Planning a check set, selecting runs, or triaging/comparing result sets | New execution and expansion need explicit selections; a requested retry gets a bounded budget and linked identity |
| [rtl-dv-debugging](#rtl-dv-debugging) | Canonical | Single-causal diagnosis of an existing compile, runtime, assertion, scoreboard, timeout or coverage failure | Diagnosis is read-only by default; a fix and a rerun are separate selections |
| [rtl-dv-review](#rtl-dv-review) | Companion skill | Read-only review of RTL/DV code, diffs and verification blind spots | No source edits, report writes or EDA by default; see the [review guide](rtl-dv-review.md) |

Use review for code correctness, regression for result-set/run selection, and
evidence for claim/artifact auditing. Debugging narrows one existing failure to
one causal hypothesis; it is not a replacement for result-set triage or a code
review.

## Before you start

This checklist separates skill deployment from the project capabilities that a
skill may need:

- Start Claude Code in the consumer project root. The project profile, normally
  <code>.ai/project.toml</code>, is the authority for paths, permissions,
  check mappings and execution policy. A kit checkout by itself does not
  update skills already deployed in a consumer project.
- Ensure the selected skill is deployed under
  <code>.claude/skills/&lt;skill-name&gt;/SKILL.md</code> or through the
  project's managed link. The canonical kit source is
  <code>resources/skills/rtl-dv-kit/SKILL.md</code>. A minimal deployment may
  contain only <code>rtl-dv-kit</code>; the kit contains its own configuration,
  bounded-facts and routing guidance. New deployments do not include a second
  context entry; see migration notes below for existing installations.
- If the task needs kit MCP functions, the project's <code>.mcp.json</code>
  must register the <code>claude-kit</code> server and the needed project
  server/tool must be available. Skill text being present is not evidence that
  an MCP tool, simulator, license, remote runner or same-named subagent exists.
- When configuration is missing, changed or unknown, resolve the relevant
  profile facts with the registered MCP function
  <code>get_project_profile</code>. Resolve unclear workflow or check choices
  with <code>plan_task</code> only when needed. Neither call authorizes a check,
  changes permissions or changes the profile.
- For an operation that needs execution, bind the authoritative source revision,
  target, test/configuration, seed, simulator, working directory and artifact
  destination as applicable. Do not guess aliases, paths, argv or run identity.
- In a project with an MCP-only execution policy, an unavailable registered tool
  is a blocker: there is no shell fallback. Declared build wrappers are usable
  only when the project policy permits them. Selecting a skill never authorizes a
  simulator, regression, coverage, synthesis or CDC run.
- Names such as <code>dv-engineer</code>, <code>commander</code>,
  <code>regression-triager</code> and <code>debugger</code> describe guidance,
  not proof that Claude Code has installed subagents with those names. Apply
  available guidance in the current session when necessary.
- Do not load this guide or a long tutorial by default from a skill. Load only
  the relevant deployed skill and conditional reference material; follow this
  guide when an engineer needs the usage contract.

## Claude Code invocation versus maintenance CLI

The prompts in this document are messages for Claude Code. They are not shell
commands. Claude Code is the normal engineer interface and should use the
registered MCP bridge. The repo-local CLI is for maintenance, deployment
diagnosis and scripted inspection; it is not a second execution backend for a
project whose policy requires MCP.

| Need | Claude Code | Maintenance CLI |
| --- | --- | --- |
| Discover or route a task | Invoke <code>/rtl-dv-kit</code>; use its MCP-backed profile/catalog functions only as needed | <code>claude-kit doctor --project-root . --strict</code> when validating setup |
| Inspect or deploy skill inventory | Ask Claude Code to inspect the registered kit MCP | <code>claude-kit list skills</code>; a maintainer may use <code>claude-kit sync --project-root .</code> to refresh deployment |
| Resolve unclear routing in maintenance scripts | Ask Claude Code to call <code>plan_task</code> | <code>claude-kit plan --task "&lt;task&gt;"</code> |
| Audit or strictly validate evidence | Invoke <code>/rtl-dv-evidence</code>, which can use registered <code>review_evidence</code> | <code>claude-kit evidence check --strict</code> |

The CLI commands above are examples of maintenance entry points; they do not
replace an engineer's selection or grant permission to run EDA. A sync can
write deployed skill files, so it belongs to project maintenance rather than an
ordinary source-edit conversation. Do not install third-party packages or add
MCP servers merely to make a skill appear usable.

Ordinary sync preserves existing files; it does not refresh old copies automatically.
Use the project's deployment mechanism and review customizations before forced updates.
The canonical integration skill now lives in the catalog, not a duplicate template.
Minimal init, full sync and shared attachment use it. Shared attachment reports
conflicts with project-owned integration files instead of silently overwriting them.

## Result statuses and the sign-off boundary

Use these statuses consistently in check menus, run reports and evidence:

| Status | Meaning |
| --- | --- |
| <code>passed</code> | The selected command or check ran, expected results were checked, and required artifacts are present |
| <code>failed</code> | The selected command ran and the check or expected result failed; preserve the first causal evidence |
| <code>blocked</code> | The item could not run because an authorization, input, tool, license, runner, permission or artifact prerequisite was missing |
| <code>skipped</code> | The item was intentionally not selected or was omitted by scope; state why |
| <code>unknown</code> | Available evidence cannot establish the execution outcome; an incomplete record can instead be reported as a separate record-validation gap when the outcome is known |

“Not run” is a fact to report alongside <code>skipped</code> or
<code>blocked</code>; it is not a reason to call a result passed. A clean tool
exit, registration, plan, generated report or strict evidence-validation pass
does not prove design correctness or sign-off.

Execution outcome and evidence-record completeness are separate axes. If
project evidence establishes that a check passed or failed but the exact argv is
missing, keep <code>passed</code> or <code>failed</code> and record the missing
argv as a record-validation gap. Use <code>unknown</code> for the execution
outcome only when the available evidence cannot establish what happened.

For a claim or evidence record, expect:

- project/root, task, source revision and relevant dirty state;
- target, test/configuration, seed, simulator and working directory when
  applicable;
- the exact invocation/argv when available, the result status, exit or job
  outcome, and expected artifact locations; if argv is unavailable, record that
  as a record-validation gap without changing a separately established outcome;
- project-relative changed paths and a reason for each path when files changed;
- supporting evidence, residual risks, coverage gaps and every skipped, blocked
  or unknown item.

Strict evidence validation checks the evidence file's schema and allowed
path/permission structure. It does not determine whether a claim is true or
authenticate the identity, argv, tool execution or artifact provenance. The
separate model/engineer audit must reconcile those facts with the actual project
and run evidence. Strict validation does not rerun the design or turn a failed
run into a pass.

External compile or simulation logs may be read only through the configured
artifact-discovery/read interface, such as
<code>discover_regression_artifacts</code> followed by
<code>read_regression_artifact</code>. A record must use the exact returned run
identity and an authorized project-local receipt or metadata path when the
project contract requires one. Do not invent a project-local path, argv, run ID,
artifact or passing result to satisfy the schema. Missing run identity may limit
the execution conclusion; a missing local receipt is a separate representation gap,
not grounds to relabel a known outcome. Read-only audits need no new receipt.

<a id="rtl-dv-kit"></a>
## rtl-dv-kit — discovery, bounded facts and routing

### Purpose and boundary

Choose this canonical entry for onboarding, uncertain routing or a task whose
configuration facts may be stale. It reads the configured profile and
applicable project instructions, resolves only the facts that affect the
bounded task, and points to the smallest useful capability or registered tool.
It does not mutate <code>.ai/project.toml</code>, rewrite permissions, install
anything, add servers, or run EDA. A known, straightforward edit does not need
a formal discovery sequence.

### Copyable Claude Code prompts

~~~text
/rtl-dv-kit Discover the configured RTL/DV profile and route this task: <task>. Reuse facts already in the session, resolve only missing or stale facts, and return the smallest useful next skill or registered tool. Do not modify the profile, install anything, add servers, or run EDA.
~~~

~~~text
/rtl-dv-kit The task is <task>. Check only the configuration and bounded task facts that affect this work, separate observed facts from assumptions, and list any missing prerequisites. Do not start a mandatory doctor/plan/inspect chain, mutate project configuration, or execute checks.
~~~

### Expected output

Expect the authoritative project/root and relevant permissions, the selected
capability or tool, the facts used, assumptions or conflicts, and only the
missing prerequisites that affect the next action. For a minimal deployment, the
output must still be useful without <code>rtl-dv-context</code>.

### Efficiency and limits

Reuse known facts and invoke profile or planning discovery only when a fact is
unknown, changed or consequential. Do not enumerate every server or load every
skill to answer a narrow routing question. The output is routing/context
evidence, not execution evidence or design sign-off.

## Retiring the old context entry

`rtl-dv-context` is folded into `/rtl-dv-kit` and is no longer listed or deployed
as a slash command. Legacy CLI/MCP requests may still resolve the old ID internally;
this does not expose a second skill.

Reattachment removes only the old kit-managed symlink whose fingerprint still
matches, leaving its target intact. Modified links and project-owned directories
are preserved and reported in `retired_managed_paths`. Copied installations are
not automatically pruned by sync: review and preserve custom instructions, then
move the old `SKILL.md` outside `.claude/skills` and use the canonical entry.
Do not force-sync over custom configuration. This change does not update an
existing XinAnRiver deployment; updating the kit alone is not consumer migration.

<a id="dv-engineering"></a>
## dv-engineering — scoped DV implementation

### Purpose and boundary

Use this canonical capability to plan or implement a focused DV test, sequence,
checker or environment change. Separate plan-only requests from edits. Map the
relevant positive, boundary, negative, reset and recovery behavior to stimulus,
observation, expected result and diagnostics; keep driver, monitor, scoreboard,
reference-model and coverage ownership clear. A test or covergroup definition
does not prove that it ran.

An implementation is not an automatic simulation, regression, coverage,
synthesis or CDC request. Present the engineer with numbered applicable checks,
and execute only the selected items in the selected order or those explicitly
delegated to an available commander. In an MCP-only project, a missing project
tool blocks the affected item; it never authorizes a shell wrapper.

### Copyable Claude Code prompts

~~~text
/dv-engineering Implement the focused DV change for <target> covering <scenarios>. Inspect relevant DUT and bench conventions, keep stimulus/observation/checker ownership explicit, and report changed files and static checks. Do not run simulation, regression, coverage, synthesis or CDC.
~~~

~~~text
/dv-engineering Plan a focused DV change for <target> and map <requirements> to positive, boundary, negative, reset and recovery scenarios where applicable. Show driver/monitor/scoreboard/reference-model/coverage responsibilities and the smallest static checks. Do not edit files or run EDA.
~~~

~~~text
/dv-engineering Present numbered validation choices for this change, including the registered project MCP tool, target/test/seed/simulator, expected evidence and known cost or unknown cost. Allow multiple selections in engineer order; do not execute until I explicitly select items or delegate the selected run to an available commander.
~~~

### Expected output

Expect the changed project-relative paths and reasons, scenario/checker
coverage, static findings, and a validation menu that separates quick static or
compile checks from simulation, regression, coverage, synthesis and CDC. After
selection, expect one report per selected item, aggregate counts and remaining
blind spots. The default simulation/regression state for a new test is
<code>skipped</code> or <code>not run</code>, not passed.

### Efficiency and limits

Read the affected DUT and bench only, then load the relevant change-check
reference. Start with the cheapest selected check that can distinguish the
suspected issue, and preserve the first causal failure before proposing wider
execution. This capability is implementation-scoped; use review for independent
code review, regression for result sets and evidence for claim auditing.

<a id="rtl-dv-evidence"></a>
## rtl-dv-evidence — claim and artifact audit

### Purpose and boundary

Use this canonical capability to audit verification claims, existing logs or
artifacts, or to prepare a reproducible evidence file that the engineer
explicitly requests. Auditing is read-only and does not modify source, approve
waivers, clean artifacts, publish comments or execute EDA. Evidence audits
claims and their support; it is not a code review.

File preparation is a separate operation: it needs a requested deliverable and
an authorized writable destination. Preserve historical failures and exceptions
instead of correcting them into a passing record.

### Copyable Claude Code prompts

~~~text
/rtl-dv-evidence Audit the verification claims for <task> using the current project files and authorized existing artifacts only. Bind each claim to source revision, target/test/seed/simulator/configuration, run identity and artifact location; classify every check as passed, failed, blocked, skipped or unknown. Do not run EDA or edit files.
~~~

~~~text
/rtl-dv-evidence Validate <evidence-file> with the registered review_evidence tool in strict mode for schema and allowed path structure. Separately audit whether identities, exact argv, statuses and artifact references are truthful and belong to the claimed run; report tool-validation errors separately from audit findings. Do not treat strict validation as design sign-off.
~~~

~~~text
/rtl-dv-evidence Create or update the project-local evidence file at <destination> for <task>, only as explicitly requested. Preserve actual results and exceptions; use authorized project-local receipts for external logs, and never invent paths, argv, run IDs or passing results. Do not rerun checks.
~~~

### Expected output

Expect claim-by-claim statuses with supporting locations, contradictions, stale or
missing evidence, residual risks and the smallest action that closes each
material gap. For file preparation, expect the destination, changed paths and
reasons, validation result and any record-contract errors. A strict pass means
the evidence record is well-shaped; it can still document failed or blocked runs.

### Efficiency and limits

Reuse supplied evidence and read only bounded log/artifact regions. Use
<code>read_artifact</code> for checkout-local files; use configured discovery
and read tools for external roots. If the exact invocation or authorized
receipt is unavailable, do not reconstruct it: record a record-validation gap.
Keep a separately established execution status unchanged, and use
<code>unknown</code> or <code>blocked</code> for the execution outcome only when
the result or authorization itself cannot be established. This skill does not
establish functional sign-off.

<a id="rtl-dv-regression"></a>
## rtl-dv-regression — result sets and run selection

### Purpose and boundary

Use this canonical capability in one of two modes: plan a bounded check set, or
triage/select/compare an existing result set. Planning and existing-result
triage are read-only. A new or modified test, a failure explanation or a
recommended check does not authorize a run.

Execution is limited to the engineer's explicit selections or delegation. Bind
each run to source revision and dirty state, target, test/configuration, seed,
simulator, working directory and run/artifact identity. A single selected run
does not need a separate retry-budget approval. If a retry is requested, declare
a bounded budget, record each retry as a new linked run and preserve the
original identity; do not silently add seeds or a wider slice. Compare only runs
with known identity and provenance, including intentional baseline/candidate
source differences that are stated and accounted for.

### Copyable Claude Code prompts

~~~text
/rtl-dv-regression Triage the existing result set at <artifact-or-run-list> for <task>. Reuse current selections and preserve the first causal error; report target/test/configuration, source revision, seed, simulator, working directory and run identity. Do not execute new checks.
~~~

~~~text
/rtl-dv-regression Run only selections <numbers> that I explicitly approved through the registered project MCP interface. Preserve engineer order and report every item separately; if a retry is requested, use a declared retry budget and record each retry as a new linked run without changing the original identity. Do not add wider slices, use a shell fallback, or clean up artifacts.
~~~

~~~text
/rtl-dv-regression Compare baseline run <run-a> with candidate run <run-b> only after verifying the complete known identity of both: source revision, target, test/configuration, seed policy, simulator, working directory and run/artifact identity. Intentional source-revision differences are allowed when the baseline/candidate relationship is explicit; state every relevant difference and limit conclusions to comparable dimensions. If identity or provenance is missing, report unknown or blocked instead of choosing by modification time or inventing argv.
~~~

### Expected output

Expect one result per selected check or observed run, the aggregate count with
its denominator, exact run identity, first causal evidence, failure class,
artifact paths and unresolved gaps. Separate tool exit state from verification
outcome, and identify which comparison conclusions are supported. External
artifacts remain visible, including in-progress lock files; triage does not
delete logs, waveforms, coverage databases or locks.

### Efficiency and limits

Start with the cheapest selected check that distinguishes environment, compile,
elaboration, runtime, protocol, assertion, scoreboard, timeout or coverage
failure. Read bounded summaries and first errors before opening a representative
artifact for each provisional failure group. This capability handles result
sets and run selection; use debugging for one causal failure and evidence for
claim reconciliation.

<a id="rtl-dv-debugging"></a>
## rtl-dv-debugging — single-causal diagnosis

### Purpose and boundary

Use this canonical capability to diagnose an existing compile, elaboration/link,
runtime, protocol, assertion, scoreboard, timeout or coverage failure from
bounded evidence. Reduce the investigation to one test/seed, transaction,
cycle or state transition and state a falsifiable root-cause hypothesis.

Diagnosis is read-only by default. A request to explain a log does not authorize
source changes, instrumentation, waveform regeneration, simulation or cleanup.
If the engineer explicitly requests a fix, the fix is still bounded and a rerun
is a separate selection. Preserve existing session and evidence ownership.

### Copyable Claude Code prompts

~~~text
/rtl-dv-debugging Diagnose the existing failure in <log-or-session>. Verify its project, source revision, target/test/seed, simulator/configuration, working directory, run identity and first meaningful error; state supported causes or remaining alternatives and do not modify files or rerun anything.
~~~

~~~text
/rtl-dv-debugging Inspect the existing debug session <session-id> and evidence owned by <owner-or-project>. Read only bounded logs/waveform windows needed for <failure>; preserve database identity and session ownership, and report missing or optimized-away data as a gap. Do not close or overwrite sessions you do not own.
~~~

~~~text
/rtl-dv-debugging I explicitly request a fix for <path-or-cause>. Make only the smallest authorized change, then present a separate rerun selection with target/test/seed/tool and expected evidence. Do not rerun until I select it, and preserve the original failure plus before/after identity.
~~~

### Expected output

Expect the supported cause or remaining alternatives, confidence and evidence,
first causal location/time, failure class, expected versus observed behavior and
the smallest discriminating next check. If a fix is authorized, report changed
paths and before/after results—or <code>blocked</code>, <code>skipped</code> or
<code>unknown</code>—without erasing the original failure.

### Efficiency and limits

Read small log regions and bounded waveform windows first. Treat unavailable
signals, optimized-away data and missing ownership as evidence gaps, not zero
values or proof of absence. Do not expand a single diagnosis into an automatic
regression; use regression when the question is which runs/results to select.

<a id="rtl-dv-review"></a>
## rtl-dv-review — companion read-only review

### Purpose and boundary

Use the companion skill for a read-only review of a diff, branch, RTL module,
DV/UVM environment, assertion or coverage claim. It establishes concrete
findings and verification blind spots from source and supplied evidence; it is
not implementation, simulation or sign-off. The fuller examples and report
shape are in the [rtl-dv-review usage guide](rtl-dv-review.md).

### Copyable Claude Code prompts

~~~text
/rtl-dv-review Review <diff-or-path> against <spec-or-base>. Keep the review read-only, trace concrete triggers to incorrect outcomes, separate confirmed defects from hypotheses and verification gaps, and do not run EDA or edit files.
~~~

~~~text
/rtl-dv-review After the read-only review, list numbered targeted validation options for the findings. For each, show the registered MCP tool, target/test/configuration, expected evidence and missing prerequisites; allow multiple selections but do not execute anything yet.
~~~

### Expected output

Expect findings ordered by impact with priority, <code>path:line</code>,
trigger/preconditions, evidence, incorrect outcome/impact and a smallest
correction direction. Then expect scope/revisions, assumptions, executed checks
and unverified items. “No actionable findings” is limited to the stated scope
and is not sign-off.

### Efficiency and limits

Provide a narrow diff or named module plus the relevant requirement and existing
reports. Load only the conditional review references needed for the changed
behavior. Select validation separately through project-authorized MCP tools; no
EDA is implied by invoking review.

## Efficient use and honest validation limits

- Begin with the smallest useful input: a named target/module, focused diff,
  existing result set or bounded log window. Reuse facts and evidence across
  skills instead of repeating discovery.
- Use the kit once for an actual unknown or routing gap. Internal compatibility
  for old IDs does not expose another skill. Load conditional
  references only for the affected domain.
- Preserve the first causal failure, keep selected-item order, and continue an
  independent selected item only when the project interface and dependencies
  make that safe. If retries are requested, keep them within a declared budget;
  wider expansion or new slices still need explicit selection.
- Treat documentation-only and local catalog/deployment checks as limited
  evidence. This guide does not run EDA, access ETX, add servers, install
  third-party packages or create external artifacts.
- No measured token, latency, accuracy, detection-rate or false-positive claim
  is made here. The current validation snapshot is 40 core tests, 15 CLI tests,
  20 deployment tests with two Windows-inapplicable cases skipped, seven new
  deployment/routing tests passed, and seven MCP tests passed. An independent
  eight-scenario instruction reasoning exercise is complete. These counts are not a native-Claude
  benchmark; local tests can check links, catalog/deployment behavior or
  reference integrity, but cannot prove native Claude behavior, simulator
  correctness or RTL sign-off.

## Navigation

- [Repository README](../README.md) and [command reference](command-reference.md)
  cover installation, profiles and CLI/MCP details.
- [Skill usage documentation checklist](skill-usage-documentation.md) is the
  maintainer checklist for keeping the English and Chinese guides aligned.
- [rtl-dv-review usage guide](rtl-dv-review.md) and
  [Chinese review examples](rtl-dv-review.zh-CN.md) contain the fuller
  read-only review examples.
- This guide is linked for human use; it is not a default skill dependency.
