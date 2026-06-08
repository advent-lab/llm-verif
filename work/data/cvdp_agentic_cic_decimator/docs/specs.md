# CIC Decimator Module Analysis

This module implements a Cascaded Integrator-Comb (CIC) decimation filter. CIC filters are widely used in digital signal processing for decimating high-rate input signals without multipliers. The design comprises two main sections: a chain of integrator stages and a chain of comb (differentiator) stages, with decimation control to reduce the effective output rate.

---

## Parameterization

- **WIDTH:** Bit-width of the input data - 16
- **RMAX:** Maximum decimation factor - 2
- **M:** Differential delay in the comb section - 1
- **N:** Number of integrator and comb stages - 2
- **REG_WIDTH:** Internal register width calculated as: WIDTH + $clog2((RMAX * M)**N)


This ensures that the register width is sufficient to avoid overflow during accumulation.

---

## Interfaces

### Clock and Reset

- **clk:** Clock signal for synchronous operations.
- **rst:** Active-high reset signal.

### Data and Handshaking

- **Input Side:**
- `input_tdata` (WIDTH bits): The input sample.
- `input_tvalid`: Indicates when the input sample is valid.
- `input_tready`: Asserted when the module is ready to accept a new input sample.

- **Output Side:**
- `output_tdata` (REG_WIDTH bits): The decimated and filtered output sample.
- `output_tvalid`: Indicates that the output sample is valid.
- `output_tready`: Handshake signal from the downstream module indicating readiness to accept data.

### Decimation Rate Control

- **rate:** A control signal (bit-width derived from `RMAX`) that determines the decimation factor by specifying how many input samples to process before producing an output.

---

## Detailed Functionality

### 1. Integrator Section

- **Structure:**  
The module uses a generate loop to create `N` integrator stages. Each stage accumulates values from either the input or the previous integrator stage.

- **Operation:**  
- **Stage 0:** Adds the incoming `input_tdata` to its current accumulated value.
- **Subsequent Stages (k > 0):** Each stage adds the output from the previous integrator stage to its current accumulated value.

- **Clocking:**  
The accumulators update on the positive edge of `clk` when both `input_tready` and `input_tvalid` are asserted.

- **Purpose:**  
The integrators sum the incoming samples, a process essential to achieving the low-pass filtering characteristic prior to decimation.

---

### 2. Comb Section

- **Structure:**  
Similar to the integrator section, a generate loop creates `N` comb stages. Each stage includes an array of `M` delay registers (`delay_reg`) to implement the required delay.

- **Operation:**  
- **Input Source:**  
  - For the first comb stage (`k == 0`), the input is the output from the last integrator stage.
  - For subsequent stages, the input is the output of the previous comb stage.
- **Differentiation:**  
  Each stage computes the difference between the current input (stored in `delay_reg[0]`) and the delayed version (`delay_reg[M-1]`).
- **Delay Line Update:**  
  The delay registers shift their values each clock cycle to provide the required delay.

- **Clocking:**  
Comb stages update on the positive edge of `clk` when `output_tready` and `output_tvalid` are asserted.

- **Purpose:**  
The comb stages effectively differentiate the integrated signal to remove unwanted low-frequency components, compensating for the droop introduced by the integrators.

---

### 3. Decimation Control

- **Cycle Counter (`cycle_reg`):**  
- The counter increments with each valid input cycle.
- It increments until it reaches the smaller of `(RMAX - 1)` or `(rate - 1)`.
- Once the counter reaches the specified limit, it resets to zero.

- **Impact on Handshaking:**  
- **Output Validity:**  
  `output_tvalid` is asserted only when `input_tvalid` is high and the `cycle_reg` is zero (indicating the decimation point).
- **Input Readiness:**  
  `input_tready` is driven by `output_tready` or when the cycle counter is not zero, ensuring continuous accumulation in the integrators.

- **Purpose:**  
This counter effectively controls the decimation process by determining when an output sample is produced, thereby reducing the output sample rate relative to the input sample rate.

---

## Summary

- **CIC Filter Composition:**  
The design features cascaded integrator and comb stages. Integrators sum the incoming samples while comb stages subtract delayed versions of the signal to differentiate it.

- **Decimation Process:**  
A cycle counter (`cycle_reg`) manages the decimation by ensuring that output samples are generated only after a predetermined number of input samples (defined by the `rate` parameter) have been processed.

- **Parameter Flexibility:**  
The module is highly parameterizable (via `WIDTH`, `RMAX`, `M`, and `N`), making it adaptable to a wide range of decimation and filtering applications in digital down-conversion and oversampled signal processing.

This analysis provides a comprehensive overview of both the architecture and the functionality of the CIC decimator module.