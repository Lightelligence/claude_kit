# AHB Guidance

Identify the AHB revision, master/slave topology, data width, supported burst types, response behavior and HREADY/HRESP timing assumptions.

## RTL checks

- Address/control phase and data phase are aligned with HREADY and the selected transfer type.
- HADDR, HTRANS, HWRITE, HSIZE, HBURST and HPROT remain valid for the correct phase and are not changed during a wait state.
- Sequential, wrapping and undefined-length bursts either follow the supported rules or are rejected explicitly.
- HRESP and error timing are sampled in the correct data phase; wait states cannot duplicate a transfer.
- Arbitration, bus parking, split/retry behavior and default-slave responses are defined when applicable.
- Reset and HREADY behavior cannot leave a master or slave permanently stalled.

## DV checks

Cover idle, non-sequential and sequential transfers, wait states, all supported sizes/bursts, unaligned or illegal accesses, error responses, reset during a transfer and arbitration handoff.
