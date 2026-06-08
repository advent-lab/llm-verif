`ifndef SHA1_SUBSCRIBER_SV
`define SHA1_SUBSCRIBER_SV

class sha1_subscriber extends uvm_subscriber #(sha1_coverage_item);
  `uvm_component_utils(sha1_subscriber)

  sha1_coverage_item item;

  // --------------------------------------------------------------------------
  // Rewritten from tb_sha1.sv to mirror the original SV testbench coverage
  // structure, covergroups, coverpoints, crosses, and bin names as closely as
  // possible in a UVM subscriber form.
  //
  // Sampling note:
  // - The SV testbench samples on clock events.
  // - This subscriber samples in write().
  // - Equivalence assumes the monitor publishes one coverage item per sampled
  //   clock with current-cycle values.
  //
  // Internal-field note:
  // - cg_status / cg_core_fsm / cg_w_mem / cg_digest require the coverage item
  //   to expose internal DUT state captured by the monitor.
  // - This rewrite assumes the following fields exist on sha1_coverage_item:
  //     status_ready, status_valid, fsm_state, round_ctr, digest,
  //     w_ctr_reg, w_mem_w
  //   Rename these references if your monitor/item uses different field names.
  // --------------------------------------------------------------------------

  covergroup cg_sha1_interface;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_address: coverpoint item.address {
      bins name0 = {8'h00};
      bins name1 = {8'h01};
      bins version = {8'h02};
      bins ctrl = {8'h08};
      bins status = {8'h09};
      bins block_range[] = {[8'h10:8'h1F]};
      bins digest_range[] = {[8'h20:8'h24]};
      bins invalid_low = {[8'h03:8'h07]};
      bins invalid_mid = {[8'h0A:8'h0F]};
      bins invalid_high = {[8'h25:8'hFF]};
    }

    cp_write_enable: coverpoint item.we {
      bins read_op = {1'b0};
      bins write_op = {1'b1};
    }

    cp_write_data_ctrl: coverpoint item.write_data[1:0]
      iff (item.address == 8'h08 && item.we) {
      bins init_only = {2'b01};
      bins next_only = {2'b10};
      bins init_next = {2'b11};
      bins none = {2'b00};
    }

    cp_block_data: coverpoint item.write_data
      iff (item.address >= 8'h10 && item.address <= 8'h1F && item.we) {
      bins all_zero = {32'h00000000};
      bins all_ones = {32'hFFFFFFFF};
      bins alternating_01 = {32'hAAAAAAAA};
      bins alternating_10 = {32'h55555555};
      bins pattern_ff00 = {32'hFF00FF00};
      bins pattern_00ff = {32'h00FF00FF};
      bins low_range = {[32'h00000001:32'h0000FFFF]};
      bins mid_range = {[32'h00010000:32'h7FFFFFFF]};
      bins high_range = {[32'h80000000:32'hFFFFFFFE]};
    }

    cross_addr_op: cross cp_address, cp_write_enable {
      bins read_name = binsof(cp_address.name0) && binsof(cp_write_enable.read_op);
      bins read_version = binsof(cp_address.version) && binsof(cp_write_enable.read_op);
      bins read_status = binsof(cp_address.status) && binsof(cp_write_enable.read_op);
      bins write_ctrl = binsof(cp_address.ctrl) && binsof(cp_write_enable.write_op);
      bins write_block = binsof(cp_address.block_range) && binsof(cp_write_enable.write_op);
      bins read_block = binsof(cp_address.block_range) && binsof(cp_write_enable.read_op);
      bins read_digest = binsof(cp_address.digest_range) && binsof(cp_write_enable.read_op);

      ignore_bins write_readonly =
        binsof(cp_address) intersect {8'h00, 8'h01, 8'h02, 8'h09} &&
        binsof(cp_write_enable.write_op);
    }

    cross_ctrl_addr: cross cp_write_data_ctrl, cp_address {
      bins init_to_ctrl = binsof(cp_write_data_ctrl.init_only) && binsof(cp_address.ctrl);
      bins next_to_ctrl = binsof(cp_write_data_ctrl.next_only) && binsof(cp_address.ctrl);
      ignore_bins non_ctrl = !binsof(cp_address.ctrl);
    }
  endgroup


  covergroup cg_control_commands;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_ctrl_init: coverpoint item.ctrl_init {
      bins inactive = {1'b0};
      bins active = {1'b1};
    }

    cp_ctrl_next: coverpoint item.ctrl_next {
      bins inactive = {1'b0};
      bins active = {1'b1};
    }

    cp_ctrl_sequence: coverpoint {item.ctrl_init, item.ctrl_next} {
      bins init_cmd = {2'b10};
      bins next_cmd = {2'b01};
      bins idle = {2'b00};
      bins init_next_simul = {2'b11};
    }

    cp_cmd_transitions: coverpoint {item.ctrl_init, item.ctrl_next} {
      bins init_to_next = (2'b10 => 2'b01);
      bins next_to_next = (2'b01 => 2'b01);
      bins init_to_idle = (2'b10 => 2'b00);
      bins next_to_idle = (2'b01 => 2'b00);
      bins idle_to_init = (2'b00 => 2'b10);
      bins idle_to_next = (2'b00 => 2'b01);
    }
  endgroup


  covergroup cg_status;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_ready: coverpoint item.status_ready {
      bins not_ready = {1'b0};
      bins ready_state = {1'b1};
    }

    cp_digest_valid: coverpoint item.status_valid {
      bins invalid = {1'b0};
      bins valid_state = {1'b1};
    }

    cp_ready_trans: coverpoint item.status_ready {
      bins ready_rise = (1'b0 => 1'b1);
      bins ready_fall = (1'b1 => 1'b0);
      bins stay_ready = (1'b1 => 1'b1);
      bins stay_busy = (1'b0 => 1'b0);
    }

    cp_valid_trans: coverpoint item.status_valid {
      bins valid_rise = (1'b0 => 1'b1);
      bins valid_fall = (1'b1 => 1'b0);
      bins stay_valid = (1'b1 => 1'b1);
      bins stay_invalid = (1'b0 => 1'b0);
    }

    cross_ready_valid: cross cp_ready, cp_digest_valid {
      bins idle_no_digest = binsof(cp_ready.ready_state) && binsof(cp_digest_valid.invalid);
      bins busy_no_digest = binsof(cp_ready.not_ready) && binsof(cp_digest_valid.invalid);
      bins ready_with_digest = binsof(cp_ready.ready_state) && binsof(cp_digest_valid.valid_state);
      bins busy_digest_hold = binsof(cp_ready.not_ready) && binsof(cp_digest_valid.valid_state);
    }
  endgroup


  covergroup cg_core_fsm;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_fsm_state: coverpoint item.fsm_state {
      bins idle_state = {2'b00};
      bins rounds_state = {2'b01};
      bins done_state = {2'b10};
      ignore_bins invalid_state_illegal = {2'b11};
    }

    cp_fsm_trans: coverpoint item.fsm_state {
      bins idle_to_rounds = (2'b00 => 2'b01);
      bins rounds_to_done = (2'b01 => 2'b10);
      bins done_to_idle = (2'b10 => 2'b00);
      bins idle_to_idle = (2'b00 => 2'b00);
      bins rounds_to_rounds = (2'b01 => 2'b01);
    }

    cp_round_counter: coverpoint item.round_ctr {
      bins round_0 = {7'd0};
      bins rounds_1_19 = {[7'd1:7'd19]};
      bins rounds_20_39 = {[7'd20:7'd39]};
      bins rounds_40_59 = {[7'd40:7'd59]};
      bins rounds_60_78 = {[7'd60:7'd78]};
      bins round_79 = {7'd79};
    }

    cross_fsm_rounds: cross cp_fsm_state, cp_round_counter {
      bins idle_round0 = binsof(cp_fsm_state.idle_state) && binsof(cp_round_counter.round_0);
      bins rounds_early = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_1_19);
      bins rounds_mid1 = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_20_39);
      bins rounds_mid2 = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_40_59);
      bins rounds_late = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_60_78);
      bins rounds_last = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.round_79);
      bins done_any_round = binsof(cp_fsm_state.done_state);

      ignore_bins idle_nonzero = binsof(cp_fsm_state.idle_state) &&
                                  (!binsof(cp_round_counter.round_0));
    }
  endgroup


  covergroup cg_w_mem;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_w_counter: coverpoint item.w_ctr_reg {
      bins initial_phase = {[7'd0:7'd15]};
      bins expansion_phase = {[7'd16:7'd79]};
    }

    cp_w_value: coverpoint item.w_mem_w {
      bins zero = {32'h00000000};
      bins all_ones = {32'hFFFFFFFF};
      bins low_val = {[32'h00000001:32'h7FFFFFFF]};
      bins high_val = {[32'h80000000:32'hFFFFFFFE]};
    }
  endgroup


  covergroup cg_digest;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_digest_h0: coverpoint item.digest[159:128] {
      bins low_range = {[32'h00000000:32'h3FFFFFFF]};
      bins mid_low = {[32'h40000000:32'h7FFFFFFF]};
      bins mid_high = {[32'h80000000:32'hBFFFFFFF]};
      bins high_range = {[32'hC0000000:32'hFFFFFFFF]};
    }

    cp_digest_h4: coverpoint item.digest[31:0] {
      bins low_range = {[32'h00000000:32'h3FFFFFFF]};
      bins mid_low = {[32'h40000000:32'h7FFFFFFF]};
      bins mid_high = {[32'h80000000:32'hBFFFFFFF]};
      bins high_range = {[32'hC0000000:32'hFFFFFFFF]};
    }
  endgroup


  covergroup cg_errors;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_error_flag: coverpoint item.error {
      bins no_error = {1'b0};
      bins error_detected = {1'b1};
    }

    cp_error_addr: coverpoint item.address iff (item.error) {
      bins invalid_addrs = {[8'h03:8'h07], [8'h0A:8'h0F], [8'h25:8'hFF]};
    }
  endgroup


  covergroup cg_back_to_back;
    option.per_instance = 1;
    option.cross_auto_bin_max = 0;

    cp_cs_pattern: coverpoint item.cs {
      bins active = {1'b1};
      bins inactive = {1'b0};
    }

    cp_we_pattern: coverpoint item.we {
      bins write_mode = {1'b1};
      bins read_mode = {1'b0};
    }

    cp_cs_transitions: coverpoint item.cs {
      bins cs_rise = (1'b0 => 1'b1);
      bins cs_fall = (1'b1 => 1'b0);
      bins cs_stay_high = (1'b1 => 1'b1);
      bins cs_stay_low = (1'b0 => 1'b0);
    }
  endgroup


  function new(string name = "sha1_subscriber", uvm_component parent = null);
    super.new(name, parent);
    cg_sha1_interface = new();
    cg_control_commands = new();
    cg_status = new();
    cg_core_fsm = new();
    cg_w_mem = new();
    cg_digest = new();
    cg_errors = new();
    cg_back_to_back = new();
  endfunction


  virtual function void write(sha1_coverage_item t);
    item = t;

    if (item.cs)
      cg_sha1_interface.sample();

    cg_control_commands.sample();
    cg_status.sample();
    cg_core_fsm.sample();
    cg_w_mem.sample();

    if (item.status_valid)
      cg_digest.sample();

    if (item.cs)
      cg_errors.sample();

    cg_back_to_back.sample();
  endfunction


  function void report_phase(uvm_phase phase);
    `uvm_info("SHA1_COV", $sformatf(
      "cg_sha1_interface  = %0.2f%%\n",
      "cg_control_commands = %0.2f%%\n",
      "cg_status          = %0.2f%%\n",
      "cg_core_fsm        = %0.2f%%\n",
      "cg_w_mem           = %0.2f%%\n",
      "cg_digest          = %0.2f%%\n",
      "cg_errors          = %0.2f%%\n",
      "cg_back_to_back    = %0.2f%%",
      cg_sha1_interface.get_coverage(),
      cg_control_commands.get_coverage(),
      cg_status.get_coverage(),
      cg_core_fsm.get_coverage(),
      cg_w_mem.get_coverage(),
      cg_digest.get_coverage(),
      cg_errors.get_coverage(),
      cg_back_to_back.get_coverage()
    ), UVM_NONE)
  endfunction

endclass : sha1_subscriber

`endif // SHA1_SUBSCRIBER_SV

