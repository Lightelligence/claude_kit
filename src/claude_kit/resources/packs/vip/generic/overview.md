# Generic VIP Guidance

## Configuration

- Record VIP and simulator versions in the project profile.
- Keep library paths, macros, class names and license settings project-local.
- Map every interface instance to exactly one intended clock, reset and protocol endpoint.
- Make instance count, active/passive mode, direction and monitor policy explicit.
- Do not assume a library being present means the configured agent is usable.

## Smoke

Run reset, one legal transfer, delayed response/backpressure, one error and recovery. Check for duplicate configuration, missing virtual interfaces, unconnected clocks/resets, unexpected X values and scoreboard mismatches.

## Evidence

Record the mapping, configuration source, command, result and log/artifact path. Keep third-party and generated sources read-only by default.
