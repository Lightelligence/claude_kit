---
name: rtl-dv-review
version: 1
description: Perform read-only RTL/DV review and evidence review before handoff or sign-off.
---

# RTL/DV Review

1. Run `claude-kit plan --workflow review --task "..."` and confirm the
   requested scope before reading implementation details.
2. Default to read-only. Review the diff and intended behavior, then inspect
   reset, handshake, queue, width, error and recovery paths.
3. Check that tests, assertions, coverage and evidence follow the behavior
   change. Check vendor, generated, build and secret boundaries.
4. Findings must include priority, path, evidence, impact and a minimal
   correction direction. Distinguish correctness findings from missing checks.
5. Do not claim sign-off when required checks were skipped; list the smallest
   follow-up that would close each material gap.
