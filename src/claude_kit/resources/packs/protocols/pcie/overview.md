# PCIe Guidance

State the generation, lane width, transaction layer scope and whether the task concerns configuration, link training, TLP, DLLP or PHY behavior.

## RTL checks

- LTSSM transitions and timeout/error recovery are explicit.
- Link width, lane state and reset assumptions are consistent.
- TLP header fields, length, byte enables, tags and completion matching are checked.
- Ordering, replay, flow control and credit accounting are not silently simplified.
- Unsupported requests, malformed packets and poisoned/error traffic have defined behavior.
- Configuration and status side effects are synchronized with link state.

## DV checks

Cover link bring-up, retrain, width changes, configuration accesses, memory traffic, completions, tags, flow-control pressure, malformed/error packets and recovery. Project-specific VIP and simulator settings belong in the profile.
