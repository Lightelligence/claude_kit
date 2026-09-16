# Evidence format and limitations

Use the installed kit's schema/validator, not an invented success envelope.
The schema_version=1 contract requires project, task and checks; record
source_revision when available and note any dirty changes affecting the result.

- Changes use project-relative strings or objects such as
  `{"path": "dv/obsolete.sv", "operation": "delete"}`. Record reasons separately.
  A schema-valid deletion entry does not authorize deleting anything.
- Each check needs name and status: passed, failed, blocked, skipped or unknown.
  Put explanatory reasons in the check/risks record. Human-facing "not run"
  maps to skipped when intentionally unselected, blocked when prerequisites
  prevent an intended check, or unknown when execution/outcome cannot be established.
- command is an array of actual invocation tokens when available. Do not fabricate
  simulator argv from a high-level MCP request. Preserve real server/tool/arguments
  and result receipt separately; if exact command evidence is unavailable, say so.
  A passed record without command evidence fails current strict validation.
  Keep the observed check outcome and this record-validation failure separate;
  do not relabel a known execution result merely to satisfy the validator.
- artifacts/artifact accepts a project-relative file path or array of such paths.
  The validator checks file existence; it does not authenticate every result.
  An absolute external regression path cannot be placed in this field.
- For external logs use configured discovery/read tools. If file preparation is
  requested, a task-owned project-local receipt/excerpt can preserve external path,
  run ID, source identity and observed result. Describe it as an excerpt/receipt,
  not the original complete log. Save only with authorized destination/permission.
  Otherwise report the representation/validation gap without copying data or faking
  a local path. Keep remote identifiers as provenance, not local artifacts.
- Strict validation promotes warnings to errors, including missing files or
  unsupported permission scope. Do not drop failed checks, edit history, invent
  artifacts or broaden project permissions to make the validator green.

Record applicable target, test, seed, simulator, cwd, exit status, job/run identity
and remaining risks in addition to the minimum schema. Irrelevant fields may be
omitted; unknown relevant fields must stay explicit. Redact secrets.

A strict PASS means the evidence record meets the validator contract. A record
can validly describe failed/blocked/skipped checks; PASS does not mean those checks
passed, that execution happened at review time, or that the design is signed off.
