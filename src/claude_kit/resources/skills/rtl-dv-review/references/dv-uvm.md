# DV/UVM checks

Trace the affected stimulus -> driver -> DUT -> monitor -> checker path, expanding
only as needed. Use the project's UVM version/architecture; do not require UVM
patterns in a non-UVM bench.

- **Stimulus:** Check randomization return handling, constraints, reachable
  boundary/error scenarios, sequence-driver completion and reset interruption.
  A passing test with no accepted traffic does not demonstrate the intended check.
  Do not require every sequence to be coverage-driven.
- **Sampling and ownership:** Check clocking event/skew and scheduling against
  DUT sampling/updates. Count accepted transfers, not asserted-valid cycles.
  For retained transactions, trace aliases to producer objects reused later;
  cloning is unnecessary when ownership/lifetime already makes retention safe.
- **Scoreboards/models:** Check identity/order/latency matching, including permitted
  reordering, duplicates, missing/unexpected responses, masks, X handling and error
  propagation. Trace reset/flush disposal of outstanding predictions and actuals.
  Predictions must not simply reproduce or read the faulty DUT result being checked.
- **Connectivity/configuration:** Trace relevant TLM connections, virtual interfaces,
  config_db scope/type and active/passive settings. Determine whether disconnected
  ports are required or intentionally optional. Check factory creation/registration
  where overrides are needed; direct `new()` is not automatically a functional bug.
- **Completion:** Trace objections, outstanding work, checker draining, timeout and
  final error status. Sequence completion may precede response checking. Relate
  drain time to allowed latency/pending-work detection rather than assuming fixed
  delays are always wrong. Check early finish, filtering and disabled checkers.
- **Registers (when affected):** Compare map, access semantics, reset, adapters and
  prediction with the contract. Account for volatile/side-effect fields; generic
  bit-bash or mirror comparisons are not appropriate for every register.
- **Integration:** Confirm test/config/build selection reaches changed sources and
  enabled checkers. Record reproducible seed/config evidence. Load the assertion
  and coverage reference only when relevant; do not launch runs to fill gaps.

Example: a monitor reuses one object while a scoreboard queues its handle for later
comparison, corrupting earlier observations. If the subscriber consumes values
immediately without retaining the handle, absence of a clone alone is not a finding.
