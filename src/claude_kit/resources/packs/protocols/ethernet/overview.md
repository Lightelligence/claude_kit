# Ethernet Guidance

First identify the layer and interface: MAC, PCS, SerDes, packet stream, management bus or link training.

## RTL checks

- Frame boundaries, length, padding, CRC/FCS ownership and error propagation are explicit.
- Ready/valid backpressure cannot drop, duplicate or reorder data.
- Minimum/maximum frame and malformed-frame behavior is defined.
- Clock-domain crossings and elastic buffering preserve frame integrity.
- Link-down, reset, training and recovery state transitions are observable and safe.
- Statistics counters have defined widths, clear behavior and overflow semantics.

## DV checks

Cover normal frames, minimum and maximum sizes, malformed frames, CRC errors, backpressure, pauses, link transitions, reset during traffic and recovery. Keep packet-level evidence separate from lane/PHY-level evidence.
