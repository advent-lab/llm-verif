# Custom Byte-Enable RAM Module

This module implements a dual-port RAM with byte-enable support and pipelining, designed for efficient memory operations in systems such as processors or embedded controllers. It features separate interfaces for two independent ports (Port A and Port B), each capable of partial writes at byte granularity. The design includes collision handling logic for simultaneous writes to the same memory location and registers inputs in a two-stage pipeline to ensure correct data propagation and controlled read latency.

---

## Parameterization

- **XLEN**:
  - Data width of the memory, typically set to 32 bits.

- **LINES**:
  - Number of 32-bit words in memory (default: 8192).
  - Address width derived as $clog2(LINES).

These parameters allow customization of the memory size and data width at compile time.

---

## Interfaces

### 1. Clock
- **clk**: Single posedge clock input synchronizing all operations.

### 2. Port A Interface
- **addr_a [ADDR_WIDTH-1:0]**: Address input for Port A.
- **en_a**: Enable signal for Port A; triggers write operations.
- **be_a [XLEN/8-1:0]**: Byte-enable vector controlling byte-level writes.
- **data_in_a [XLEN-1:0]**: 32-bit data input for Port A.
- **data_out_a [XLEN-1:0]**: Pipelined 32-bit data output from memory.

### 3. Port B Interface
- **addr_b [ADDR_WIDTH-1:0]**: Address input for Port B.
- **en_b**: Enable signal for Port B; triggers write operations.
- **be_b [XLEN/8-1:0]**: Byte-enable vector controlling byte-level writes.
- **data_in_b [XLEN-1:0]**: 32-bit data input for Port B.
- **data_out_b [XLEN-1:0]**: Pipelined 32-bit data output from memory.

---

## Internal Architecture

### 1. Memory Organization
The memory array is defined as:
logic [XLEN-1:0] ram [LINES-1:0];
Simplifies synthesis and supports word-level addressing.

### 2. Input Pipelining
**Stage-1 Registers**:
- Registers (`addr_a_reg`, `en_a_reg`, `be_a_reg`, `data_in_a_reg`, etc.) capture port inputs on each clock's rising edge, synchronizing subsequent operations.

### 3. Write Collision Handling (Stage-2)
**Collision Detection**:

if (en_a_reg && en_b_reg && (addr_a_reg == addr_b_reg))
Determines simultaneous writes to the same address.

**Byte-Level Arbitration**:
- If collision occurs, priority is:
  - **Port A's byte-enable active**: byte written from Port A.
  - **Port A's byte-enable inactive & Port B's active**: byte written from Port B.
- Ensures selective byte-level updates with Port A prioritized.

**Independent Writes**:
- Without collision, each port independently updates enabled bytes.

### 4. Pipelined Read Outputs
- Data outputs (`data_out_a`, `data_out_b`) reflect data from pipelined addresses, introducing one-cycle latency.

---

## Summary of Functionality

- **Dual-Port Operation**: Supports concurrent operations on two independent ports.
- **Byte-Enable Write**: Allows partial byte-level word updates via byte-enable mask.
- **Collision Handling**: Resolves simultaneous write collisions at byte granularity, prioritizing Port A.
- **Pipelined Operation**: Utilizes a two-stage pipeline (input capture and memory update/read), introducing one-cycle latency.
- **Initialization**: Memory initialized to zero at startup.

This `custom_byte_enable_ram` module is flexible and robust, suitable for a variety of high-performance digital system applications requiring dual-port memory access with precise byte-level control.