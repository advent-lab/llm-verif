# ttc_counter_lite Specification Document

## Introduction

The **ttc_counter_lite** module implements a lightweight, programmable timer with support for **interval and single-shot counting modes**. It includes a 16-bit up-counter, configurable match and reload registers, a programmable prescaler, and an interrupt generation mechanism. The module is controlled through a **simple AXI-like register interface**.

This timer is useful for general-purpose timing operations, including periodic interrupts, timeouts, and system heartbeats.

---

## Functional Overview

The timer counts system clock cycles and generates an interrupt when the count value matches a programmable `match_value`. Optionally, in **interval mode**, the counter reloads a pre-programmed `reload_value` and continues counting.

Key features include:

- Start/stop control via `enable` bit.
- **Prescaler** to divide the input clock.
- **Interrupt output** that asserts when a match occurs.
- **Register interface** for runtime configuration and monitoring.

---

## Example Operation

1. Set `match_value` to 1000.
2. Set `reload_value` to 500.
3. Set `prescaler` to 3 (divide-by-4 behavior).
4. Enable **interval mode** and **interrupt** via the `control` register.
5. When `count` reaches 1000, an interrupt is generated and the counter resets to 500.

---

## Module Interface

```verilog
module ttc_counter_lite (
    input wire         clk,
    input wire         reset,
    input wire [3:0]   axi_addr,
    input wire [31:0]  axi_wdata,
    input wire         axi_write_en,
    input wire         axi_read_en,
    output reg [31:0]  axi_rdata,
    output reg         interrupt
);
```
## Port Description

| Port Name     | Direction | Width   | Description                                |
|---------------|-----------|---------|--------------------------------------------|
| `clk`         | Input     | 1 bit   | System clock                               |
| `reset`       | Input     | 1 bit   | Active-high synchronous reset              |
| `axi_addr`    | Input     | 4 bits  | Address input for read/write access        |
| `axi_wdata`   | Input     | 32 bits | Data to be written to register             |
| `axi_write_en`| Input     | 1 bit   | Write enable signal                        |
| `axi_read_en` | Input     | 1 bit   | Read enable signal                         |
| `axi_rdata`   | Output    | 32 bits | Data read from selected register           |
| `interrupt`   | Output    | 1 bit   | Asserted when count reaches match_value    |

---

## Register Map

| Address | Name           | Access | Description                                        |
|---------|----------------|--------|----------------------------------------------------|
| `0x0`   | COUNT          | R      | Current value of the 16-bit counter                |
| `0x1`   | MATCH_VALUE    | R/W    | Target value at which the timer will trigger       |
| `0x2`   | RELOAD_VALUE   | R/W    | Reload value when in interval mode                 |
| `0x3`   | CONTROL        | R/W    | Timer control: enable, mode, interrupt enable      |
| `0x4`   | STATUS         | R/W    | Interrupt status; write to clear                   |
| `0x5`   | PRESCALER      | R/W    | Prescaler value for input clock division (4 bits)  |

---

## Control Register Description

Bits `[2:0]` of the `CONTROL` register define timer behavior:

| Bit Index | Field Name        | Description                              |
|-----------|-------------------|------------------------------------------|
| 0         | `enable`          | Starts the counter when set              |
| 1         | `interval_mode`   | Enables automatic reloading              |
| 2         | `interrupt_enable`| Enables interrupt output on match        |

---

## Internal Architecture

### Counter Unit
A 16-bit register that increments on each prescaler pulse. If `interval_mode` is enabled and a match occurs, it reloads from `reload_value`.

### Prescaler Logic
Divides the input clock by `(prescaler + 1)` to control the counting frequency.

### Interrupt Generator
When the counter matches `match_value` and `interrupt_enable` is asserted, the `interrupt` output is driven high.

### AXI-Like Register Access
Supports independent read and write paths. Registers are accessed through the `axi_addr` interface.

---

## Timing and Latency

- Counter increments based on prescaler frequency.
- Interrupt is asserted within **1 clock cycle** after `count == match_value`.
- In **interval mode**, counter reloads and continues counting after match.
- All register **reads/writes are handled in 1 clock cycle**.

---