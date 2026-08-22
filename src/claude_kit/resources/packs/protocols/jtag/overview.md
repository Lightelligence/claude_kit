# JTAG Guidance

Identify TAP implementation scope, supported instructions, IR width, DR paths, IDCODE/BYPASS behavior and multi-device chain assumptions.

## RTL checks

- TMS/TCK transitions implement the complete TAP state machine.
- Capture, shift and update timing matches the selected edge semantics.
- IR capture pattern, instruction decode and reset-to-IDCODE/BYPASS behavior are defined.
- DR length and bit order are correct for every instruction.
- TDO is driven only in the intended shift states and is safe in other states.
- Test reset and system reset interactions do not leave stale instruction or data state.

## DV checks

Cover every TAP transition, reset by TMS and external reset, each instruction, capture/shift/update, BYPASS, IDCODE, invalid instruction and multi-device chain timing.
