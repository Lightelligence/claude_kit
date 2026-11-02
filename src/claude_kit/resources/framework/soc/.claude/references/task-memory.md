# Cross-session memory with bounded context

Use this workflow for a task needing recovery after restart, compact or handoff.
Simple questions and one-step edits need no checkpoint. Reuse the project's
planning workflow: this is its recovery index, not another plan or transcript.

## Information ownership

- Stable shared rules stay in the pinned kit; project conventions stay in
  project instruction files. Both should be short because they consume context.
- Native auto memory holds personal preferences and reusable feedback. It is
  client/machine-local, not synchronized by a kit pin.
- Task facts stay in the consumer's `.claude/task-memory/<task>/STATE.md` and travel with
  the project when committed. Select the task explicitly; never choose the
  latest by timestamp or load all tasks.

Do not copy project status into the kit or temporary progress into native
memory. Do not eagerly `@` import task files or this guide. Read the selected
checkpoint only when missing or changed; keep procedures in on-demand guidance.

## Native auto memory

`claude-kit memory status --project-root .` reports sanitized project settings;
it reads no home-directory memory and cannot determine effective client settings.
`claude-kit memory enable-auto --project-root .` adds an absent
`autoMemoryEnabled` key to `.claude/settings.json`. Existing values and explicit
`false` are preserved; report that choice instead of overriding it. Global/local
settings, hooks, models, MCP servers and native memory files are not changed.
Check `/memory` in the actual Claude Code client for activation and its memory
location: user, managed, environment and session-type overrides can still apply.

## Start, checkpoint and resume

Follow project writable scopes and current authorization. These metadata
commands grant no source/EDA permissions and select no checks. Prefer the
project's pinned launcher, `python <kit>/bin/claude-kit`, using `kit_path` from
`.claude/kit-attachment.toml`. `claude-kit` below is shorthand for that launcher.
There is no memory MCP operation: the agent can run this deterministic metadata
CLI directly without asking the engineer to run Python. EDA routes are unchanged.

1. Choose the explicit task slug from the current task/branch. Read its state:
   `claude-kit memory read --project-root . --task <task>`.
   For a new task, use `memory init` with those options; it refuses to overwrite.
2. Keep Objective, Constraints, Decisions, Progress, Evidence and Next within
   50 lines and 4096 UTF-8 bytes. Include relevant branch/PR/MR and source/run
   identity, unresolved choices and selected/not-run checks. Reference the
   existing plan and full artifacts; do not copy them. Keep credentials and
   private conversation transcripts out of committed checkpoints.
3. At a meaningful change, milestone or handoff, retain the SHA256 from a fresh
   read. Supply a project-relative UTF-8 input file, or pipe UTF-8 bytes with
   `--input -`, to:
   `claude-kit memory checkpoint --project-root . --task <task> --input <file> --expected-sha256 <sha>`.
   Cooperating kit writers use an exclusive OS lock and atomic publication.
   A stale hash or busy writer is a conflict: reread and reconcile, never blindly
   overwrite. Reusable locks live under `.claude/.runtime/task-memory-locks/`;
   the OS releases ownership after a process exits or crashes. Keep runtime files
   Git-ignored and do not delete a lock file while a writer may be using it.
   Versions are rechecked immediately before publication, but external editors
   do not share this lock; avoid editing the same settings/state concurrently.
4. After restart/compact, read only that task's state when absent from context.
   Verify stale branch/source/run/configuration facts before relying on them.
   Checkpoint claims are not verification evidence or new authorization. Retain
   explicit failures and missing evidence.

Oversized/incomplete states are rejected, not silently truncated. Move details
to references while retaining consequential constraints and risks. No state is
added to MCP discovery. The kit helpers make no model/network calls and add no
hooks or per-turn transcript summarization; native auto memory retains its own
client behavior and costs.

## Validation and cost

Use `/context` to inspect actual loaded instructions and `/memory` for native
notes. Splitting text into eager `@` imports does not reduce startup context.
Measure bytes/read counts separately from provider-reported tokens. Recovery
tests and byte bounds do not prove model adherence, billing savings or reduced
compact frequency. A new process should recover constraints, evidence and next
action without rereading conversation history.

References: [native memory](https://code.claude.com/docs/en/memory) and
[context costs](https://code.claude.com/docs/en/costs).
