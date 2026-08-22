# Common RTL/DV Guidance

Use this pack for every project unless the project explicitly replaces a rule.

## Analyze before edit

- Locate the project root and validate the project profile.
- Read local CLAUDE.md or equivalent project rules.
- Separate source, test, vendor, generated and artifact paths.
- Identify the project-owned command wrapper before running tools.

## Correctness baseline

Check reset and initialization, state-machine completeness, handshake stability, queue boundaries, parameter widths, signedness, error behavior, timeout, retry and recovery.

## Verification baseline

For every behavioral change, consider a focused positive test, a boundary test, a negative test, reset/recovery behavior, assertion coverage and evidence.

## Evidence baseline

Record the exact command, working directory, result, artifact path and anything not run. Never claim verification from inspection alone.
