# RGB to HSV Conversion Module Specification Document

## Introduction

The **RGB to HSV Conversion Module** is designed to convert RGB (Red, Green, Blue) color space values into HSV (Hue, Saturation, Value) color space values. This module is optimized for hardware implementation, leveraging pipelining and fixed-point arithmetic to achieve efficient and accurate conversion. The module supports 8-bit RGB input values and produces 12-bit Hue, 13-bit Saturation, and 12-bit Value outputs in fixed-point formats.


## Algorithm Overview

The conversion from RGB to HSV involves the following steps:

1. **Normalize RGB Values:**  
   The 8-bit RGB values are scaled to 12-bit fixed-point representation to maintain precision during calculations.

2. **Determine Maximum and Minimum Values:**  
   The maximum (`i_max`) and minimum (`i_min`) values among the R, G, and B components are identified. These values are used to calculate the delta (`delta_i`), which is the difference between `i_max` and `i_min`.

3. **Calculate Hue (H):**  
   The Hue value is calculated based on the maximum RGB component:
   - If the maximum component is **Red**, Hue is calculated using the formula:  
     `H = 60 * ((G - B) / delta)`
   - If the maximum component is **Green**, Hue is calculated using the formula:  
     `H = 60 * ((B - R) / delta) + 120`
   - If the maximum component is **Blue**, Hue is calculated using the formula:  
     `H = 60 * ((R - G) / delta) + 240`
   - If `delta_i` is zero, Hue is set to `0`.

4. **Calculate Saturation (S):**  
   Saturation is calculated using the formula:  
   `S = (delta / i_max)`

5. **Calculate Value (V):**  
   Value is simply the maximum RGB component:  
   `V = i_max`

The module uses precomputed inverse values of `i_max` and `delta_i` stored in memory to avoid division operations, replacing them with multiplications for efficiency.


## Module Interface

The module is defined as follows:

```verilog
module rgb_color_space_hsv (
    input               clk,
    input               rst,
    
    // Memory ports to initialize (1/delta) values
    input               we,
    input       [7:0]   waddr,
    input      [24:0]   wdata,
    
    // Input data with valid.
    input               valid_in,
    input       [7:0]   r_component,
    input       [7:0]   g_component,
    input       [7:0]   b_component,

    // Output values
    output reg [11:0]   h_component,  // Output in fx10.2 format, For actual degree value = (h_component)/4
    output reg [12:0]   s_component,  // Output in fx1.12 format. For actual % value = (s_component/4096)*100
    output reg [11:0]   v_component,  // For actual % value = (v_component/255) * 100
    output reg          valid_out
);
```

### Port Descriptions

- **clk:** Clock signal. All operations are synchronized to the positive edge of this signal.
- **rst:** Active-high asynchronous reset signal. When asserted, all internal registers and shift registers are initialized to their default values.
- **we:** Active-high write enable signal. Used to initialize the inverse values in the dual-port RAM.
- **waddr:** 8-bit write address signal. Specifies the memory location to be written during initialization.
- **wdata:** 25-bit write data signal. Contains the inverse values to be stored in the dual-port RAM during initialization.
- **valid_in:** Active-high input signal. Indicates that the input RGB data (`r_component`, `g_component`, `b_component`) is valid.
- **r_component:** 8-bit input signal. Represents the Red component of the RGB input.
- **g_component:** 8-bit input signal. Represents the Green component of the RGB input.
- **b_component:** 8-bit input signal. Represents the Blue component of the RGB input.
- **h_component:** 12-bit output signal. Represents the Hue value in fixed-point format (fx10.2). The degree value is obtained by dividing the decimal value by 4.
- **s_component:** 13-bit output signal. Represents the Saturation value in fixed-point format (fx1.12). The percentage value is obtained by multiplying the decimal value by 100 and dividing by 4096.
- **v_component:** 12-bit output signal. Represents the Value in percentage format. The percentage value is obtained by multiplying the decimal value by 100 and dividing by 255.
- **valid_out:** Active-high output signal. Indicates that the output data (`h_component`, `s_component`, `v_component`) is valid.

## Submodules

### 1. Dual-Port RAM
The dual-port RAM is used to store precomputed inverse values for `i_max` and `delta_i`. It supports one write port and two independent read ports.

#### Interface Ports:
- **clk:** Clock signal for synchronization.
- **we:** Active-high write enable signal.
- **waddr:** 8-bit write address for memory initialization.
- **wdata:** 25-bit write data for memory initialization.
- **ren_a:** Active-high read enable signal for port A.
- **raddr_a:** 8-bit read address for port A.
- **rdata_a:** 25-bit read data from port A.
- **ren_b:** Active-high read enable signal for port B.
- **raddr_b:** 8-bit read address for port B.
- **rdata_b:** 25-bit read data from port B.

### 2. Saturation Multiplier
The saturation multiplier performs fixed-point multiplication of the delta value with the inverse of `i_max` to calculate saturation.

#### Interface Ports:
- **clk:** Clock signal for synchronization.
- **rst:** Active-high reset signal.
- **a:** 25-bit multiplicand (inverse of `i_max`).
- **b:** 13-bit multiplier (delta value).
- **result:** 26-bit result of the multiplication, representing saturation.

The module computes the multiplication of a and b and the result is stored in a 39-bit intermediate register.
The result is **truncated** by selecting bits `[38:12]`, effectively discarding the lower 12 bits.
**Rounding is applied** by adding back the most significant bit of the discarded portion.

### 3. Hue Multiplier
The hue multiplier performs fixed-point multiplication of the precomputed hue value with the inverse of `delta_i` to calculate the hue value before doing hue addition.

#### Interface Ports:
- **clk:** Clock signal for synchronization.
- **rst:** Active-high reset signal.
- **dataa:** 19-bit signed multiplicand (precomputed hue value).
- **datab:** 25-bit multiplier (inverse of `delta_i`).
- **result:** 12-bit signed result of the multiplication, representing hue.

The `hue_mult` module multiplies dataa and datab and the result is **44-bit wide**.
This module selects bits `[33:22]`, effectively truncating the lower 22 bits.
**No explicit rounding is performed**

## Internal Architecture

The internal architecture is divided into several stages, each implemented using pipelined logic for efficient processing:

1. **Input Scaling and Max/Min Calculation:**  
   - The 8-bit RGB inputs are scaled to 12-bit fixed-point values.
   - The maximum (`i_max`) and minimum (`i_min`) values among the R, G, and B components are determined.
   - The delta (`delta_i`) is calculated as the difference between `i_max` and `i_min`.

2. **Memory Lookup for Inverse Values:**  
   - The inverse values of `i_max` and `delta_i` are fetched from the dual-port RAM. These values are precomputed and stored to avoid division operations.

3. **Hue Calculation:**  
   - The Hue value is calculated based on the maximum RGB component using precomputed inverse values and fixed-point arithmetic.
   - The result is adjusted based on the maximum component (Red, Green, or Blue) and normalized to the range [0, 360].

4. **Saturation Calculation:**  
   - Saturation is calculated using the formula `S = (delta / i_max)`, implemented using fixed-point multiplication with the pre-computed inverse of `i_max`.

5. **Value Calculation:**  
   - Value is the maximum RGB component, scaled to the output format.

6. **Output Pipeline:**  
   - The calculated Hue, Saturation, and Value are passed through a pipeline to ensure proper timing and synchronization.
   - The `valid_out` signal is asserted when the output data is ready.


## Timing and Latency

The design is fully pipelined, with a total latency of **8 clock cycles** from the assertion of `valid_in` to the assertion of `valid_out`. Each computational step within the module has a specific processing time, but because the design is **pipelined**, different portions of the input data progress through distinct stages concurrently. 

1. **Subtraction (1 cycle)**  
   - The first stage computes the differences required for Hue calculation: `(G - B)`, `(B - R)`, and `(R - G)`.  
   - These values are passed forward to later stages while new input data enters the pipeline.  

2. **Max/Min Value Calculation (2 cycles)**  
   - The second stage determines the **maximum (`i_max`)** and **minimum (`i_min`)** values among `R`, `G`, and `B`.  

3. **Determine the Maximum Component and Compute Delta (3 cycles)**  
   - This stage identifies which component (`R`, `G`, or `B`) contributed to `i_max`.  
   - It also calculates **delta (`delta_i`)**, which is the difference between `i_max` and `i_min`.  

4. **Memory Lookup for Inverse Values (4 cycles from `valid_in`)**  
   - The inverse values of `i_max` and `delta_i` are retrieved from a precomputed lookup table.  
   - Memory access itself takes **1 cycle**, but the lookup results become available at different times:
     - The **inverse of `i_max`** is available **3 cycles after `valid_in`**.
     - The **inverse of `delta_i`** is available **4 cycles after `valid_in`**.  

5. **Saturation Calculation (6 cycles from `valid_in`)**  
   - Once `delta_i` and `i_max` are available, the saturation computation is performed using **fixed-point multiplication**.  
   - The **inverse of `i_max`** and `delta_i` become available after 3 cycles. The multiplication takes an additional **3 cycles** for computation and rounding.  
   - The computed saturation value is stored in the pipeline and remains until **valid_out** is asserted at cycle 8.  

6. **Hue Calculation (8 cycles from `valid_in`)**  
   - The hue calculation involves two key computations:
     1. **Precomputed Hue Calculation (`5 cycles`)**  
        - The **subtracted value** used in Hue calculation (`G - B`, `B - R`, or `R - G`) is available **1 cycle after `valid_in`**.  
        - Identifying which component contributed to `i_max` takes **3 cycles**, so the appropriate subtracted value is selected by cycle **4**.  
        - An additional **1 cycle** is required to multiply this value by **60**, making the **precomputed hue** available by cycle **5**.  
     2. **Final Hue Computation (`3 additional cycles`)**  
        - The **inverse of `delta_i`** is available at **cycle 4**.  
        - The **hue multiplication module** receives `precomputed hue` (cycle 5) and `inverse of delta` (cycle 4) and performs the multiplication, which takes **2 cycles**.  
        - An additional **1 cycle** is required to add the **hue offset** (0, 120, or 240 degrees based on `i_max`).  
        - The final **Hue (`h_component`) is available at cycle 8**, aligning with `valid_out`.  

7. **Value Calculation (2 cycles from `valid_in`)**  
   - The **Value (`V`) component** is simply assigned the maximum input (`i_max`).  
   - Since `i_max` is computed early in the pipeline, `v_component` is ready **by cycle 2** but remains in the pipeline until all outputs are valid.  



## Memory Initialization

The dual-port RAM stores precomputed inverse values for `i_max` and `delta_i`. These values are initialized using the `we`, `waddr`, and `wdata` signals. The memory is organized as follows:
- **Address Range:** 0 to 255 (8-bit address).
- **Data Width:** 25 bits (fixed-point representation of inverse values).


## Fixed-Point Formats

- **Hue (h_component):**  
  - Format: fx10.2 (10 integer bits, 2 fractional bits).
  - Range: 0 to 360 degrees (scaled by a factor of 4).

- **Saturation (s_component):**  
  - Format: fx1.12 (1 integer bit, 12 fractional bits).
  - Range: 0% to 100% (scaled by a factor of 4096).

- **Value (v_component):**  
  - Format: 12-bit decimal.
  - Range: 0% to 100% (scaled by a factor of 255).


## Precision and Error Tolerance

The module is designed to maintain the following error tolerances:
- **Hue:** ±0.25 degree.
- **Saturation:** ±0.25%.
- **Value:** ±0.25%.

These tolerances account for precision loss during fixed-point arithmetic and rounding operations.

## Input constraints
- Assume that new inputs are provided to the design only after `valid_out` is asserted indication all outputs are valid.