/*######################################################################*\
## Class Name: rgb_color_space_hsv_subscriber
## Based on:  AES_Encrypt_subscriber style (uvm_subscriber + sub_imp)
## Purpose:   Functional coverage for RGB->HSV converter
\*######################################################################*/

class rgb_color_space_hsv_subscriber extends uvm_subscriber #(rgb_color_space_hsv_seq_item);
  `uvm_component_utils(rgb_color_space_hsv_subscriber)

  // Latest observed transaction
  rgb_color_space_hsv_seq_item item;

  // Match the AES template pattern (explicit analysis imp)
  uvm_analysis_imp #(rgb_color_space_hsv_seq_item, rgb_color_space_hsv_subscriber) sub_imp;

  // --------------------------------------------------------------------
  // Derived signals (mirrors tb_rgb_color_space_hsv.sv derived coverage logic)
  // --------------------------------------------------------------------
  logic [7:0] max_rgb;
  logic [7:0] min_rgb;
  logic [7:0] delta_rgb;

  // --------------------------------------------------------------------
  // Helpers (mirror TB calc_max/calc_min intent)
  // --------------------------------------------------------------------
  function automatic logic [7:0] calc_max(input logic [7:0] a,
                                         input logic [7:0] b,
                                         input logic [7:0] c);
    logic [7:0] m;
    m = (a >= b) ? a : b;
    m = (m >= c) ? m : c;
    return m;
  endfunction

  function automatic logic [7:0] calc_min(input logic [7:0] a,
                                         input logic [7:0] b,
                                         input logic [7:0] c);
    logic [7:0] m;
    m = (a <= b) ? a : b;
    m = (m <= c) ? m : c;
    return m;
  endfunction

  // --------------------------------------------------------------------
  // COVERAGE: Advanced RGB/HSV behavior (ported from tb covergroup)
  // In TB this was: covergroup cg_rgb_hsv_advanced @(posedge clk iff valid_in);
  // Here: sample from write(), with iff(item.valid_in) on points/crosses.
  // --------------------------------------------------------------------
  covergroup cg_rgb_hsv_advanced;
    option.per_instance = 1;

    // Cover R component corner cases
    cp_r_component: coverpoint item.r_component iff (item.valid_in) {
      bins zero       = {8'h00};
      bins one        = {8'h01};
      bins max_val    = {8'hFF};
      bins almost_max = {8'hFE};
      bins low_range  = {[8'h02:8'h1F]};
      bins mid_low    = {[8'h20:8'h7F]};
      bins mid_high   = {[8'h80:8'hDF]};
      bins high_range = {[8'hE0:8'hFD]};
      bins power_of_2[] = {8'h01, 8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
    }

    // Cover G component corner cases
    cp_g_component: coverpoint item.g_component iff (item.valid_in) {
      bins zero       = {8'h00};
      bins one        = {8'h01};
      bins max_val    = {8'hFF};
      bins almost_max = {8'hFE};
      bins low_range  = {[8'h02:8'h1F]};
      bins mid_low    = {[8'h20:8'h7F]};
      bins mid_high   = {[8'h80:8'hDF]};
      bins high_range = {[8'hE0:8'hFD]};
      bins power_of_2[] = {8'h01, 8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
    }

    // Cover B component corner cases
    cp_b_component: coverpoint item.b_component iff (item.valid_in) {
      bins zero       = {8'h00};
      bins one        = {8'h01};
      bins max_val    = {8'hFF};
      bins almost_max = {8'hFE};
      bins low_range  = {[8'h02:8'h1F]};
      bins mid_low    = {[8'h20:8'h7F]};
      bins mid_high   = {[8'h80:8'hDF]};
      bins high_range = {[8'hE0:8'hFD]};
      bins power_of_2[] = {8'h01, 8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
    }

    // Cover which channel is maximum (determines hue sector)
    cp_max_channel: coverpoint {
        (item.r_component >= item.g_component && item.r_component >= item.b_component),
        (item.g_component >= item.r_component && item.g_component >= item.b_component),
        (item.b_component >= item.r_component && item.b_component >= item.g_component)
      } iff (item.valid_in)
    {
      bins r_is_max  = {3'b100};
      bins g_is_max  = {3'b010};
      bins b_is_max  = {3'b001};
      bins r_g_tie   = {3'b110};
      bins g_b_tie   = {3'b011};
      bins r_b_tie   = {3'b101};
      bins all_equal = {3'b111};
    }

    // Cover delta (max - min) values - critical for saturation and hue
    cp_delta: coverpoint delta_rgb iff (item.valid_in) {
      bins zero            = {8'h00}; // Grayscale
      bins very_small_delta = {[8'h01:8'h0F]};
      bins small_delta      = {[8'h10:8'h3F]};
      bins medium_delta     = {[8'h40:8'hBF]};
      bins large_delta      = {[8'hC0:8'hFE]};
      bins max_delta        = {8'hFF};
    }

    // Cover grayscale vs color
    cp_color_type: coverpoint (item.r_component == item.g_component &&
                               item.g_component == item.b_component) iff (item.valid_in)
    {
      bins grayscale = {1'b1};
      bins color_val = {1'b0};
    }

    // Cover primary colors
    cp_primary_colors: coverpoint {item.r_component, item.g_component, item.b_component} iff (item.valid_in) {
      bins pure_red     = {24'hFF0000};
      bins pure_green   = {24'h00FF00};
      bins pure_blue    = {24'h0000FF};
      bins pure_cyan    = {24'h00FFFF};
      bins pure_magenta = {24'hFF00FF};
      bins pure_yellow  = {24'hFFFF00};
      bins pure_white   = {24'hFFFFFF};
      bins pure_black   = {24'h000000};
    }

    // Cover equal channel combinations (corner cases for hue calculation)
    cp_equal_channels: coverpoint {
        (item.r_component == item.g_component),
        (item.g_component == item.b_component),
        (item.r_component == item.b_component)
      } iff (item.valid_in)
    {
      bins all_different   = {3'b000};
      bins r_eq_g          = {3'b100};
      bins g_eq_b          = {3'b010};
      bins r_eq_b          = {3'b001};
      bins all_equal       = {3'b111};
    }

    // Cross: R vs G to cover all comparison cases
    cross_r_vs_g: cross cp_r_component, cp_g_component iff (item.valid_in) {
      bins r_greater_g = binsof(cp_r_component.mid_high) && binsof(cp_g_component.low_range);
      bins g_greater_r = binsof(cp_g_component.mid_high) && binsof(cp_r_component.low_range);
      bins r_eq_g_zero = binsof(cp_r_component.zero)     && binsof(cp_g_component.zero);
      bins r_eq_g_max  = binsof(cp_r_component.max_val)  && binsof(cp_g_component.max_val);
    }

    // Cross: All three channels to capture specific color patterns
    cross_rgb_pattern: cross cp_r_component, cp_g_component, cp_b_component iff (item.valid_in) {
      bins all_zero           = binsof(cp_r_component.zero)    && binsof(cp_g_component.zero)    && binsof(cp_b_component.zero);
      bins all_max            = binsof(cp_r_component.max_val) && binsof(cp_g_component.max_val) && binsof(cp_b_component.max_val);
      bins r_max_others_zero  = binsof(cp_r_component.max_val) && binsof(cp_g_component.zero)    && binsof(cp_b_component.zero);
      bins g_max_others_zero  = binsof(cp_r_component.zero)    && binsof(cp_g_component.max_val) && binsof(cp_b_component.zero);
      bins b_max_others_zero  = binsof(cp_r_component.zero)    && binsof(cp_g_component.zero)    && binsof(cp_b_component.max_val);
    }

    // Cross: Max channel with delta to verify hue calculation
    cross_max_delta: cross cp_max_channel, cp_delta iff (item.valid_in) {
      bins r_max_no_sat    = binsof(cp_max_channel.r_is_max) && binsof(cp_delta.zero);
      bins g_max_no_sat    = binsof(cp_max_channel.g_is_max) && binsof(cp_delta.zero);
      bins b_max_no_sat    = binsof(cp_max_channel.b_is_max) && binsof(cp_delta.zero);
      bins r_max_full_sat  = binsof(cp_max_channel.r_is_max) && binsof(cp_delta.max_delta);
      bins g_max_full_sat  = binsof(cp_max_channel.g_is_max) && binsof(cp_delta.max_delta);
      bins b_max_full_sat  = binsof(cp_max_channel.b_is_max) && binsof(cp_delta.max_delta);
    }

    // Cross: Color type with delta
    cross_color_delta: cross cp_color_type, cp_delta iff (item.valid_in) {
      bins grayscale_zero_delta = binsof(cp_color_type.grayscale) && binsof(cp_delta.zero);
      illegal_bins grayscale_nonzero =
        binsof(cp_color_type.grayscale) && (!binsof(cp_delta.zero));
    }

  endgroup : cg_rgb_hsv_advanced

  // --------------------------------------------------------------------
  // COVERAGE: Valid behavior (ported from tb covergroup)
  // TB: covergroup cg_valid_behavior @(posedge clk);
  // Here: sampled on write(); transitions only work if write() called each cycle.
  // --------------------------------------------------------------------
  covergroup cg_valid_behavior;
    option.per_instance = 1;

    cp_valid_in_trans: coverpoint item.valid_in {
      bins rise      = (1'b0 => 1'b1);
      bins fall      = (1'b1 => 1'b0);
      bins stay_high = (1'b1 => 1'b1);
      bins stay_low  = (1'b0 => 1'b0);
    }
  endgroup : cg_valid_behavior

  // --------------------------------------------------------------------
  // UVM plumbing (AES template style)
  // --------------------------------------------------------------------
  function new(string name="rgb_color_space_hsv_subscriber", uvm_component parent=null);
    super.new(name, parent);
    cg_rgb_hsv_advanced = new();
    cg_valid_behavior   = new();
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    sub_imp = new("sub_imp", this);
  endfunction

  virtual function void write(rgb_color_space_hsv_seq_item t);
    item = t;

    // Update derived signals (mirrors TB)
    max_rgb   = calc_max(item.r_component, item.g_component, item.b_component);
    min_rgb   = calc_min(item.r_component, item.g_component, item.b_component);
    delta_rgb = max_rgb - min_rgb;

    // Sample valid behavior always (matches TB intent of clock sampling)
    cg_valid_behavior.sample();

    // Sample the advanced RGB coverage only when valid_in is asserted (matches TB iff valid_in)
    if (item.valid_in) begin
      cg_rgb_hsv_advanced.sample();
    end
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("rgb_color_space_hsv_subscriber",
              $sformatf("cg_rgb_hsv_advanced coverage = %0.2f%%",
                        cg_rgb_hsv_advanced.get_coverage()),
              UVM_NONE)

    `uvm_info("rgb_color_space_hsv_subscriber",
              $sformatf("cg_valid_behavior coverage = %0.2f%%",
                        cg_valid_behavior.get_coverage()),
              UVM_NONE)
  endfunction

endclass : rgb_color_space_hsv_subscriber