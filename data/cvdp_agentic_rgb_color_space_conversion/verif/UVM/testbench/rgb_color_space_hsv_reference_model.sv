// rgb_color_space_hsv_reference_model.sv
`ifndef RGB_COLOR_SPACE_HSV_REFERENCE_MODEL_SV
`define RGB_COLOR_SPACE_HSV_REFERENCE_MODEL_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

// IMPORTANT:
// This file assumes rgb_color_space_hsv_seq_item is visible at compile time.
// (Your filelist already compiles it first.)

class rgb_color_space_hsv_ref_model extends uvm_component;

  // Incoming transaction type from monitor/agent
  typedef rgb_color_space_hsv_seq_item item_t;

  // Default pipeline latency (matches your earlier model)
  localparam int unsigned DEFAULT_LATENCY_CYCLES = 8;

  // Expected pipeline slot (no known/reason; pure expected)
  typedef struct packed {
    bit          valid_out;
    logic [11:0] h_component;
    logic [12:0] s_component;
    logic [11:0] v_component;
  } exp_slot_t;

  // TLM
  uvm_analysis_imp #(item_t, rgb_color_space_hsv_ref_model) in_imp;

  // Optional: forward actual transaction to other components if you want
  // (safe to leave disconnected)
  uvm_analysis_port#(item_t) out_ap;

  // Inverse LUT memory written by DUT test interface
  logic [24:0] inverse_lut [0:255];

  // Expected pipeline queue
  exp_slot_t exp_pipe[$];

  int unsigned latency_cycles;

  `uvm_component_utils(rgb_color_space_hsv_ref_model)

  function new(string name="rgb_color_space_hsv_ref_model", uvm_component parent=null);
    super.new(name, parent);
    in_imp = new("in_imp", this);
    out_ap = new("out_ap", this);
    latency_cycles = DEFAULT_LATENCY_CYCLES;
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'(uvm_config_db#(int unsigned)::get(this, "", "latency_cycles", latency_cycles));
    if (latency_cycles == 0) latency_cycles = DEFAULT_LATENCY_CYCLES;
    reset_pipeline();
  endfunction

  // ----------------------------
  // Helpers
  // ----------------------------
  function automatic exp_slot_t make_bubble();
    exp_slot_t b;
    b.valid_out   = 1'b0;
    b.h_component = '0;
    b.s_component = '0;
    b.v_component = '0;
    return b;
  endfunction

  function void reset_pipeline();
    exp_pipe.delete();
    for (int i = 0; i < latency_cycles; i++) begin
      exp_pipe.push_back(make_bubble());
    end
  endfunction

  function automatic logic [7:0] max3(logic [7:0] a, logic [7:0] b, logic [7:0] c);
    logic [7:0] t;
    t = (a > b) ? a : b;
    return (t > c) ? t : c;
  endfunction

  function automatic logic [7:0] min3(logic [7:0] a, logic [7:0] b, logic [7:0] c);
    logic [7:0] t;
    t = (a < b) ? a : b;
    return (t < c) ? t : c;
  endfunction

  // Predict expected HSV for ONE valid_in sample (design intent model)
  function automatic exp_slot_t predict_hsv(item_t tr);
    exp_slot_t slot;

    logic [7:0] cmax, cmin, delta;

    logic [24:0] inv_i_max;
    logic [24:0] inv_delta;

    logic signed [12:0] pre_hue;
    logic [8:0]         hue_offset;
    logic signed [18:0] pre_hue_prod;

    longint unsigned    sat_mult;
    longint unsigned    sat_scaled;
    longint signed      hue_mult_full;

    logic signed [11:0] almost_hue;
    logic signed [12:0] hue_sum;

    slot = make_bubble();
    slot.valid_out = 1'b1;

    cmax  = max3(tr.r_component, tr.g_component, tr.b_component);
    cmin  = min3(tr.r_component, tr.g_component, tr.b_component);
    delta = cmax - cmin;

    // V is just max channel (zero-extended)
    slot.v_component = {4'b0000, cmax};

    // S = (delta / cmax) in fixed-point using inverse LUT
    inv_i_max = inverse_lut[cmax];

    if (cmax == 0) begin
      slot.s_component = '0;
    end else begin
      sat_mult   = longint'(inv_i_max) * longint'(delta);
      // rounding similar to your earlier model
      sat_scaled = (sat_mult >> 12) + ((sat_mult >> 11) & 64'd1);
      slot.s_component = sat_scaled[12:0];
    end

    // H is 0 when delta==0
    if (delta == 0) begin
      slot.h_component = '0;
      return slot;
    end

    inv_delta = inverse_lut[delta];

    // pre_hue and offset selection (matches earlier intent)
    if (cmax == tr.r_component) begin
      pre_hue = $signed({1'b0, tr.g_component}) - $signed({1'b0, tr.b_component});
      if (pre_hue < 0) hue_offset = 9'd360;
      else             hue_offset = 9'd0;
    end else if (cmax == tr.g_component) begin
      pre_hue    = $signed({1'b0, tr.b_component}) - $signed({1'b0, tr.r_component});
      hue_offset = 9'd120;
    end else begin
      pre_hue    = $signed({1'b0, tr.r_component}) - $signed({1'b0, tr.g_component});
      hue_offset = 9'd240;
    end

    pre_hue_prod  = pre_hue * 19'sd60;
    hue_mult_full = longint'(pre_hue_prod) * longint'($signed({1'b0, inv_delta}));

    // shift to match fixed point scaling from your earlier model
    almost_hue = $signed(hue_mult_full >>> 22);

    // add offset (note your earlier model used {hue_offset,2'b00})
    hue_sum = $signed(almost_hue) + $signed({1'b0, hue_offset, 2'b00});

    slot.h_component = hue_sum[11:0];
    return slot;
  endfunction

  // ----------------------------
  // Main TLM entry: gets transactions from monitor/agent
  // ----------------------------
  function void write(item_t tr);
    exp_slot_t next_slot;
    exp_slot_t out_slot;

    if (tr == null) begin
      `uvm_warning(get_type_name(), "Received null transaction")
      return;
    end

    // Update LUT writes first (design intent)
    if (tr.we) begin
      inverse_lut[tr.waddr] = tr.wdata;
    end

    // Reset clears expected pipeline
    if (tr.rst) begin
      reset_pipeline();
    end

    // Push expected for this cycle (or bubble)
    next_slot = make_bubble();
    if (!tr.rst && tr.valid_in && !tr.we) begin
      next_slot = predict_hsv(tr);
    end

    exp_pipe.push_back(next_slot);
    out_slot = exp_pipe.pop_front();

    // Compare when DUT claims valid_out OR when we expect valid_out.
    // This catches both missing and spurious valids.
    if (tr.valid_out !== out_slot.valid_out) begin
      `uvm_error("REF_VO_MISMATCH",
        $sformatf("valid_out mismatch: DUT=%0b EXP=%0b | rgb=(%0d,%0d,%0d) we=%0b rst=%0b time=%0t",
          tr.valid_out, out_slot.valid_out,
          tr.r_component, tr.g_component, tr.b_component,
          tr.we, tr.rst, $time))
    end

    if (out_slot.valid_out) begin
      if (tr.h_component !== out_slot.h_component ||
          tr.s_component !== out_slot.s_component ||
          tr.v_component !== out_slot.v_component) begin

        `uvm_error("REF_HSV_MISMATCH",
          $sformatf("HSV mismatch @%0t:\n  rgb=(%0d,%0d,%0d)\n  DUT: h=%0d s=%0d v=%0d\n  EXP: h=%0d s=%0d v=%0d",
            $time,
            tr.r_component, tr.g_component, tr.b_component,
            tr.h_component, tr.s_component, tr.v_component,
            out_slot.h_component, out_slot.s_component, out_slot.v_component))
      end
    end

    // Optional forward
    out_ap.write(tr);
  endfunction

endclass

`endif
