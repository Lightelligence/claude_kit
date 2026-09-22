# Regression log evidence

Use the connected `claude-kit` server. The project launcher adds two read-only
tools. The project adapter also limits artifact reads to 12,000 bytes by
default and reads only that prefix from disk; explicit larger limits remain
available. Check `truncated`, `bytes_read`, and `stable`. The kit submodule
remains pinned and unchanged. `resolve_context` requires a task and uses only
explicitly selected roles/packs/skills; omitted arrays mean none. Prefer
`get_project_profile` for project facts and reuse unchanged results.
Reconnect the server after updating the launcher so the new tools are discoverable.

1. Use `discover_regression_artifacts` with the known target/test/run ID. Select
   the exact returned log; resolve ambiguous runs with the engineer. Do not pick
   by modification time or `.last_sim` / `.last_fail`.
2. Call `summarize_regression_log(path)` before requesting raw log text. It returns
   diagnostic counts, exact duplicate groups, first detected error, nearby lines,
   phase hints, reported outcomes, and the scanned tail. These are evidence, not
   an automatic root-cause diagnosis or verification signoff.
3. Expand relevant evidence using `read_regression_log_range(path, start_line,
   line_count, expected_fingerprint)`. Lines are one-based. Pass the summary's
   fingerprint; stale files are rejected. Continue with `next_line` / `next_column`
   when output is bounded; `start_column` is zero-based.
4. Preserve raw files and report the selected run, log path, line ranges, observed
   status, and remaining uncertainty. Reuse current evidence instead of rereading
   whole logs; refresh after file/run changes.

## Completeness and limits

- No errors found is `unknown` unless an explicit pass marker is present in a
  complete, stable scan. Even `reported_pass` is only the selected log's report.
- Conflicting success/failure evidence is `conflicting`. A present run lock or
  a file changing during summary prevents a pass conclusion.
- UVM summary counts are separate from diagnostic occurrences; `UVM_ERROR : 0`
  and `UVM_FATAL : 0` are not errors. Addresses, seeds, and values are not removed
  when grouping diagnostics. Warning counts remain visible.
- Defaults: eight diagnostic groups, two context lines, a 64 MiB scan limit, and
  12,000 output characters. Larger explicit limits are bounded by tool schemas.
- Check `scan_complete`, `stable`, `stop_reason`, `output_truncated`,
  `omitted_diagnostic_events`, and per-line `text_truncated`. A scanned tail is the
  actual file tail only when `tail_is_file_end` is true.
- Physical lines over 64 KiB stop the scan explicitly; invalid UTF-8 is flagged.
  Limits do not mean success. Keep the original artifact available and report
  incomplete evidence when these tools cannot cover the required text.
- A fingerprint describes file metadata, not a permanent content cache. A full
  stable summary also returns SHA-256. A range read stops after its requested
  window; its `scan_complete` need not be true when the requested range is complete.

The adapter relies on the pinned kit's framing, dispatch, and profile helpers.
Run `.claude/scripts/tests/test_kit_log_bridge.py` after kit/runtime updates;
it uses temporary synthetic logs and the real launcher, without EDA execution.
