# UART Guidance

Record baud-rate generation, oversampling ratio, data width, parity, stop bits, break behavior and flow-control assumptions.

## RTL checks

- Start-bit detection and sampling point tolerate the specified clock/baud error.
- Data bit order, parity calculation and stop-bit validation are explicit.
- Framing, parity, break, overrun and noise errors are reported and cleared correctly.
- RX synchronizers and reset behavior prevent metastability from becoming protocol state.
- TX output remains stable between defined baud transitions.
- FIFO full/empty and flow-control behavior cannot silently drop bytes.

## DV checks

Cover legal configurations, baud error, jitter within the contract, parity modes, framing error, break, overrun, reset during a byte, back-to-back traffic and flow-control stalls.
