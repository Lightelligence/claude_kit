# I2C Guidance

Identify address width, speed mode, master/slave role, repeated-start support, clock stretching and multi-master assumptions.

## RTL checks

- SDA and SCL use open-drain semantics; the design never drives a forbidden high.
- START, repeated START, STOP, ACK and NACK are sampled and generated on valid edges.
- Address, read/write direction, byte boundaries and ACK ownership are explicit.
- Clock stretching, arbitration loss, bus busy and stuck-low recovery are defined.
- Reset cannot create a false START, STOP or write side effect.
- Synchronizers and filtering for asynchronous pins are sized to the project timing contract.

## DV checks

Cover read, write, repeated START, NACK, clock stretch, arbitration loss, stuck bus, reset during transfer, invalid address and back-to-back transactions.
