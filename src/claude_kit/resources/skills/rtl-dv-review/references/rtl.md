# RTL checks

Apply categories touched by the change or needed to explain its effect. Use the
specification, legal parameter ranges and project conventions.

- **Widths and parameters:** Trace signedness, sizing, casts, shifts, truncation
  and overflow to an observable result. Check supported boundary configurations,
  including depth one/non-power-of-two sizes, zero-width `$clog2` uses and bounds.
  An unsupported parameter setting is not a defect unless it must be supported.
- **State and scheduling:** Trace old/new values and assignment ordering across
  processes. Check unintended storage, multiple drivers, combinational loops,
  incomplete updates and required FSM recovery. `always_ff`, `unique case`, enums
  or a particular FSM partition are not universal requirements; a pattern alone
  does not establish an incorrect result.
- **Transfer and backpressure:** Identify the actual acceptance condition. Check
  payload/control stability under stalls, packet boundaries, response association
  and state advancement. Trace loss, duplication, ordering or failed progress with
  a concrete sequence. Apply protocol-specific rules only to that protocol/version.
- **Queues and credits:** Trace empty/full, simultaneous push/pop, wraparound and
  reset/flush with outstanding entries. Derive occupancy/credits from permitted
  operations; full-plus-pop acceptance is a contract choice. Check bypass and
  read-during-write assumptions against the instantiated memory/primitive.
- **Reset and recovery:** Trace assertion/release, reset/flush/transfer priorities
  and stale valid/data/response state. Unreset data can be safe when invalid and
  unable to affect architectural state. Check X-sensitive control under reachable
  initialization/error scenarios, not hypothetical unsupported inputs.
- **Clock/reset crossings:** Inspect affected signal purpose, synchronizer,
  handshake or FIFO structure, pulse capture and multi-bit coherency. Two flops
  alone do not establish safe multi-bit transfer. Identify missing CDC/RDC or
  constraint evidence; do not claim physical/timing sign-off from source review.
- **Integration:** Follow changed ports, parameters, generate branches, packages
  and build selection into affected users. Check elaboration assumptions and
  tested configurations. Do not assume unused vendor/generated variants are active.

Example: trace an overwritten registered payload while `valid && !ready` to the
lost transaction under the interface contract. Changing invalid payload data is
not itself a handshake violation.
