# UCIe Guidance

Identify the physical, adapter and protocol-layer scope, package topology, lane configuration and reset/training assumptions.

## RTL checks

- Link training, negotiation, active and recovery states have explicit transitions and timeout behavior.
- Lane mapping, width, polarity and lane failure handling are consistent.
- Flit framing, CRC/retry, sequence tracking and flow control preserve ordering.
- Reset and sideband behavior are defined during training and active traffic.
- Multi-instance configuration does not accidentally share state or status.

## DV checks

Cover bring-up, retraining, lane/width changes, CRC/retry, backpressure, reset at each state, error injection and recovery. Keep package/physical assumptions in the project profile and keep this pack protocol-focused.
