# AXI4 Guidance

Confirm the exact AXI family and version before applying this pack. AXI4, AXI4-Lite and AXI-Stream are not interchangeable.

## RTL checks

- VALID must not depend combinationally on READY in a way that creates a loop.
- Once VALID is asserted without READY, the payload and required sideband must remain stable.
- A transfer occurs only on the accepted handshake; no duplicate or lost transaction is allowed.
- Read and write channels must preserve the project's ordering and ID rules.
- Burst length, size, alignment, boundary and response semantics must be explicit.
- Backpressure must not corrupt state or leave a transaction permanently outstanding.
- Reset must clear or define all channel-visible state.

## DV checks

Cover single transfer, delayed READY, delayed VALID, simultaneous traffic, burst boundaries, outstanding IDs, response errors, reset during activity and recovery after backpressure.

## Evidence

The project profile supplies the actual VIP class, interface names, build command and simulator details. This pack supplies protocol reasoning, not project-specific library paths.
