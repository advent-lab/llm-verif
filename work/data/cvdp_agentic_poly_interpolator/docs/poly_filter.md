# Polyphase Filter Module

The `poly_filter` module performs the multiply-accumulate (MAC) operations required in a polyphase filter structure. It takes as inputs:
- A **sample buffer** (from a shift register) containing the history of input samples.
- A **phase selection** signal that determines which group of filter coefficients to use.
- A **valid_in** flag indicating that new input data is available.

The module operates in four main stages:

1. **Stage 0: Input Registration**  
   The incoming sample buffer and the phase signal are registered into internal registers (`sample_reg` and `phase_reg`). A valid flag (`valid_stage0`) is generated when the input data is valid.

2. **Stage 1: Coefficient Fetch**  
   For each tap, a coefficient is fetched from an instance of the **coeff_ram** module.

3. **Stage 2: Multiplication**  
   Each registered sample is multiplied by its corresponding coefficient to produce a set of products.

4. **Stage 3: Summation**  
   The products are summed using a pipelined **adder_tree** module. The output of the adder tree is a single sum representing the filtered result.

5. **Stage 4: Output Registration**  
   The final sum is registered and output along with a valid flag, indicating that the filter output is ready.

---

## Interface Table

| Signal Name     | Direction | Width                                                 | Description                                                         |
|-----------------|-----------|-------------------------------------------------------|---------------------------------------------------------------------|
| `clk`           | Input     | 1                                                     | Clock signal                                                        |
| `arst_n`        | Input     | 1                                                     | Active-low asynchronous reset                                       |
| `sample_buffer` | Input     | Array of `TAPS` elements, each `DATA_WIDTH` bits wide | Input sample history, from a shift register                         |
| `valid_in`      | Input     | 1                                                     | Valid flag for the sample_buffer.                                   |
| `phase`         | Input     | `$clog2(N)` bits                                      | Phase selection signal used to choose the correct coefficient group |
| `filter_out`    | Output    | `ACC_WIDTH`                                           | Final filter output                                                 |
| `valid`         | Output    | 1                                                     | Valid flag indicating that the output on `filter_out`               |


---

## Submodule Integration

### Coefficient RAM (coeff_ram)

- **Purpose:**  
  The **coeff_ram** module stores filter coefficients. In the poly_filter, a generate block named `coeff_fetch` instantiates one `coeff_ram` instance per tap.
  
- **Operation:**  
  For each tap (index `j`), the coefficient RAM is accessed with an address computed as:
  ```
  addr = phase_reg * TAPS + j
  ```
  This fetches the coefficient corresponding to the current phase and tap.
  
- **Integration:**  
  The output of each coefficient RAM instance is assigned to an array (`coeff[j]`), which is later used in the multiplication stage.

### Adder Tree (adder_tree)

- **Purpose:**  
  The **adder_tree** module sums an array of products obtained from multiplying the registered samples and the fetched coefficients.
  
- **Operation:**  
  The multiplication results are stored in the `products` array. The adder_tree uses a pipelined structure where the number of values is halved at each stage until a single summed value is produced.
  
- **Integration:**  
  The adder_tree is instantiated with the parameters:
  - `NUM_INPUTS = TAPS`
  - `DATA_WIDTH = DATA_WIDTH + COEFF_WIDTH`
  
  Its output is assigned to the final filter result (`sum_result`), and a valid flag (`valid_adder`) indicates when the summed result is valid.

---

## Detailed Operation Flow

1. **Stage 0 – Input Registration:**  
   - Registers each element of `sample_buffer` into `sample_reg`.
   - Registers the `phase` signal into `phase_reg`.
   - Generates `valid_stage0` if `valid_in` is high.

2. **Stage 1 – Coefficient Fetch:**  
   - For each tap `j`, calculates the coefficient address: `addr = phase_reg * TAPS + j`.
   - Instantiates `coeff_ram` to retrieve the coefficient at the computed address.
   - Outputs are stored in the `coeff` array.

3. **Stage 2 – Multiplication:**  
   - For each tap `j`, multiplies `sample_reg[j]` with `coeff[j]` to obtain `products[j]`.

4. **Stage 3 – Summation via Adder Tree:**  
   - The `products` array is input to the adder_tree module.
   - The adder_tree computes the sum of all products.
   - The final sum is available at `sum_result` and is accompanied by a valid signal (`valid_adder`).

5. **Stage 4 – Output Registration:**  
   - The `sum_result` is registered and assigned to `filter_out`.
   - The output valid flag `valid` is set based on `valid_adder`.