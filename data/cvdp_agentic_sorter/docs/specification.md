# Sorting Engine Specification Document

## Introduction

The **Sorting Engine** should implement an **8-element parallel merge sort** algorithm. This module is designed to sort 8 inputs of configurable bit-width (parameterized by `WIDTH`) in ascending order (lowest value at LSB and highest at MSB). The design must leverage the parallelism inherent in the merge sort algorithm by dividing the sort process into multiple stages. Each stage performs compare–swap and merging operations in a pipelined finite state machine (FSM) manner.

---

## Algorithm Overview

**Merge Sort** is a well-known divide-and-conquer sorting algorithm. The basic idea is to divide the unsorted list into smaller sub-lists, sort each sub-list, and then merge them to produce a sorted list. The parallel merge sort algorithm to be implemented in this module works as follows:

1. **Pair Sorting:**  
   The input array is divided into 4 pairs. Each pair is independently sorted using a compare–swap operation. This is the step where parallel operation happens for all pairs.

2. **Merge Sorted Pairs:**  
   Two consecutive sorted pairs are merged sequentially into a 4-element sorted group. This is done for both halves of the array, the first 4 pairs of elements and the last 4 elements.

3. **Final Merge:**  
   The two 4-element groups are merged to produce the final sorted 8-element array.

### Example

Consider the input array (from lowest index to highest):

```
[8, 7, 6, 5, 4, 3, 2, 1]
```

**Stage 1 – Pair Sorting:**  
- Pairs are sorted:  
  - Compare 8 and 7 → [7, 8]  
  - Compare 6 and 5 → [5, 6]  
  - Compare 4 and 3 → [3, 4]  
  - Compare 2 and 1 → [1, 2]

**Stage 2 – Merge Sorted Pairs:**  
- Merge the first two pairs: [7, 8] and [5, 6] → [5, 6, 7, 8]  
- Merge the next two pairs: [3, 4] and [1, 2] → [1, 2, 3, 4]

**Stage 3 – Final Merge:**  
- Merge the two 4-element groups: [5, 6, 7, 8] and [1, 2, 3, 4] → [1, 2, 3, 4, 5, 6, 7, 8]

The final output is the sorted list in ascending order.

---

## Module Interface

The module should be defined as follows:

```verilog
module sorting_engine #(parameter WIDTH = 8)(
    input                     clk,
    input                     rst,
    input                     start,  
    input  [8*WIDTH-1:0]      in_data,
    output reg                done,   
    output reg [8*WIDTH-1:0]  out_data
);
```

### Port Description

- **clk:** Clock signal.
- **rst:** Active-high asynchronous reset to set the outputs to 0.
- **start:** Active-high signal to initiate the sort operation. High for 1 clock cycle.
- **in_data:** Flat input bus representing 8 data elements, each `WIDTH` bits wide.
- **done:** Active-high signal indicating the completion of the sort operation. High for 1 clock cycle after sorting completes.
- **out_data:** Flat output bus containing the sorted data. Updated along with done signal and remains stable until data from next sorting operation is updated.

---

## Internal Architecture

The internal architecture must be organized into several stages controlled by an FSM:

1. **Data Loading:**  
   The flat `in_data` vector should be unpacked into an internal array.

2. **Stage 1 – Pair Compare–Swap:**  
   Four pairs of data must be compared and swapped in parallel if necessary. The sorted pairs should be stored for subsequent merging.

3. **Stage 2 – Merging Sorted Pairs:**  
   Two merge operations to be performed sequentially:
   - The first merge combines pairs `[0,1]` with `[2,3]` into a sorted 4-element group.
   - The second merge combines pairs `[4,5]` with `[6,7]` into another sorted 4-element group.

4. **Stage 3 – Final Merge:**  
   The two 4-element groups should be merged to produce the final sorted array.

The design should utilize sequential merging with pointer and counter logic, allowing the design to be pipelined and easily scalable for production.

---

## Timing and Latency

The design should be fully synchronous with a pipelined FSM. The expected latency from asserting the start signal to asserting the done signal is **20 clock cycles**. This includes:
- A few cycles for data loading.
- Cycles dedicated to the pair sorting and merging stages.
- Final packaging of the sorted output into the flat bus.