# APB Guidance

## RTL checks

- A transfer has a setup phase followed by an access phase.
- Select, address, direction, write data and control fields remain stable through the access phase.
- The transfer completes only when the completion signal is asserted.
- Wait states do not create repeated side effects.
- Error response, reset during a transfer and unmapped address behavior are defined.
- Address width, alignment, byte strobes and register side effects match the project map.

## DV checks

Cover read, write, wait-state, error, back-to-back, reset and illegal/unmapped accesses. Check that side effects occur once and that response timing is bounded by the project contract.

The project profile supplies the actual APB interface, VIP and register-map adapter.
