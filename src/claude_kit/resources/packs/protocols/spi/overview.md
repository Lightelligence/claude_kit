# SPI Guidance

Identify master/slave direction, CPOL/CPHA mode, word width, bit order, chip-select policy and whether the design supports full or half duplex.

## RTL checks

- Clock idle level, sampling edge and launch edge match the selected mode.
- Chip select setup, hold, inter-word gap and deassertion behavior are explicit.
- Bit count, first-bit ordering, word boundaries and last-bit handling are correct.
- MISO/MOSI ownership and tri-state behavior are safe when multiple slaves share a bus.
- Reset during a transfer cannot create a false completion or partial side effect.
- Clock-domain crossing and asynchronous input sampling are handled explicitly.

## DV checks

Cover all supported modes, word widths, back-to-back words, delayed response, chip-select glitches, reset during transfer, short/long transfers and invalid configuration. Check exact edge-level timing as well as transaction-level data.
