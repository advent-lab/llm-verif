# **Specification Document: 8-bit LFSR with Configurable Feedback, Direction, and Weighted Logic**

## **1. Introduction**
This document describes the design and implementation of a **8-bit Linear Feedback Shift Register (LFSR)** using the **Galois configuration** with support for:
- **Configurable feedback logic** (NOR/NAND)
- **Directional control** (LSB to MSB or MSB to LSB)
- **Weighted feedback logic** to introduce bias in pseudo-random patterns

The module is implemented in **SystemVerilog** and generates pseudo-random sequences based on the **primitive polynomial**:

\[
x^{8} + x^6 + x^5 + x + 1
\]

## **2. Design Specifications**

### **2.1 Inputs**
| **Signal**  | **Width** | **Description**                                                                                                             |
|-------------|-----------|-----------------------------------------------------------------------------------------------------------------------------|
| `clock`     | 1-bit     | Clock signal driving the synchronous operation at the positive edge.                                                        |
| `reset`     | 1-bit     | Active-low reset signal to initialize the LFSR state.                                                                       |
| `lfsr_seed` | 8-bit    | Initial seed value to set the starting state of the LFSR.                                                                   |
| `sel`       | 1-bit     | Selector input for choosing NAND or NOR-based feedback logic:<br>• `0` → NOR feedback<br>• `1` → NAND feedback              |
| `dir`       | 1-bit     | Direction control input to determine the shift direction:<br>• `0` → Shift from LSB to MSB<br>• `1` → Shift from MSB to LSB |
| `weight`    | 3-bit     | Weight control signal to apply biased pseudo-random logic.                                                                  |

### **2.2 Outputs**
| **Signal** | **Width** | **Description**                                              |
|------------|-----------|--------------------------------------------------------------|
| `lfsr_new` | 8-bit    | Updated LFSR output after applying feedback and shift logic. |

---

## **3. Functional Description**
During each clock cycle, the **8-bit LFSR** performs the following operations:

1. **Feedback Calculation:**
   - Uses the primitive polynomial **x⁶ + x⁵ + x + 1** to compute the feedback bit.
   - The feedback is modified based on the `sel` input (`NOR` or `NAND`).

2. **Shift Logic:**
   - The LFSR shifts in the **LSB-to-MSB** or **MSB-to-LSB** direction based on `dir`.

3. **Weighted Logic:**
   - The `weight` input controls how many bits of the LFSR output undergo feedback logic.
   - Weight values range from `4'b0000` (no modification) to `4'b1111` (all bits modified).

---

## **4. Algorithm**
### **4.1 LSB to MSB, NOR Logic (sel = 0, dir = 0)**
- If `weight = 3'b000`, no changes are applied.
- If `weight > 3'b000`, apply **NOR** logic incrementally:
  - Example: `weight = 3'b001` applies NOR to `lfsr_out[0]` only.
  - `weight = 3'b111` applies NOR to `lfsr_out[7:0]`.

### **4.2 LSB to MSB, NAND Logic (sel = 1, dir = 0)**
- Similar to NOR logic, but **NAND** replaces NOR.
- Example: `weight = 3'b010` applies NAND to `lfsr_out[1:0]`.

### **4.3 MSB to LSB, NOR Logic (sel = 0, dir = 1)**
- Reverse the shift direction.
- Example: `weight = 3'b100` applies NOR to `lfsr_out[7:4]`.

### **4.4 MSB to LSB, NAND Logic (sel = 1, dir = 1)**
- Reverse direction while applying **NAND-based** feedback.

---

## **5. Sequential Logic for LFSR Update**
- The final computed **output (lfsr_new)** updates the **LFSR state**.
- Controlled using `always_ff` block triggered on **posedge clock** or **negedge reset**.

---

## **6. Summary**
| **Feature**         | **Support**                           |
|---------------------|---------------------------------------|
| LFSR Configuration  | 8-bit, Galois                        |
| Feedback Polynomial | `x^8 + x^6 + x^5 + x + 1`            |
| Feedback Logic      | NOR / NAND                            |
| Shift Direction     | LSB-to-MSB / MSB-to-LSB               |
| Weighted Logic      | Configurable via 3-bit `weight` input |

This design ensures flexibility in pseudo-random sequence generation, making it suitable for **built-in self-test (BIST), encryption, and signal processing applications**.

---

## **7. Future Enhancements**
1. **Configurable Polynomial:** Allow dynamic selection of the polynomial.
2. **Variable Bit Width:** Extend support for different LFSR lengths.
3. **Multiple Biasing Schemes:** Introduce additional weight-based randomization methods.

---

## **8. Conclusion**
The **8-bit LFSR module** is designed to provide **configurable feedback logic, direction control, and weighted biasing**, enabling a flexible and robust pseudo-random pattern generator.
