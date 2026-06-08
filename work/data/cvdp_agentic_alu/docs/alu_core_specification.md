# ALU Core Specification Document

## Introduction

The **ALU Core** module implements a simple arithmetic and logic unit supporting basic operations such as addition, subtraction, multiplication, division, and bitwise logic functions. It operates on three signed operands of parameterized width (`DATA_WIDTH`) and determines the operation based on a 4-bit opcode.

---

## Module Interface

The module is defined as follows:

```verilog
module alu_core #(
    parameter DATA_WIDTH = 32
)(
    input  logic [3:0]                         opcode,
    input  logic signed [DATA_WIDTH-1:0]       operand1,
    input  logic signed [DATA_WIDTH-1:0]       operand2,
    input  logic signed [DATA_WIDTH-1:0]       operand3,
    output logic signed [DATA_WIDTH-1:0]       result
);
```

### Port Description

- **opcode:** 4-bit control signal that determines the operation performed.
- **operand1, operand2, operand3:** Signed input operands of `DATA_WIDTH` bits each.
- **result:** Signed output result of `DATA_WIDTH` bits.

---

## Supported Operations

The module supports the following arithmetic and logical operations based on the `opcode`:

| Opcode | Operation            | Description                                |
|--------|----------------------|--------------------------------------------|
| 0x0    | Addition             | `result = operand1 + operand2 + operand3`  |
| 0x1    | Subtraction          | `result = operand1 - operand2 - operand3`  |
| 0x2    | Multiplication       | `result = operand1 * operand2 * operand3`  |
| 0x3    | Division             | `result = operand1 / operand2 / operand3`  |
| 0x4    | Bitwise AND          | `result = operand1 & operand2 & operand3`  |
| 0x5    | Bitwise OR           | `result = operand1 | operand2 | operand3`  |
| 0x6    | Bitwise XOR          | `result = operand1 ^ operand2 ^ operand3`  |
| Other  | Default (Zero)       | `result = 0`                               |

---

## Internal Architecture

The **ALU Core** operates as a combinational unit where the computation is determined purely based on input values without any clock-driven state retention. The processing is handled through dedicated functions that perform different arithmetic and logical operations.

1. **Operand Handling:**  
   - The ALU takes three signed operands as inputs.
   - These operands are directly fed into the computational logic.

2. **Operation Selection:**  
   - A 4-bit opcode determines which arithmetic or logical operation will be performed.
   - The opcode is evaluated using a case structure, mapping each opcode to a specific function.

3. **Computation Execution:**  
   - For arithmetic operations (addition, subtraction, multiplication, and division), the three operands are processed according to their respective mathematical rules.
   - For bitwise operations (AND, OR, XOR), the computation is performed at the bit level.

4. **Result Assignment:**  
   - The computed value is assigned to the result output.
   - If the opcode does not match any predefined operation, the result defaults to zero.

5. **Considerations:**  
   - The module does not handle division by zero explicitly, which may result in undefined behavior.
   - The design does not store any past computation results since it is purely combinational.

By implementing this approach, the **ALU Core** ensures efficient and immediate computation of results based on the given inputs and control opcode.

---