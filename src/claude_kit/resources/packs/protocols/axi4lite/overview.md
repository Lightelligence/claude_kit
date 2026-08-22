# AXI4-Lite Guidance

Identify the data/address width, register side effects, supported response codes and whether the implementation permits multiple outstanding transactions.

## RTL checks

- Address, write data, write response, read address and read data channels are independently handshaken.
- A write response is produced exactly once after the required address/data acceptance, regardless of channel arrival order.
- Read data and response are stable while VALID is asserted and READY is low.
- Unsupported burst, lock, cache or QoS semantics are rejected or documented rather than silently accepted.
- Byte strobes, alignment, access permissions and reset values match the register contract.
- Backpressure and reset cannot duplicate, lose or reorder a register side effect.

## DV checks

Cover address-before-data and data-before-address writes, delayed READY on every channel, stalled responses, byte strobes, invalid addresses, read-only/write-only side effects, reset during a transfer and back-to-back accesses.
