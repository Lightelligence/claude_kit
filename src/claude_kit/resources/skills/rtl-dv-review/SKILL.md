---
name: rtl-dv-review
version: 1
description: Perform read-only RTL/DV review and evidence review before handoff or sign-off.
---

# RTL/DV Review

Default to read-only. Review the diff, intended behavior, reset, handshake, queue, width, error and recovery paths. Check that tests, assertions, coverage and evidence follow the behavior change. Check vendor, generated, build and secret boundaries. Findings must include priority, path, evidence, impact and a minimal correction direction. Do not claim sign-off when required checks were skipped.
