# CAN Protocol Controller

**Source:** https://github.com/freecores/can
**Author:** Igor Mohor (igorm@opencores.org)

## Overview

A Verilog implementation of a CAN (Controller Area Network) protocol controller compatible with the CAN 2.0B specification. The core supports both Basic and Extended frame formats and has been validated against the Bosch VHDL Reference Model.

## Top-Level Module

`can_top` — top-level wrapper exposing a Wishbone slave interface, CAN bus I/O (`rx_i`, `tx_o`), interrupt output, and clock/reset signals.

## Submodules

- **can_registers** — Wishbone-accessible register file (mode, timing, error counters, acceptance filter, interrupt enable/status, TX/RX data)
- **can_btl** — Bit Timing Logic: synchronization, sample point control, baud rate generation
- **can_bsp** — Bit Stream Processor: CAN frame encoding/decoding, arbitration, error detection and handling, error counters, bus-off recovery
- **can_acf** — Acceptance Code Filter: single/dual filter support for standard and extended frames
- **can_fifo** — Receive FIFO: stores received frames for host readback
- **can_crc** — CRC-15 generator/checker for CAN frame integrity
- **can_ibo** — Input Buffer Override: mux between filtered bus input and loopback
- **can_register**, **can_register_asyn**, **can_register_syn**, **can_register_asyn_syn** — Register primitives with synchronous/asynchronous reset variants

## Key Features

- CAN 2.0B compliant (standard 11-bit and extended 29-bit identifiers)
- Wishbone bus interface
- Programmable baud rate via bit timing registers
- Dual acceptance filter with mask support
- Receive FIFO with overrun detection
- Error counters with bus-off and error-warning interrupt generation
- Self-test (loopback) mode
