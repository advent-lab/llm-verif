# Multiplexer Specification Document

## Introduction

The **Multiplexer** module is a configurable data selector that chooses one of the multiple input data lines based on a selection signal. It supports configurable data width, input count, optional registered output, and default output handling when an invalid selection is made.

---

## Functional Overview

The multiplexer operates based on the following conditions:

1. **Selection Logic:**  
   - The `sel` input selects one of the `NUM_INPUTS` input data lines.
   - If `HAS_DEFAULT` is enabled and `sel` is out of range, the output is set to `DEFAULT_VALUE`.

2. **Bypass Mode:**  
   - If the `bypass` signal is active, the multiplexer forces `out` to always select `inp_array[0]`, regardless of the `sel` value.

3. **Registering Output:**  
   - If `REGISTER_OUTPUT` is enabled, the output data is registered using `clk` and `rst_n`.
   - If `REGISTER_OUTPUT` is disabled, the output is purely combinational.

---

## Module Interface

The multiplexer module should be defined as follows:

```verilog
module multiplexer #( 
    parameter DATA_WIDTH = 8,
    parameter NUM_INPUTS = 4,
    parameter REGISTER_OUTPUT = 0,
    parameter HAS_DEFAULT = 0,
    parameter [DATA_WIDTH-1:0] DEFAULT_VALUE = {DATA_WIDTH{1'b0}}
)(
    input  wire clk,
    input  wire rst_n,
    input  wire [(DATA_WIDTH*NUM_INPUTS)-1:0] inp,
    input  wire [$clog2(NUM_INPUTS)-1:0]       sel,
    input  wire bypass,
    output reg  [DATA_WIDTH-1:0] out
);
```

### Port Description

- **clk:** Clock signal (used when REGISTER_OUTPUT is enabled).
- **rst_n:** Active-low asynchronous reset (used when REGISTER_OUTPUT is enabled).
- **inp:** A flat input bus containing `NUM_INPUTS` data values, each `DATA_WIDTH` bits wide.
- **sel:** Select signal used to choose one of the input data lines.
- **bypass:** If active, forces the output to always be `inp_array[0]`.
- **out:** Selected output data.

---

## Internal Architecture

The multiplexer consists of the following key components:

1. **Input Data Array Construction:**  
   - The flat `inp` vector is split into an internal array using `generate` blocks.

2. **Selection Logic:**  
   - If `HAS_DEFAULT` is enabled and `sel` is out of range, output `DEFAULT_VALUE` is used.
   - Otherwise, the selected data input is assigned to the output.

3. **Bypass Logic:**  
   - If `bypass` is asserted, the multiplexer always selects `inp_array[0]`.

4. **Output Registering (if enabled):**  
   - If `REGISTER_OUTPUT` is set, the output is latched on the rising edge of `clk`.
   - If `rst_n` is de-asserted, `out` resets to zero.

---

## Timing and Latency

The multiplexer is a combinational circuit when `REGISTER_OUTPUT` is disabled, providing zero-cycle latency. However, if `REGISTER_OUTPUT` is enabled, the output will be available after **one clock cycle** due to register delay.

---

## Configuration Options

- **DATA_WIDTH**: Configurable width of the input data.
- **NUM_INPUTS**: Number of selectable inputs.
- **REGISTER_OUTPUT**: Enables synchronous output register.
- **HAS_DEFAULT**: Provides a default value when selection is out of range.
- **DEFAULT_VALUE**: Defines the default output when `HAS_DEFAULT` is enabled.

This flexible multiplexer module allows dynamic selection of input signals while offering configurable features for different system requirements.