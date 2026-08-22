# AXI4-Stream Guidance

Identify the stream width, packet boundary, byte qualifiers, sideband ownership, optional interleaving and whether empty or partial beats are legal.

## RTL checks

- TDATA and all enabled sidebands remain stable while TVALID is high and TREADY is low.
- TLAST marks the intended packet boundary and is preserved through width conversion or buffering.
- TKEEP/TSTRB semantics for partial final beats are explicit and consistent with packet length.
- TVALID does not depend combinationally on TREADY in a way that creates a loop or deadlock.
- Reset, flush, packet drop and error paths cannot leak stale data or sideband state.
- Arbitration and interleaving preserve the documented source, destination, ID and user metadata.

## DV checks

Cover single-beat and multi-beat packets, all legal partial beats, backpressure at every beat, continuous traffic, idle gaps, reset/flush mid-packet, error/drop paths and concurrent stream arbitration.
