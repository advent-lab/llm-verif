# JPEG Encoder (`jpeg_top`) — Design Specification

## Overview

`jpeg_top` is a hardware JPEG baseline encoder. It accepts a stream of 24-bit RGB pixels and produces a packed JPEG-compliant bitstream. The design implements the full baseline JPEG encode pipeline: RGB-to-YCbCr color conversion, 8×8 2D DCT, quantization using standard luminance/chrominance tables, Huffman entropy coding, and JPEG-standard 0xFF byte stuffing.

The design operates as a streaming pipeline — pixels are clocked in one per cycle when `enable` is asserted, and encoded JPEG data words appear at the output after the pipeline latency.

---

## Top Module: `jpeg_top`

```
module jpeg_top(
    input        clk,
    input        rst,
    input        end_of_file_signal,
    input        enable,
    input  [23:0] data_in,
    output [31:0] JPEG_bitstream,
    output        data_ready,
    output [4:0]  end_of_file_bitstream_count,
    output        eof_data_partial_ready
);
```

### Port Descriptions

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `clk` | in | 1 | Clock |
| `rst` | in | 1 | Synchronous active-high reset |
| `end_of_file_signal` | in | 1 | Assert high for one cycle to signal end of image |
| `enable` | in | 1 | Enable pixel input; hold high while streaming pixels |
| `data_in` | in | 24 | RGB pixel: R=[7:0], G=[15:8], B=[23:16] |
| `JPEG_bitstream` | out | 32 | 32-bit packed JPEG output data word |
| `data_ready` | out | 1 | High when `JPEG_bitstream` contains valid data |
| `end_of_file_bitstream_count` | out | 5 | Number of valid bits in the final (partial) output word at EOF |
| `eof_data_partial_ready` | out | 1 | High when the final partial EOF data word is available |

---

## Encoding Pipeline

```
data_in (RGB)
    │
    ▼
RGB2YCBCR          — converts R/G/B to Y (luminance), Cb/Cr (chrominance)
    │
    ├──► yd_q_h    — Y channel:  y_dct → y_quantizer → y_huff
    ├──► cbd_q_h   — Cb channel: cb_dct → cb_quantizer → cb_huff
    └──► crd_q_h   — Cr channel: cr_dct → cr_quantizer → cr_huff
             │
             ▼
          fifo_out  — merges three encoded bitstreams via sync_fifo_32 buffers
             │
             ▼
          ff_checker — inserts 0x00 after any 0xFF byte (JPEG standard)
             │
             ▼
    JPEG_bitstream (32-bit words) + data_ready strobe
```

- **DCT:** 2D 8×8 DCT operating on 8-bit pixel blocks; produces 64 × 11-bit coefficients.
- **Quantization:** Uses fixed standard JPEG luminance table (Y) and chrominance table (Cb/Cr). Quantization step divides each DCT coefficient.
- **Huffman:** Fixed JPEG baseline Huffman tables. DC coefficients use differential coding. AC coefficients use run-length + magnitude category coding. Output is variable-length codes packed into a 32-bit shift register (`output_reg_count` tracks how many bits are valid).
- **FF stuffing:** Any `0xFF` byte in the bitstream has `0x00` appended after it. This is handled by `ff_checker` / `sync_fifo_ff`.

---

## How to Generate Stimulus

### Basic operation

1. Assert `rst` for at least one cycle, then deassert.
2. Assert `enable = 1`.
3. Drive `data_in[23:0]` with RGB pixels every clock cycle. Pixels are processed in raster-scan order, grouped into 8×8 MCU blocks internally.
4. Monitor `data_ready` — when high, `JPEG_bitstream` contains 32 valid bits of encoded output.
5. To terminate: assert `end_of_file_signal` for one cycle after the last pixel. The final partial word is flagged by `eof_data_partial_ready`, with `end_of_file_bitstream_count` indicating how many bits are valid in that word.

### Coverage guidance

- **Channel coverage:** All three pipelines (Y, Cb, Cr) are active simultaneously from the first pixel. No special sequencing is needed.
- **Huffman coverage:** To exercise different Huffman code paths, vary the pixel values to produce a range of DCT coefficient magnitudes:
  - Uniform flat regions (e.g., all-grey) exercise small AC coefficients (run-length codes).
  - High-contrast edges or sharp gradients produce large AC/DC coefficients.
  - Try all-zero, all-max, checkerboard, ramp, and random pixel patterns.
- **DCT block boundaries:** Each 8×8 pixel block is processed as a unit. Feed at least a few complete blocks (64+ pixels) per test.
- **EOF path:** Assert `end_of_file_signal` after a complete image to exercise the EOF logic in `ff_checker` and `fifo_out`.
- **FF stuffing:** `ff_checker` activates when an output byte equals `0xFF`. This is difficult to target directly; it occurs naturally in some pixel patterns that produce dense Huffman codes.

---

## Key Internal Modules

| Module | File | Role |
|--------|------|------|
| `RGB2YCBCR` | `rgb2ycbcr.v` | 3-stage pipelined color space converter |
| `y_dct` / `cb_dct` / `cr_dct` | `*_dct.v` | 2D 8×8 DCT per channel |
| `y_quantizer` / `cb_quantizer` / `cr_quantizer` | `*_quantizer.v` | Fixed-table quantization |
| `y_huff` / `cb_huff` / `cr_huff` | `*_huff.v` | Huffman entropy encoder per channel |
| `yd_q_h` / `cbd_q_h` / `crd_q_h` | `*d_q_h.v` | Combined DCT+quantizer+Huffman pipeline per channel |
| `pre_fifo` | `pre_fifo.v` | Drives all three channel pipelines in parallel |
| `fifo_out` | `fifo_out.v` | Merges Y/Cb/Cr bitstreams; uses `sync_fifo_32` buffers |
| `ff_checker` | `ff_checker.v` | Scans output for 0xFF, inserts 0x00 stuffing bytes |
| `sync_fifo_32` | `sync_fifo_32.v` | 16-entry × 32-bit synchronous FIFO |
| `sync_fifo_ff` | `sync_fifo_ff.v` | 16-entry × 91-bit FIFO used by ff_checker |
