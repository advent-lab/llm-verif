# JPEG Decoder Core

**Source:** https://github.com/ultraembedded/core_jpeg
**License:** Apache 2.0

## Overview

A synthesizable Verilog 2001 baseline JPEG decoder core. It accepts a raw JPEG byte stream over a 32-bit AXI-Stream-like input port and produces decoded 24-bit RGB pixels one at a time on an output port. The core handles all stages of JPEG baseline decoding internally: header/table parsing, Huffman entropy decoding, dequantization, inverse DCT, and YCbCr-to-RGB color conversion. It supports Monochrome, YCbCr 4:4:4, and YCbCr 4:2:0 chroma subsampling.

## Top-Level Module

`jpeg_core` — single top-level module with the following interface:

### Parameter

| Parameter            | Default | Description                                                    |
|----------------------|---------|----------------------------------------------------------------|
| `SUPPORT_WRITABLE_DHT` | `0`   | Set to 1 to allow custom Huffman tables from the JPEG stream. Set to 0 for fixed standard tables (smaller, faster). |

### Input Ports

| Port               | Width | Description                                                                 |
|--------------------|-------|-----------------------------------------------------------------------------|
| `clk_i`            | 1     | Clock                                                                       |
| `rst_i`            | 1     | Synchronous active-high reset                                               |
| `inport_valid_i`   | 1     | Input data valid. Assert to push JPEG bytes into the core.                  |
| `inport_data_i`    | 32    | Input data word (4 bytes of JPEG stream, LSB first)                        |
| `inport_strb_i`    | 4     | Byte-enable strobes for `inport_data_i` (1 bit per byte)                   |
| `inport_last_i`    | 1     | Assert on the last word of the JPEG stream for a given image                |
| `outport_accept_i` | 1     | Output ready. Assert to consume the current output pixel.                   |

### Output Ports

| Port                | Width | Description                                                                |
|---------------------|-------|----------------------------------------------------------------------------|
| `inport_accept_o`   | 1     | Input ready. The core can accept a new input word this cycle.              |
| `outport_valid_o`   | 1     | Output pixel valid. A decoded RGB pixel is available this cycle.           |
| `outport_width_o`   | 16    | Width of the decoded image in pixels                                       |
| `outport_height_o`  | 16    | Height of the decoded image in pixels                                      |
| `outport_pixel_x_o` | 16    | X coordinate of the current output pixel                                   |
| `outport_pixel_y_o` | 16    | Y coordinate of the current output pixel                                   |
| `outport_pixel_r_o` | 8     | Red channel of the current output pixel                                    |
| `outport_pixel_g_o` | 8     | Green channel of the current output pixel                                  |
| `outport_pixel_b_o` | 8     | Blue channel of the current output pixel                                   |
| `idle_o`            | 1     | Asserted when the core has finished decoding and is idle                   |

### Handshake Protocol

The input and output ports use a valid/accept (valid/ready) handshake:
- A transfer occurs on any cycle where `valid` and `accept` are both high.
- `inport_accept_o` may be low when the core's internal pipeline is full.
- `outport_valid_o` goes high when a decoded pixel is ready; the pixel is held until `outport_accept_i` is asserted.

### Typical Usage Sequence

1. Assert `rst_i` for at least one cycle, then deassert.
2. Drive `inport_valid_i`, `inport_data_i`, `inport_strb_i` with successive 32-bit words of a JPEG file. On each cycle where `inport_accept_o` is high, the transfer is accepted; otherwise hold the current word.
3. Assert `inport_last_i` on the final word of the JPEG stream.
4. Monitor `outport_valid_o`. Each cycle it is high, a valid RGB pixel is available at `outport_pixel_{r,g,b}_o` along with its `outport_pixel_{x,y}_o` coordinates. Assert `outport_accept_i` to advance to the next pixel.
5. After all pixels have been consumed, `idle_o` goes high indicating the core is ready to accept a new JPEG image.

## Internal Pipeline (Submodules)

| Submodule             | Description                                                                                     |
|-----------------------|-------------------------------------------------------------------------------------------------|
| `jpeg_input`          | Parses JPEG file headers (SOI, SOF, SOS, DHT, DQT markers). Extracts image dimensions, color mode, and table data. Routes raw bitstream bytes to the bit buffer. |
| `jpeg_dht`            | Stores Huffman decode tables for DC and AC coefficients (Y and CbCr channels). With `SUPPORT_WRITABLE_DHT=0` uses fixed standard JPEG tables (`jpeg_dht_std_y_dc`, `jpeg_dht_std_y_ac`, `jpeg_dht_std_cx_dc`, `jpeg_dht_std_cx_ac`). |
| `jpeg_bitbuffer`      | Bit-level FIFO buffer over the compressed entropy-coded data segment. Provides a 32-bit sliding window and bit-pop interface to the MCU processor. |
| `jpeg_mcu_proc`       | Minimum Coded Unit processor. Reads bits from the bit buffer, performs Huffman lookup via `jpeg_dht`, and reconstructs DC/AC DCT coefficients for each 8×8 block. Uses `jpeg_mcu_id` to track MCU block identity across chroma subsampling modes. |
| `jpeg_dqt`            | Dequantization stage. Multiplies each DCT coefficient by the corresponding entry in the quantization table (loaded from the JPEG stream). Outputs dequantized 8×8 blocks. |
| `jpeg_idct`           | Inverse Discrete Cosine Transform. Contains a 2-pass (row then column) 8-point IDCT implemented via `jpeg_idct_x`, `jpeg_idct_y`, intermediate transposition RAM (`jpeg_idct_transpose` / `jpeg_idct_transpose_ram`), input RAM (`jpeg_idct_ram` / `jpeg_idct_ram_dp`), and an output FIFO (`jpeg_idct_fifo`). |
| `jpeg_output`         | Output formatter. Converts IDCT spatial-domain samples from YCbCr to RGB. Buffers luma (`jpeg_output_y_ram`) and chroma (`jpeg_output_cx_ram`) samples, handles 4:2:0 upsampling, and emits one RGB pixel per cycle with x/y coordinates via an output FIFO (`jpeg_output_fifo`). |

## Key Features and Constraints

- Supports **Baseline sequential** JPEG only (no progressive, no lossless).
- Chroma subsampling: **Monochrome**, **4:4:4**, **4:2:0** (4:2:2 is not supported).
- Input is a complete JPEG File Interchange Format (JFIF) byte stream; the core parses all required markers internally.
- One image is decoded at a time; the core must return to `idle_o` before a new image can be started.
- Restart markers and the first layer of progressive JPEG are not supported.
- With `SUPPORT_WRITABLE_DHT=0`, the DHT segment in the JPEG stream is ignored and standard JPEG Huffman tables are used. Set `SUPPORT_WRITABLE_DHT=1` only if non-standard (optimised) Huffman tables are required.
