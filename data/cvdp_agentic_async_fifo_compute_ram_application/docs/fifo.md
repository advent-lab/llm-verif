# Asynchronous FIFO Specification

## 1. Overview

The **async_fifo** design is a parameterizable asynchronous FIFO module. It uses separate clock domains for writing and reading, providing safe data transfer between two clock domains. The design employs dual-port memory and Gray-coded pointers for reliable synchronization.

### Key Features
1. Configurable data width and FIFO depth (determined by address width).
2. Separate write and read clocks.
3. Synchronization logic for pointers between clock domains.
4. Full and empty flags to indicate FIFO status.
5. Dual-port memory for simultaneous read and write.


## 2. Top-Level Module: `async_fifo`

### 2.1 Parameters

- **p_data_width** (default = 32)
  - Defines the width of data being transferred in/out of the FIFO.
- **p_addr_width** (default = 16)
  - Defines the width of the address pointers for the FIFO.
  - The FIFO depth will be \(2^{\text{p\_addr\_width}}\).

### 2.2 Ports

| **Port Name**       | **Direction** | **Width**                   | **Description**                                                         |
|---------------------|---------------|-----------------------------|-------------------------------------------------------------------------|
| `i_wr_clk`          | Input         | 1 bit                       | Write clock domain.                                                     |
| `i_wr_rst_n`        | Input         | 1 bit                       | Active-low reset signal for the write clock domain.                     |
| `i_wr_en`           | Input         | 1 bit                       | Write enable signal. When high and FIFO not full, data is written.      |
| `i_wr_data`         | Input         | `p_data_width` bits         | Write data to be stored in the FIFO.                                    |
| `o_fifo_full`       | Output        | 1 bit                       | High when FIFO is full and cannot accept more data.                     |
| `i_rd_clk`          | Input         | 1 bit                       | Read clock domain.                                                      |
| `i_rd_rst_n`        | Input         | 1 bit                       | Active-low reset signal for the read clock domain.                      |
| `i_rd_en`           | Input         | 1 bit                       | Read enable signal. When high and FIFO not empty, data is read out.     |
| `o_rd_data`         | Output        | `p_data_width` bits         | Read data from the FIFO.                                                |
| `o_fifo_empty`      | Output        | 1 bit                       | High when FIFO is empty and no data is available to read.               |

### 2.3 Internal Signals
- `w_wr_bin_addr` & `w_rd_bin_addr`
  - Binary write and read address buses.
- `w_wr_grey_addr` & `w_rd_grey_addr`
  - Gray-coded write and read address buses.
- `w_rd_ptr_sync` & `w_wr_ptr_sync`
  - Synchronized read pointer in the write domain and synchronized write pointer in the read domain, respectively.

### 2.4 Submodule Instantiations

#### 1. `read_to_write_pointer_sync`
Synchronizes the Gray-coded read pointer from the read clock domain to the write clock domain.

**Instantiation:**
```verilog
read_to_write_pointer_sync #(p_addr_width) read_to_write_pointer_sync_inst (
    .o_rd_ptr_sync  (w_rd_ptr_sync),
    .i_rd_grey_addr (w_rd_grey_addr),
    .i_wr_clk       (i_wr_clk),
    .i_wr_rst_n     (i_wr_rst_n)
);
```

#### 2. `write_to_read_pointer_sync`
Synchronizes the Gray-coded write pointer from the write clock domain to the read clock domain.

**Instantiation:**
```verilog
write_to_read_pointer_sync #(p_addr_width) write_to_read_pointer_sync_inst (
    .i_rd_clk       (i_rd_clk),
    .i_rd_rst_n     (i_rd_rst_n),
    .i_wr_grey_addr (w_wr_grey_addr),
    .o_wr_ptr_sync  (w_wr_ptr_sync)
);
```

#### 3. `wptr_full`
Handles the write pointer logic, updates the pointer upon valid writes, and detects FIFO full condition.

**Instantiation:**
```verilog
wptr_full #(p_addr_width) wptr_full_inst (
    .i_wr_clk       (i_wr_clk),
    .i_wr_rst_n     (i_wr_rst_n),
    .i_wr_en        (i_wr_en),
    .i_rd_ptr_sync  (w_rd_ptr_sync),
    .o_fifo_full    (o_fifo_full),
    .o_wr_bin_addr  (w_wr_bin_addr),
    .o_wr_grey_addr (w_wr_grey_addr)
);
```

#### 4. `fifo_memory`
Dual-port RAM used to store the FIFO data. Supports simultaneous write and read using separate clocks.

**Instantiation:**
```verilog
fifo_memory #(p_data_width, p_addr_width) fifo_memory_inst (
    .i_wr_clk       (i_wr_clk),
    .i_wr_clk_en    (i_wr_en),
    .i_wr_addr      (w_wr_bin_addr),
    .i_wr_data      (i_wr_data),
    .i_wr_full      (o_fifo_full),
    .i_rd_clk       (i_rd_clk),
    .i_rd_clk_en    (i_rd_en),
    .i_rd_addr      (w_rd_bin_addr),
    .o_rd_data      (o_rd_data)
);
```

#### 5. `rptr_empty`
Handles the read pointer logic, updates the pointer upon valid reads, and detects FIFO empty condition.

**Instantiation:**
```verilog
rptr_empty #(p_addr_width) rptr_empty_inst (
    .i_rd_clk       (i_rd_clk),
    .i_rd_rst_n     (i_rd_rst_n),
    .i_rd_en        (i_rd_en),
    .i_wr_ptr_sync  (w_wr_ptr_sync),
    .o_fifo_empty   (o_fifo_empty),
    .o_rd_bin_addr  (w_rd_bin_addr),
    .o_rd_grey_addr (w_rd_grey_addr)
);
```


## 3. Submodules

This section describes each submodule in detail.

---

### 3.1 `fifo_memory`

#### 3.1.1 Parameters

- **p_data_width** (default = 32)  
  Width of each data word stored in the memory.
- **p_addr_width** (default = 16)  
  Width of the memory address ports. The depth of the memory is \(2^{\text{p\_addr\_width}}\).

#### 3.1.2 Ports

| **Port Name** | **Direction** | **Width**           | **Description**                                               |
|---------------|---------------|---------------------|---------------------------------------------------------------|
| `i_wr_clk`    | Input         | 1 bit               | Write clock.                                                  |
| `i_wr_clk_en` | Input         | 1 bit               | Write clock enable; when high, a write operation may occur.   |
| `i_wr_addr`   | Input         | `p_addr_width` bits | Address in memory where data will be written.                 |
| `i_wr_data`   | Input         | `p_data_width` bits | Data to be stored in the memory.                              |
| `i_wr_full`   | Input         | 1 bit               | FIFO full indicator (used to block writes when FIFO is full). |
| `i_rd_clk`    | Input         | 1 bit               | Read clock.                                                   |
| `i_rd_clk_en` | Input         | 1 bit               | Read clock enable; when high, a read operation may occur.     |
| `i_rd_addr`   | Input         | `p_addr_width` bits | Address in memory from where data will be read.               |
| `o_rd_data`   | Output        | `p_data_width` bits | Output data read from the memory.                             |

#### 3.1.3 Functionality

- **Write Operation**:
  - Occurs on the rising edge of `i_wr_clk` when `i_wr_clk_en` is high and `i_wr_full` is low.
  - Data `i_wr_data` is stored at address `i_wr_addr`.
- **Read Operation**:
  - Occurs on the rising edge of `i_rd_clk` when `i_rd_clk_en` is high.
  - Data at address `i_rd_addr` is latched into an internal register and then driven onto `o_rd_data`.

### 3.2 `read_to_write_pointer_sync`

#### 3.2.1 Module Declaration

```verilog
module read_to_write_pointer_sync
    #(
        parameter p_addr_width = 16
    )(
        input  wire              i_wr_clk,
        input  wire              i_wr_rst_n,
        input  wire [p_addr_width:0] i_rd_grey_addr,
        output reg  [p_addr_width:0] o_rd_ptr_sync
    );
    ...
endmodule
```

#### 3.2.2 Parameters

- **p_addr_width** (default = 16)  
  Defines the address width (not counting the extra MSB bit used for indexing).

#### 3.2.3 Ports

| **Port Name** | **Direction** | **Width** | **Description** |
|--------------|--------------|----------|----------------|
| `i_wr_clk`   | Input        | 1 bit    | Write clock domain. |
| `i_wr_rst_n` | Input        | 1 bit    | Active-low reset for the write clock domain. |
| `i_rd_grey_addr` | Input    | `p_addr_width+1` bits | Gray-coded read pointer from the read clock domain. |
| `o_rd_ptr_sync`  | Output (reg) | `p_addr_width+1` bits | Synchronized read pointer in the write clock domain (two-stage synchronization). |

#### 3.2.4 Functionality

- **Synchronization**:
  - Synchronizes the `i_rd_grey_addr` from the read domain into the write domain using a two-stage flip-flop approach.
  - Ensures metastability containment and provides a stable version of the read pointer (`o_rd_ptr_sync`) in the write clock domain.

---

### 3.3 `write_to_read_pointer_sync`


#### 3.3.1 Parameters

- **p_addr_width** (default = 16)

#### 3.3.2 Ports

| **Port Name** | **Direction** | **Width** | **Description** |
|--------------|--------------|----------|----------------|
| `i_rd_clk`   | Input        | 1 bit    | Read clock domain. |
| `i_rd_rst_n` | Input        | 1 bit    | Active-low reset for the read clock domain. |
| `i_wr_grey_addr` | Input    | `p_addr_width+1` bits | Gray-coded write pointer from the write clock domain. |
| `o_wr_ptr_sync`  | Output (reg) | `p_addr_width+1` bits | Synchronized write pointer in the read clock domain (two-stage synchronization). |

#### 3.3.3 Functionality

- **Synchronization**:
  - Similar to `read_to_write_pointer_sync`, but in the opposite direction.
  - Takes the Gray-coded write pointer from the write clock domain, synchronizes it into the read clock domain via a two-stage flip-flop method, producing `o_wr_ptr_sync`.

### 3.4 `wptr_full`


#### 3.4.1 Parameters

- **p_addr_width** (default = 16)

#### 3.4.2 Ports

| **Port Name** | **Direction** | **Width** | **Description** |
|--------------|--------------|----------|----------------|
| `i_wr_clk`   | Input        | 1 bit    | Write clock. |
| `i_wr_rst_n` | Input        | 1 bit    | Active-low reset for the write clock domain. |
| `i_wr_en`    | Input        | 1 bit    | Write enable signal. |
| `i_rd_ptr_sync` | Input    | `p_addr_width+1` bits | Synchronized read pointer from the read clock domain (Gray-coded). |
| `o_fifo_full` | Output (reg) | 1 bit    | Indicates when the FIFO is full. |
| `o_wr_bin_addr` | Output (wire) | `p_addr_width` bits | Binary write address used for indexing the memory. |
| `o_wr_grey_addr` | Output (reg) | `p_addr_width+1` bits | Gray-coded write pointer. |

#### 3.4.3 Functionality

1. Maintains a **binary write pointer** (`r_wr_bin_addr_pointer`) that increments when `i_wr_en` is asserted and the FIFO is not full.
2. Generates a **Gray-coded write pointer** (`o_wr_grey_addr`) from the binary pointer.
3. Compares the next Gray-coded write pointer to the synchronized read pointer (`i_rd_ptr_sync`) to determine if the FIFO is full.
   - **Full condition**: The next Gray-coded write pointer matches the read pointer with the most significant bit(s) inverted (typical FIFO full logic).
4. Sets `o_fifo_full` accordingly.

---

### 3.5 `rptr_empty`

#### 3.5.1 Parameters

- **p_addr_width** (default = 16)

#### 3.5.2 Ports

| **Port Name** | **Direction** | **Width** | **Description** |
|--------------|--------------|----------|----------------|
| `i_rd_clk`   | Input        | 1 bit    | Read clock domain. |
| `i_rd_rst_n` | Input        | 1 bit    | Active-low reset for the read clock domain. |
| `i_rd_en`    | Input        | 1 bit    | Read enable signal. |
| `i_wr_ptr_sync` | Input    | `p_addr_width+1` bits | Synchronized write pointer from the write clock domain (Gray-coded). |
| `o_fifo_empty` | Output (reg) | 1 bit    | Indicates when the FIFO is empty. |
| `o_rd_bin_addr` | Output (wire) | `p_addr_width` bits | Binary read address used for indexing the memory. |
| `o_rd_grey_addr` | Output (reg) | `p_addr_width+1` bits | Gray-coded read pointer. |

#### 3.5.3 Functionality

1. Maintains a **binary read pointer** (`r_rd_bin_addr_pointer`) which increments when `i_rd_en` is asserted and the FIFO is not empty.
2. Generates a **Gray-coded read pointer** (`o_rd_grey_addr`) from the binary pointer.
3. Compares the next Gray-coded read pointer with the synchronized write pointer (`i_wr_ptr_sync`) to determine if the FIFO is empty.
   - **Empty condition**: The next Gray-coded read pointer equals the synchronized write pointer.
4. Sets `o_fifo_empty` accordingly.

## 4. Design Considerations

1. **Synchronization**  
   - The design uses two-stage flip-flop synchronizers (in `read_to_write_pointer_sync` and `write_to_read_pointer_sync`) to safely transfer Gray-coded pointers across clock domains.

2. **Gray Code**  
   - Gray-coding is used to ensure that only one bit changes at a time when incrementing the pointer, minimizing metastability issues in multi-bit signals across asynchronous boundaries.

3. **Full and Empty Detection**  
   - `wptr_full` checks if the next Gray-coded write pointer would “catch up” to the synchronized read pointer.
   - `rptr_empty` checks if the next Gray-coded read pointer equals the synchronized write pointer.

4. **Reset Handling**  
   - Both write and read sides have independent resets (`i_wr_rst_n` and `i_rd_rst_n`), which asynchronously reset the respective pointer logic and synchronizers.

5. **Clock Enable and Full/Empty Blocking**  
   - The `fifo_memory` write is gated by both `i_wr_clk_en` (tied to `i_wr_en`) and `i_wr_full`. The read is gated by `i_rd_clk_en` (tied to `i_rd_en`).

6. **Parameter Limits**  
   - `p_data_width` can be chosen based on the required data width (commonly 8, 16, 32, etc.).
   - `p_addr_width` determines the depth of the FIFO and should be sized to accommodate the desired maximum storage.
```