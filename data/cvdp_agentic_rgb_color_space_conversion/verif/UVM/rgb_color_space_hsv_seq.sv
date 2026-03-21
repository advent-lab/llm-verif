// rgb_color_space_hsv_seq.sv
// UVM sequences for rgb_color_space_hsv
//
// This file mirrors the original *directed* stimulus style from tb_rgb_color_space_hsv.sv:
//   - init_inverse_lut(): we asserted for 256 cycles while writing waddr/wdata, then we deasserted
//   - send_rgb(r,g,b): valid_in asserted for 1 cycle with RGB, then deasserted/cleared next cycle
//   - repeat(10) idle cycles between RGB inputs, and repeat(20) at the end to flush the pipeline
//
// Notes:
//   - No reliance on monitor events (e.g., valid_out) for pacing; we use explicit idle cycles like the TB.
//   - If your driver already forces outputs low between items, these explicit deassert/idle items are still safe.

`ifndef RGB_COLOR_SPACE_HSV_SEQ_SV
`define RGB_COLOR_SPACE_HSV_SEQ_SV

//--------------------------
// Base Sequence
//--------------------------
class rgb_color_space_hsv_base_sequence extends uvm_sequence #(rgb_color_space_hsv_seq_item);

  `uvm_object_utils(rgb_color_space_hsv_base_sequence)

  function new(string name = "rgb_color_space_hsv_base_sequence");
    super.new(name);
  endfunction

  // Drive exactly one cycle worth of stimulus (one seq_item).
  // The driver is expected to apply the fields for one clk and then move on.
  protected virtual task drive_cycle(
      bit        we,
      bit        valid_in,
      byte unsigned r,
      byte unsigned g,
      byte unsigned b,
      byte unsigned waddr,
      logic [24:0] wdata
  );
    rgb_color_space_hsv_seq_item item;
    item = rgb_color_space_hsv_seq_item::type_id::create("item");

    start_item(item);
      // Prefer explicit assignments over randomize() so we match the TB exactly.
      item.we         = we;
      item.valid_in   = valid_in;
      item.r_component = r;
      item.g_component = g;
      item.b_component = b;
      item.waddr      = waddr;
      item.wdata      = wdata;
    finish_item(item);
  endtask

  // N idle cycles: deassert everything, drive zeros.
  protected virtual task idle_cycles(int unsigned n);
    for (int unsigned k = 0; k < n; k++) begin
      drive_cycle(/*we*/0, /*valid_in*/0, 8'h00, 8'h00, 8'h00, 8'h00, 25'h0);
    end
  endtask

  // TB-equivalent LUT init:
  //   we=1 for 256 cycles; each cycle updates waddr and wdata.
  //   special case: i==0 => wdata = 25'h1FFFFFF
  //   else: wdata = 25'h1000000 / i
  protected virtual task init_inverse_lut();
    `uvm_info(get_type_name(), "Initializing inverse lookup table (TB-equivalent)", UVM_MEDIUM)

    for (int unsigned i = 0; i < 256; i++) begin
      logic [24:0] lut_data;
      if (i == 0)
        lut_data = 25'h1FFFFFF;
      else
        lut_data = (25'h1000000 / i);

      drive_cycle(/*we*/1, /*valid_in*/0, 8'h00, 8'h00, 8'h00, byte'(i[7:0]), lut_data);
    end

    // Deassert we after the write burst (TB: we=0 after loop)
    drive_cycle(/*we*/0, /*valid_in*/0, 8'h00, 8'h00, 8'h00, 8'h00, 25'h0);

    `uvm_info(get_type_name(), "Inverse LUT initialized", UVM_MEDIUM)
  endtask

  // TB-equivalent RGB send:
  //   Cycle 1: valid_in=1 with r/g/b
  //   Cycle 2: valid_in=0 and clear RGB
  protected virtual task send_rgb(byte unsigned r, byte unsigned g, byte unsigned b);
    drive_cycle(/*we*/0, /*valid_in*/1, r, g, b, 8'h00, 25'h0);
    drive_cycle(/*we*/0, /*valid_in*/0, 8'h00, 8'h00, 8'h00, 8'h00, 25'h0);
  endtask

endclass

//--------------------------
// Directed Sequence (matches tb_rgb_color_space_hsv.sv)
//--------------------------
class rgb_color_space_hsv_directed_sequence extends rgb_color_space_hsv_base_sequence;

  `uvm_object_utils(rgb_color_space_hsv_directed_sequence)

  function new(string name = "rgb_color_space_hsv_directed_sequence");
    super.new(name);
  endfunction

  virtual task body();
    // Mirror TB pacing around reset (TB: repeat(5) then deassert reset in tb)
    // Reset itself is typically driven by the test/env, so we just add the post-reset spacing.
    idle_cycles(5);

    // Initialize inverse lookup table
    init_inverse_lut();

    // TB: repeat(5) after init
    idle_cycles(5);

    `uvm_info(get_type_name(), "=== Basic Sanity Tests ===", UVM_LOW)

    // Test 1: Primary colors
    `uvm_info(get_type_name(), "Test 1: Primary colors", UVM_LOW)
    send_rgb(8'hFF, 8'h00, 8'h00); // Red
    idle_cycles(10);
    send_rgb(8'h00, 8'hFF, 8'h00); // Green
    idle_cycles(10);
    send_rgb(8'h00, 8'h00, 8'hFF); // Blue
    idle_cycles(10);

    // Test 2: Grayscale
    `uvm_info(get_type_name(), "Test 2: Grayscale values", UVM_LOW)
    send_rgb(8'h00, 8'h00, 8'h00); // Black
    idle_cycles(10);
    send_rgb(8'h80, 8'h80, 8'h80); // Gray
    idle_cycles(10);
    send_rgb(8'hFF, 8'hFF, 8'hFF); // White
    idle_cycles(10);

    // Test 3: Secondary colors
    `uvm_info(get_type_name(), "Test 3: Secondary colors", UVM_LOW)
    send_rgb(8'hFF, 8'hFF, 8'h00); // Yellow
    idle_cycles(10);
    send_rgb(8'h00, 8'hFF, 8'hFF); // Cyan
    idle_cycles(10);
    send_rgb(8'hFF, 8'h00, 8'hFF); // Magenta
    idle_cycles(10);

    // Test 4: Random samples (TB: 10 samples)
    `uvm_info(get_type_name(), "Test 4: Random color samples", UVM_LOW)
    for (int unsigned i = 0; i < 10; i++) begin
      byte unsigned rr, gg, bb;
      rr = byte'($urandom_range(0, 255));
      gg = byte'($urandom_range(0, 255));
      bb = byte'($urandom_range(0, 255));
      send_rgb(rr, gg, bb);
      idle_cycles(10);
    end

    // TB: Wait for pipeline to flush
    idle_cycles(20);

  endtask

endclass

//--------------------------
// Random Sequence (optional, TB-like pacing)
//--------------------------
class rgb_color_space_hsv_random_sequence extends rgb_color_space_hsv_base_sequence;

  rand int unsigned num_random;
  constraint c_num_random { num_random inside {[1:5000]}; }
  int unsigned idle_between = 10;

  `uvm_object_utils_begin(rgb_color_space_hsv_random_sequence)
    `uvm_field_int(num_random, UVM_DEFAULT)
    `uvm_field_int(idle_between, UVM_DEFAULT)
  `uvm_object_utils_end

  function new(string name = "rgb_color_space_hsv_random_sequence");
    super.new(name);
    num_random = 10; // match TB default behavior unless overridden
  endfunction

  virtual task body();
    idle_cycles(5);
    init_inverse_lut();
    idle_cycles(5);

    for (int unsigned i = 0; i < num_random; i++) begin
      byte unsigned rr, gg, bb;
      rr = byte'($urandom_range(0, 255));
      gg = byte'($urandom_range(0, 255));
      bb = byte'($urandom_range(0, 255));
      send_rgb(rr, gg, bb);
      idle_cycles(idle_between);
    end

    idle_cycles(20);
  endtask

endclass

`endif
