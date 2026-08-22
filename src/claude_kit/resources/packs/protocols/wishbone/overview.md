# Wishbone Guidance

Identify the B4 mode, data/address width, classic or pipelined cycle type, registered feedback assumptions, tags and endianness before applying this pack.

## RTL checks

- CYC, STB, WE, address, data and select signals remain valid for the documented cycle phase.
- ACK, STALL, ERR and RTY are mutually understood and terminate or hold a request exactly once.
- Classic and pipelined cycles do not mix response timing or outstanding request accounting.
- Byte select, endian mapping, address increment and burst/lock conventions are explicit.
- Reset terminates an active cycle without creating a phantom acknowledge or write side effect.
- Master and slave cannot deadlock when STALL is asserted or a response is delayed.

## DV checks

Cover reads, writes, wait states, back-to-back and pipelined transfers, byte enables, error/retry responses, reset mid-cycle, illegal control combinations and maximum outstanding traffic.
