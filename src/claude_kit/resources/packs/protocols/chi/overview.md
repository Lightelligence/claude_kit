# CHI Guidance

State the CHI version, node roles, channel subset, snoop scope, data width, credit model and ordering rules before applying this pack.

## RTL checks

- Request, response, data and snoop channels have explicit ownership and ordering rules.
- Credits are consumed and returned exactly once; underflow and overflow are impossible.
- Transaction IDs, source IDs, DBIDs and response matching are preserved.
- Snoop, retry, barrier, DVM and data corruption/error behavior match the supported subset.
- Link activation, deactivation, reset and recovery do not leak outstanding transactions.
- Width conversion and data beat ordering are explicit.

## DV checks

Cover reads, writes, atomics if supported, snoop hits/misses, retry, barriers, credit pressure, out-of-order responses, data errors, reset with outstanding traffic and link recovery. Keep the exact supported CHI subset in the project profile.
