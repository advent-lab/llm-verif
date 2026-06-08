## Introduction

The `tb_dual_port_memory` testbench is designed to verify the functionality and robustness of a **dual-port memory module with ECC (Hamming code)**. The memory module features independent read and write ports (`addr_a`, `addr_b`) and ECC-based error detection. The testbench includes a diverse suite of test cases to simulate normal operations, boundary conditions, and fault injection scenarios.

---

## Purpose

This testbench aims to:

- Verify correctness of read/write memory operations.
- Validate ECC detection for single-bit errors in data and ECC.
- Simulate edge and corner cases across address and data space.
- Ensure reset functionality and proper FSM behavior.
- Confirm dual-port behavior including simultaneous access.

---

## DUT Interface

The `dual_port_memory` module has the following interface:

```verilog
module dual_port_memory #(
    parameter DATA_WIDTH = 4,
    parameter ECC_WIDTH = 3,
    parameter ADDR_WIDTH = 5,
    parameter MEM_DEPTH  = (1 << ADDR_WIDTH)
)(
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         we,
    input  logic [ADDR_WIDTH-1:0]        addr_a,
    input  logic [ADDR_WIDTH-1:0]        addr_b,
    input  logic [DATA_WIDTH-1:0]        data_in,
    output logic [DATA_WIDTH-1:0]        data_out,
    output logic                         ecc_error
);
```

---

## Testbench Features

| Feature                     | Description |
|----------------------------|-------------|
| Clock & Reset              | 10ns clock period with synchronous reset (`rst_n`) |
| Monitoring                 | `$monitor` tracks all key inputs/outputs |
| Logging                    | `$display` announces the start of each test |
| Pure Stimulus              | Procedural test cases only; no tasks/functions |
| Parameterization           | Inherits `DATA_WIDTH`, `ECC_WIDTH`, `ADDR_WIDTH` from DUT |
| Inline ECC Fault Injection | Direct bit flips in ECC/data memory arrays |

---

## Test Scenarios

| **Test #** | **Scenario Description**                                        |
|-----------:|------------------------------------------------------------------|
| 1          | Write and read same address                                      |
| 2          | Back-to-back writes and reads                                    |
| 3          | Read from previous address immediately after write               |
| 4          | Same data written to multiple addresses                          |
| 5          | ECC error from single-bit data corruption                        |
| 6          | ECC error from parity bit corruption                             |
| 7          | Min/max address boundary test                                    |
| 8          | Walking 1s data pattern                                          |
| 9          | Fill entire memory with zeros                                    |
| 10         | Corrupt ECC at every 4th address                                 |
| 11         | Simultaneous read/write to the same address                      |
| 12         | One-hot address testing                                          |
| 13         | Sequentially write all 4-bit data patterns (0–15)                |
| 14         | Feedback-based inversion write                                   |
| 15         | Manual read-modify-write simulation                              |
| 16         | Max corruption (invert data + ECC)                               |
| 17         | Flip each ECC bit independently                                  |
| 18         | Flip each data bit independently                                 |
| 19         | Toggle write to min and max address in rapid sequence            |
| 20–36      | Structured variations (even/odd writes, random patterns, etc.)   |
| 37–45      | Repeating write-read test sequences                              |

---

## Functional Coverage

| **Feature**                 | **Covered in Test(s)** |
|----------------------------|------------------------|
| Basic read/write           | 1, 2, 3                |
| ECC detection on read      | 5, 6, 10, 16–18        |
| Address boundary coverage  | 7, 12, 19              |
| Data pattern coverage      | 8, 13, 14              |
| Fault injection handling   | 5, 6, 10, 16–18        |
| Simultaneous access        | 3, 11, 19              |
| Full data bit toggle       | 13, 18                 |
| One-hot / wrap addresses   | 7, 12, 19              |
| Read-modify-write          | 15                     |
| Reset behavior             | Verified at init       |

---

## Reset Behavior

- `rst_n` (active-low) resets:
  - FSM state (to IDLE)
  - All control/data signals
  - Memory state (assumed initialized to 0)
  - `ecc_error` and `data_out` to 0

---

## Monitoring and Logging

The testbench uses:

```verilog
$monitor("%4t | clk=%b rst_n=%b we=%b addr_a=%0d addr_b=%0d data_in=%b | data_out=%b ecc_error=%b", ...);
$display("\n[Test #] <description>");
```