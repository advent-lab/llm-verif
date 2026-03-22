//======================================================================
// trng_subscriber.sv
//
// UVM functional coverage collector for the TRNG.
// Modelled after sha1_subscriber: covergroups are defined inside the
// class, NO separate handle declarations, new() called in constructor.
//======================================================================

`ifndef TRNG_SUBSCRIBER_SV
`define TRNG_SUBSCRIBER_SV

class trng_subscriber extends uvm_subscriber #(trng_seq_item);
  `uvm_component_utils(trng_subscriber)

  // Transaction handle populated in write() and referenced by all
  // covergroup coverpoints.
  trng_seq_item item;

  //====================================================================
  // Address-map constants
  //====================================================================

  // Subsystem prefixes (address[11:8])
  localparam PREFIX_TRNG   = 4'h0;
  localparam PREFIX_ENT1   = 4'h5;
  localparam PREFIX_ENT2   = 4'h6;
  localparam PREFIX_MIXER  = 4'ha;
  localparam PREFIX_CSPRNG = 4'hb;

  // TRNG sub-addresses
  localparam TRNG_NAME0       = 8'h00;
  localparam TRNG_NAME1       = 8'h01;
  localparam TRNG_VERSION     = 8'h02;
  localparam TRNG_CTRL        = 8'h10;
  localparam TRNG_STATUS      = 8'h11;
  localparam TRNG_DEBUG_CTRL  = 8'h12;
  localparam TRNG_DEBUG_DELAY = 8'h13;

  // Mixer sub-addresses
  localparam MIXER_CTRL    = 8'h10;
  localparam MIXER_STATUS  = 8'h11;
  localparam MIXER_TIMEOUT = 8'h20;

  // CSPRNG sub-addresses
  localparam CSPRNG_CTRL            = 8'h10;
  localparam CSPRNG_STATUS          = 8'h11;
  localparam CSPRNG_RND_DATA        = 8'h20;
  localparam CSPRNG_NUM_ROUNDS      = 8'h40;
  localparam CSPRNG_NUM_BLOCKS_LOW  = 8'h41;
  localparam CSPRNG_NUM_BLOCKS_HIGH = 8'h42;

  // Debug mux select values
  localparam DBG_ENTROPY0 = 3'h0;
  localparam DBG_ENTROPY1 = 3'h1;
  localparam DBG_ENTROPY2 = 3'h2;
  localparam DBG_MIXER    = 3'h3;
  localparam DBG_CSPRNG   = 3'h4;


  // Sampled error-context signals preserved from the SV testbench.
  logic [3:0] sampled_prefix;
  logic       sampled_we;
  logic       sampled_error;
  logic       sampled_sec_err;

  covergroup cg_api_prefix;
	option.cross_auto_bin_max = 0;
    cp_prefix: coverpoint item.address[11:8] {
      bins trng_prefix   = {PREFIX_TRNG};
      bins ent1_prefix   = {PREFIX_ENT1};
      bins ent2_prefix   = {PREFIX_ENT2};
      bins mixer_prefix  = {PREFIX_MIXER};
      bins csprng_prefix = {PREFIX_CSPRNG};
      bins other[]       = default;
    }

    cp_rw: coverpoint item.we {
      bins read  = {0};
      bins write = {1};
    }

    // Hard cross: every prefix × read/write
    cx_prefix_rw: cross cp_prefix, cp_rw {
      bins trng_wr   = binsof(cp_prefix.trng_prefix)   && binsof(cp_rw.write);
      bins trng_rd   = binsof(cp_prefix.trng_prefix)   && binsof(cp_rw.read);
      bins ent1_wr   = binsof(cp_prefix.ent1_prefix)   && binsof(cp_rw.write);
      bins ent1_rd   = binsof(cp_prefix.ent1_prefix)   && binsof(cp_rw.read);
      bins ent2_wr   = binsof(cp_prefix.ent2_prefix)   && binsof(cp_rw.write);
      bins ent2_rd   = binsof(cp_prefix.ent2_prefix)   && binsof(cp_rw.read);
      bins mixer_wr  = binsof(cp_prefix.mixer_prefix)  && binsof(cp_rw.write);
      bins mixer_rd  = binsof(cp_prefix.mixer_prefix)  && binsof(cp_rw.read);
      bins csprng_wr = binsof(cp_prefix.csprng_prefix) && binsof(cp_rw.write);
      bins csprng_rd = binsof(cp_prefix.csprng_prefix) && binsof(cp_rw.read);
    }
  endgroup

  covergroup cg_trng_regs;
option.cross_auto_bin_max = 0;
    cp_addr: coverpoint item.address[7:0] {
      bins name0       = {TRNG_NAME0};
      bins name1       = {TRNG_NAME1};
      bins version     = {TRNG_VERSION};
      bins ctrl        = {TRNG_CTRL};
      bins status      = {TRNG_STATUS};
      bins debug_ctrl  = {TRNG_DEBUG_CTRL};
      bins debug_delay = {TRNG_DEBUG_DELAY};
      bins other[]     = default;
    }

    cp_we: coverpoint item.we {
      bins rd = {0};
      bins wr = {1};
    }

    cx_trng_addr_rw: cross cp_addr, cp_we {
      bins ctrl_wr        = binsof(cp_addr.ctrl)        && binsof(cp_we.wr);
      bins ctrl_rd        = binsof(cp_addr.ctrl)        && binsof(cp_we.rd);
      bins debug_ctrl_wr  = binsof(cp_addr.debug_ctrl)  && binsof(cp_we.wr);
      bins debug_ctrl_rd  = binsof(cp_addr.debug_ctrl)  && binsof(cp_we.rd);
      bins debug_delay_wr = binsof(cp_addr.debug_delay) && binsof(cp_we.wr);
      bins debug_delay_rd = binsof(cp_addr.debug_delay) && binsof(cp_we.rd);
    }
  endgroup

  covergroup cg_trng_ctrl_bits;
option.cross_auto_bin_max = 0;
    cp_discard: coverpoint item.discard_reg {
      bins inactive = {0};
      bins active   = {1};
    }
    cp_test_mode: coverpoint item.test_mode_reg {
      bins normal    = {0};
      bins test_mode = {1};
    }
    cx_discard_testmode: cross cp_discard, cp_test_mode {
      bins normal_op          = binsof(cp_discard.inactive)  && binsof(cp_test_mode.normal);
      bins discard_only       = binsof(cp_discard.active)    && binsof(cp_test_mode.normal);
      bins test_only          = binsof(cp_discard.inactive)  && binsof(cp_test_mode.test_mode);
      bins discard_and_test   = binsof(cp_discard.active)    && binsof(cp_test_mode.test_mode);
    }
  endgroup

  covergroup cg_debug_mux;
option.cross_auto_bin_max = 0;
    cp_mux: coverpoint item.debug_mux_reg {
      bins entropy0 = {DBG_ENTROPY0};
      bins entropy1 = {DBG_ENTROPY1};
      bins entropy2 = {DBG_ENTROPY2};
      bins mixer    = {DBG_MIXER};
      bins csprng   = {DBG_CSPRNG};
    }
    cp_dbg_update: coverpoint item.debug_update {
      bins no_update  = {0};
      bins do_update  = {1};
    }
    // Hard cross: every mux selection × item.debug_update pulse
    cx_mux_update: cross cp_mux, cp_dbg_update {
      bins ent1_update   = binsof(cp_mux.entropy1) && binsof(cp_dbg_update.do_update);
      bins ent2_update   = binsof(cp_mux.entropy2) && binsof(cp_dbg_update.do_update);
      bins mixer_update  = binsof(cp_mux.mixer)    && binsof(cp_dbg_update.do_update);
      bins csprng_update = binsof(cp_mux.csprng)   && binsof(cp_dbg_update.do_update);
    }
  endgroup

  covergroup cg_mixer_ctrl_fsm;
option.cross_auto_bin_max = 0;
    cp_state: coverpoint item.mixer_ctrl_state {
      bins idle    = {4'h0};
      bins collect = {4'h1};
      bins mix     = {4'h2};
      bins syn     = {4'h3};
      bins ack     = {4'h4};
      bins next    = {4'h5};
    }

    cp_discard_m: coverpoint item.discard_reg {
      bins no_discard = {0};
      bins discard    = {1};
    }

    // Hard cross: discard asserted in each FSM state
    cx_mixer_state_discard: cross cp_state, cp_discard_m {
      bins discard_in_collect = binsof(cp_state.collect) && binsof(cp_discard_m.discard);
      bins discard_in_mix     = binsof(cp_state.mix)     && binsof(cp_discard_m.discard);
      bins discard_in_syn     = binsof(cp_state.syn)     && binsof(cp_discard_m.discard);
      bins discard_in_ack     = binsof(cp_state.ack)     && binsof(cp_discard_m.discard);
      bins discard_in_next    = binsof(cp_state.next)    && binsof(cp_discard_m.discard);
    }

    cp_init_done: coverpoint item.init_done {
      bins not_done = {0};
      bins done     = {1};
    }

    // Hard: mixing both init and next blocks
    cx_mixer_state_initdone: cross cp_state, cp_init_done {
      bins mix_first_block = binsof(cp_state.mix) && binsof(cp_init_done.not_done);
      bins mix_next_block  = binsof(cp_state.mix) && binsof(cp_init_done.done);
    }
  endgroup

  covergroup cg_entropy_collect_fsm;
option.cross_auto_bin_max = 0;
    cp_efsm: coverpoint item.entropy_coll_state {
      bins idle      = {4'h0};
      bins src0      = {4'h1};
      bins src0_ack  = {4'h2};
      bins src1      = {4'h3};
      bins src1_ack  = {4'h4};
      bins src2      = {4'h5};
      bins src2_ack  = {4'h6};
    }

    cp_word_ctr_val: coverpoint item.word_ctr {
      bins zero      = {5'h00};
      bins mid_range = {[5'h01:5'h1e]};
      bins max_val   = {5'h1f};  // block full – hardest to hit
    }

    // Hard cross: block completion observed from each source
    cx_source_word_ctr: cross cp_efsm, cp_word_ctr_val {
      bins src0_ack_full = binsof(cp_efsm.src0_ack) && binsof(cp_word_ctr_val.max_val);
      bins src1_ack_full = binsof(cp_efsm.src1_ack) && binsof(cp_word_ctr_val.max_val);
      bins src2_ack_full = binsof(cp_efsm.src2_ack) && binsof(cp_word_ctr_val.max_val);
    }

    cp_timeout: coverpoint item.entropy_timeout_sig {
      bins no_timeout = {0};
      bins timeout    = {1};
    }

    // Hard: timeout in each source-wait state
    cx_efsm_timeout: cross cp_efsm, cp_timeout {
      bins src0_timeout = binsof(cp_efsm.src0) && binsof(cp_timeout.timeout);
      bins src1_timeout = binsof(cp_efsm.src1) && binsof(cp_timeout.timeout);
      bins src2_timeout = binsof(cp_efsm.src2) && binsof(cp_timeout.timeout);
    }
  endgroup

  covergroup cg_csprng_fsm;
option.cross_auto_bin_max = 0;
    cp_cstate: coverpoint item.csprng_ctrl_state {
      bins idle   = {4'h0};
      bins seed0  = {4'h1};
      bins nsyn   = {4'h2};
      bins seed1  = {4'h3};
      bins init0  = {4'h4};
      bins init1  = {4'h5};
      bins next0  = {4'h6};
      bins next1  = {4'h7};
      bins more   = {4'h8};
      bins cancel = {4'hf};
    }

    cp_csprng_enable: coverpoint item.csprng_enable {
      bins disabled = {0};
      bins enabled  = {1};
    }

    cp_seed_reg: coverpoint item.seed_reg {
      bins no_seed = {0};
      bins seed    = {1};
    }

    // Hard: cancel triggered from many states
    cx_csprng_state_disable: cross cp_cstate, cp_csprng_enable {
      bins cancel_from_seed0  = binsof(cp_cstate.seed0)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_nsyn   = binsof(cp_cstate.nsyn)   && binsof(cp_csprng_enable.disabled);
      bins cancel_from_seed1  = binsof(cp_cstate.seed1)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_init0  = binsof(cp_cstate.init0)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_init1  = binsof(cp_cstate.init1)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_next0  = binsof(cp_cstate.next0)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_next1  = binsof(cp_cstate.next1)  && binsof(cp_csprng_enable.disabled);
      bins cancel_from_more   = binsof(cp_cstate.more)   && binsof(cp_csprng_enable.disabled);
    }

    // Hard: seed_reg asserted mid-operation
    cx_csprng_state_seed_req: cross cp_cstate, cp_seed_reg {
      bins reseed_from_seed0 = binsof(cp_cstate.seed0) && binsof(cp_seed_reg.seed);
      bins reseed_from_init0 = binsof(cp_cstate.init0) && binsof(cp_seed_reg.seed);
      bins reseed_from_next0 = binsof(cp_cstate.next0) && binsof(cp_seed_reg.seed);
      bins reseed_from_more  = binsof(cp_cstate.more)  && binsof(cp_seed_reg.seed);
    }
  endgroup

  covergroup cg_block_ctr;
option.cross_auto_bin_max = 0;
    cp_blk_ctr: coverpoint item.block_ctr {
      bins zero      = {64'h0000000000000000};
      bins low       = {[64'h0000000000000001 : 64'h00000000000000ff]};
      bins mid       = {[64'h0000000000000100 : 64'h0ffffffffffffffe]};
      bins near_max  = {64'h0fffffffffffffff};  // one before DEFAULT_NUM_BLOCKS
      bins at_max    = {64'h1000000000000000};  // DEFAULT_NUM_BLOCKS – triggers reseed
    }
    cp_blk_max_flag: coverpoint dut.csprng_inst.block_ctr_max {
      bins not_max = {0};
      bins is_max  = {1};  // hardest bin – forces reseed path
    }
  endgroup

  covergroup cg_fifo;
    option.cross_auto_bin_max = 0;
    cp_wr_fsm: coverpoint item.fifo_wr_state {
      bins wr_idle    = {3'h0};
      bins wr_discard = {3'h7};
    }

    cp_rd_fsm: coverpoint item.fifo_rd_state {
      bins rd_idle    = {3'h0};
      bins rd_ack     = {3'h1};
      bins rd_discard = {3'h7};
    }

    cp_fifo_fill: coverpoint item.fifo_ctr_obs {
      bins empty     = {2'h0};
      bins one_entry = {2'h1};
      bins two_entry = {2'h2};
      bins full      = {2'h3};  // hardest – requires 4 writes without reads
    }

    cp_empty_flag: coverpoint item.fifo_empty {
      bins not_empty = {0};
      bins is_empty  = {1};
    }

    cp_full_flag: coverpoint item.fifo_full {
      bins not_full = {0};
      bins is_full  = {1};  // hard to hit – need 4 consecutive writes
    }

    // Hard: RD ack state while FIFO also has data
    cx_rd_fill: cross cp_rd_fsm, cp_fifo_fill {
      bins ack_when_one  = binsof(cp_rd_fsm.rd_ack) && binsof(cp_fifo_fill.one_entry);
      bins ack_when_two  = binsof(cp_rd_fsm.rd_ack) && binsof(cp_fifo_fill.two_entry);
      bins ack_when_full = binsof(cp_rd_fsm.rd_ack) && binsof(cp_fifo_fill.full);
    }

    // Hard: discard in each FSM state
    cp_fifo_discard: coverpoint dut.csprng_inst.fifo_discard {
      bins no_discard  = {0};
      bins do_discard  = {1};
    }

    cx_wr_discard: cross cp_wr_fsm, cp_fifo_discard {
      bins discard_in_idle = binsof(cp_wr_fsm.wr_idle) && binsof(cp_fifo_discard.do_discard);
    }
    cx_rd_discard: cross cp_rd_fsm, cp_fifo_discard {
      bins rd_discard_from_idle = binsof(cp_rd_fsm.rd_idle) && binsof(cp_fifo_discard.do_discard);
      bins rd_discard_from_ack  = binsof(cp_rd_fsm.rd_ack)  && binsof(cp_fifo_discard.do_discard);
    }
  endgroup

  covergroup cg_csprng_regs;
option.cross_auto_bin_max = 0;
    cp_addr: coverpoint item.address[7:0] {
      bins ctrl           = {CSPRNG_CTRL};
      bins status         = {CSPRNG_STATUS};
      bins rnd_data       = {CSPRNG_RND_DATA};
      bins num_rounds     = {CSPRNG_NUM_ROUNDS};
      bins num_blocks_low = {CSPRNG_NUM_BLOCKS_LOW};
      bins num_blocks_hi  = {CSPRNG_NUM_BLOCKS_HIGH};
      bins other[]        = default;
    }
    cp_we: coverpoint item.we {
      bins rd = {0};
      bins wr = {1};
    }
    cx_csprng_addr_rw: cross cp_addr, cp_we {
      bins rnd_data_rd       = binsof(cp_addr.rnd_data)       && binsof(cp_we.rd);
      bins ctrl_wr           = binsof(cp_addr.ctrl)           && binsof(cp_we.wr);
      bins num_rounds_wr     = binsof(cp_addr.num_rounds)     && binsof(cp_we.wr);
      bins num_blocks_low_wr = binsof(cp_addr.num_blocks_low) && binsof(cp_we.wr);
      bins num_blocks_hi_wr  = binsof(cp_addr.num_blocks_hi)  && binsof(cp_we.wr);
    }
    // Hard: reading random data when FIFO is non-empty
    cp_rnd_syn: coverpoint dut.csprng_inst.fifo_inst.rnd_syn_reg {
      bins no_data = {0};
      bins has_data = {1};
    }
    cx_rnd_data_rd_when_valid: cross cp_addr, cp_we, cp_rnd_syn {
      bins rnd_rd_when_valid = binsof(cp_addr.rnd_data) &&
                               binsof(cp_we.rd)         &&
                               binsof(cp_rnd_syn.has_data);
    }
  endgroup

  covergroup cg_mixer_regs;
option.cross_auto_bin_max = 0;
    cp_addr: coverpoint item.address[7:0] {
      bins ctrl    = {MIXER_CTRL};
      bins status  = {MIXER_STATUS};
      bins timeout = {MIXER_TIMEOUT};
      bins other[] = default;
    }
    cp_we: coverpoint item.we {
      bins rd = {0};
      bins wr = {1};
    }
    cx_mixer_addr_rw: cross cp_addr, cp_we {
      bins ctrl_wr    = binsof(cp_addr.ctrl)    && binsof(cp_we.wr);
      bins ctrl_rd    = binsof(cp_addr.ctrl)    && binsof(cp_we.rd);
      bins timeout_wr = binsof(cp_addr.timeout) && binsof(cp_we.wr);
      bins timeout_rd = binsof(cp_addr.timeout) && binsof(cp_we.rd);
    }
    // Hard: write enable/disable to mixer while mixing is active
    cp_mixer_state: coverpoint item.mixer_ctrl_state {
      bins idle_state    = {4'h0};
      bins active_states = {[4'h1:4'h5]};
    }
    cx_ctrl_wr_during_activity: cross cp_addr, cp_we, cp_mixer_state {
      bins ctrl_wr_while_active = binsof(cp_addr.ctrl)          &&
                                  binsof(cp_we.wr)               &&
                                  binsof(cp_mixer_state.active_states);
    }
  endgroup

  covergroup cg_entropy_handshake;
option.cross_auto_bin_max = 0;
    cp_ent1_enabled: coverpoint item.ent1_enabled {
      bins disabled = {0};
      bins enabled  = {1};
    }
    cp_ent1_syn: coverpoint item.ent1_syn {
      bins no_data = {0};
      bins data    = {1};
    }
    cp_ent1_ack: coverpoint item.ent1_ack {
      bins no_ack = {0};
      bins ack    = {1};
    }
    cp_ent2_enabled: coverpoint item.ent2_enabled {
      bins disabled = {0};
      bins enabled  = {1};
    }
    cp_ent2_syn: coverpoint item.ent2_syn {
      bins no_data = {0};
      bins data    = {1};
    }
    cp_ent2_ack: coverpoint item.ent2_ack {
      bins no_ack = {0};
      bins ack    = {1};
    }
    // Hard: ack asserted from each enabled source
    cx_ent1_handshake: cross cp_ent1_enabled, cp_ent1_syn, cp_ent1_ack {
      bins ent1_full_handshake = binsof(cp_ent1_enabled.enabled) &&
                                 binsof(cp_ent1_syn.data)        &&
                                 binsof(cp_ent1_ack.ack);
    }
    cx_ent2_handshake: cross cp_ent2_enabled, cp_ent2_syn, cp_ent2_ack {
      bins ent2_full_handshake = binsof(cp_ent2_enabled.enabled) &&
                                 binsof(cp_ent2_syn.data)        &&
                                 binsof(cp_ent2_ack.ack);
    }
  endgroup

  covergroup cg_errors;
option.cross_auto_bin_max = 0;
    cp_api_error: coverpoint item.error {
      bins no_error = {0};
      bins has_error = {1};
    }
    cp_security_error: coverpoint item.security_error {
      bins no_sec_error  = {0};
      bins has_sec_error = {1};
    }
    // Hard: item.error observed on each prefix
    cp_prefix_err: coverpoint sampled_prefix iff (sampled_error) {
      bins trng_err   = {PREFIX_TRNG};
      bins mixer_err  = {PREFIX_MIXER};
      bins csprng_err = {PREFIX_CSPRNG};
    }
    // Hard: item.error from write to illegal item.address
    cp_we_err: coverpoint sampled_we iff (sampled_error) {
      bins read_error  = {0};
      bins write_error = {1};
    }
  endgroup

  covergroup cg_system_state_cross;
option.cross_auto_bin_max = 0;
    cp_csprng_active: coverpoint item.csprng_ctrl_state {
      bins csprng_idle   = {4'h0};
      bins csprng_seeding = {4'h1, 4'h2, 4'h3};
      bins csprng_init    = {4'h4, 4'h5};
      bins csprng_running = {4'h6, 4'h7, 4'h8};
      bins csprng_cancel  = {4'hf};
    }
    cp_mixer_active: coverpoint item.mixer_ctrl_state {
      bins mixer_idle    = {4'h0};
      bins mixer_collect = {4'h1};
      bins mixer_hashing = {4'h2, 4'h3};
      bins mixer_syncing = {4'h4, 4'h5};
    }
    // Hard: many combinations of both FSMs simultaneously active
    cx_system_state: cross cp_csprng_active, cp_mixer_active {
      bins running_and_collecting   = binsof(cp_csprng_active.csprng_running) &&
                                      binsof(cp_mixer_active.mixer_collect);
      bins seeding_while_hashing    = binsof(cp_csprng_active.csprng_seeding) &&
                                      binsof(cp_mixer_active.mixer_hashing);
      bins seeding_while_syncing    = binsof(cp_csprng_active.csprng_seeding) &&
                                      binsof(cp_mixer_active.mixer_syncing);
      bins running_while_hashing    = binsof(cp_csprng_active.csprng_running) &&
                                      binsof(cp_mixer_active.mixer_hashing);
      bins cancel_while_collecting  = binsof(cp_csprng_active.csprng_cancel)  &&
                                      binsof(cp_mixer_active.mixer_collect);
      bins init_while_collecting    = binsof(cp_csprng_active.csprng_init)    &&
                                      binsof(cp_mixer_active.mixer_collect);
    }
  endgroup

  covergroup cg_seed_handshake;
option.cross_auto_bin_max = 0;
    cp_seed_syn: coverpoint item.seed_syn_obs {
      bins no_syn = {0};
      bins syn    = {1};
    }
    cp_seed_ack: coverpoint item.seed_ack_reg {
      bins no_ack = {0};
      bins ack    = {1};
    }
    cp_more_seed: coverpoint item.more_seed_obs {
      bins no_request = {0};
      bins requesting = {1};
    }
    // Hard: complete handshake cycle
    cx_seed_handshake: cross cp_seed_syn, cp_seed_ack, cp_more_seed {
      bins seed_request_active    = binsof(cp_more_seed.requesting) &&
                                    binsof(cp_seed_syn.no_syn);
      bins seed_available         = binsof(cp_seed_syn.syn)         &&
                                    binsof(cp_seed_ack.no_ack);
      bins seed_acked             = binsof(cp_seed_syn.syn)         &&
                                    binsof(cp_seed_ack.ack);
    }
  endgroup

  covergroup cg_debug_delay;
option.cross_auto_bin_max = 0;
    cp_delay_ctr: coverpoint item.debug_delay_ctr_reg {
      bins zero     = {32'h0};
      bins mid      = {[32'h1:32'h002625_9f]};
      bins at_delay = {32'h002625a0};  // DEFAULT_DEBUG_DELAY – triggers debug update
    }
    cp_debug_out_we: coverpoint item.debug_out_we {
      bins no_update = {0};
      bins update    = {1};  // hard – only hits once per delay period
    }
  endgroup

  covergroup cg_mixer_ctrl_write;
option.cross_auto_bin_max = 0;
    cp_enable_bit: coverpoint item.write_data[0] {
      bins mixer_off = {0};
      bins mixer_on  = {1};
    }
    cp_restart_bit: coverpoint item.write_data[1] {
      bins no_restart = {0};
      bins restart    = {1};  // hard
    }
    cx_enable_restart: cross cp_enable_bit, cp_restart_bit {
      bins enable_no_restart  = binsof(cp_enable_bit.mixer_on)  && binsof(cp_restart_bit.no_restart);
      bins disable_no_restart = binsof(cp_enable_bit.mixer_off) && binsof(cp_restart_bit.no_restart);
      bins enable_restart     = binsof(cp_enable_bit.mixer_on)  && binsof(cp_restart_bit.restart);
      bins disable_restart    = binsof(cp_enable_bit.mixer_off) && binsof(cp_restart_bit.restart);
    }
  endgroup

  covergroup cg_csprng_rounds;
option.cross_auto_bin_max = 0;
    cp_rounds: coverpoint item.num_rounds_reg {
      bins min_rounds  = {5'h08};  // 8 rounds – minimum useful ChaCha
      bins default_rnd = {5'h18};  // 24 – DEFAULT_NUM_ROUNDS
      bins max_rounds  = {5'h1f};
      bins other[]     = default;
    }
  endgroup

  covergroup cg_noise;
option.cross_auto_bin_max = 0;
    cp_noise: coverpoint item.avalanche_noise {
      bins low  = {0};
      bins high = {1};
    }
    // Hard: noise changes while entropy collection is active
    cp_ecoll_active: coverpoint item.entropy_coll_state {
      bins collecting = {[4'h1:4'h6]};
      bins idle       = {4'h0};
    }
    cx_noise_during_collect: cross cp_noise, cp_ecoll_active {
      bins noise_low_during_collect  = binsof(cp_noise.low)  && binsof(cp_ecoll_active.collecting);
      bins noise_high_during_collect = binsof(cp_noise.high) && binsof(cp_ecoll_active.collecting);
    }
  endgroup
  //====================================================================
  // Constructor — covergroups instantiated here, exactly as in
  // sha1_subscriber. No separate handle declarations needed; the
  // covergroup definition inside the class IS the type, and
  // "cg_name = new()" both creates and binds the instance.
  //====================================================================
  function new(string name = "trng_subscriber",
               uvm_component parent = null);
    super.new(name, parent);
    cg_api_prefix          = new();
    cg_trng_regs           = new();
    cg_trng_ctrl_bits      = new();
    cg_debug_mux           = new();
    cg_mixer_ctrl_fsm      = new();
    cg_entropy_collect_fsm = new();
    cg_csprng_fsm          = new();
    cg_block_ctr           = new();
    cg_fifo                = new();
    cg_csprng_regs         = new();
    cg_mixer_regs          = new();
    cg_entropy_handshake   = new();
    cg_errors              = new();
    cg_system_state_cross  = new();
    cg_seed_handshake      = new();
    cg_debug_delay         = new();
    cg_mixer_ctrl_write    = new();
    cg_csprng_rounds       = new();
    cg_noise               = new();
  endfunction : new


  //====================================================================
  // write() — called by the monitor's analysis port on every transaction
  //====================================================================
  virtual function void write(trng_seq_item t);
    item = t;

    if (item.cs) begin
      sampled_prefix = item.address[11:8];
      sampled_we     = item.we;
    end
    sampled_error   = item.error;
    sampled_sec_err = item.security_error;

    // Bus-level covergroups — always sample; each coverpoint is
    // internally gated with iff() so only valid cycles contribute.
    cg_api_prefix.sample();
    cg_trng_regs.sample();
    cg_csprng_regs.sample();
    cg_mixer_regs.sample();

    // Control register field covergroups
    cg_trng_ctrl_bits.sample();
    cg_debug_mux.sample();
    cg_debug_delay.sample();
    cg_mixer_ctrl_write.sample();
    cg_csprng_rounds.sample();

    // Always-on: error flags, noise, handshakes, block counter
    cg_errors.sample();
    cg_noise.sample();
    cg_entropy_handshake.sample();
    cg_seed_handshake.sample();
    cg_block_ctr.sample();

    // FSM and structural covergroups
    cg_mixer_ctrl_fsm.sample();
    cg_entropy_collect_fsm.sample();
    cg_csprng_fsm.sample();
    cg_fifo.sample();
    cg_system_state_cross.sample();
  endfunction : write


  //====================================================================
  // report_phase — print per-covergroup coverage summary at end of sim
  //====================================================================
  function void report_phase(uvm_phase phase);
    `uvm_info("TRNG_COV", $sformatf(
      "\n==========================================\n",
      "TRNG Subscriber Coverage Summary\n",
      "==========================================\n",
      "  cg_api_prefix          : %0.2f%%\n",
      "  cg_trng_regs           : %0.2f%%\n",
      "  cg_trng_ctrl_bits      : %0.2f%%\n",
      "  cg_debug_mux           : %0.2f%%\n",
      "  cg_mixer_ctrl_fsm      : %0.2f%%\n",
      "  cg_entropy_collect_fsm : %0.2f%%\n",
      "  cg_csprng_fsm          : %0.2f%%\n",
      "  cg_block_ctr           : %0.2f%%\n",
      "  cg_fifo                : %0.2f%%\n",
      "  cg_csprng_regs         : %0.2f%%\n",
      "  cg_mixer_regs          : %0.2f%%\n",
      "  cg_entropy_handshake   : %0.2f%%\n",
      "  cg_errors              : %0.2f%%\n",
      "  cg_system_state_cross  : %0.2f%%\n",
      "  cg_seed_handshake      : %0.2f%%\n",
      "  cg_debug_delay         : %0.2f%%\n",
      "  cg_mixer_ctrl_write    : %0.2f%%\n",
      "  cg_csprng_rounds       : %0.2f%%\n",
      "  cg_noise               : %0.2f%%\n",
      "==========================================",
      cg_api_prefix.get_coverage(),
      cg_trng_regs.get_coverage(),
      cg_trng_ctrl_bits.get_coverage(),
      cg_debug_mux.get_coverage(),
      cg_mixer_ctrl_fsm.get_coverage(),
      cg_entropy_collect_fsm.get_coverage(),
      cg_csprng_fsm.get_coverage(),
      cg_block_ctr.get_coverage(),
      cg_fifo.get_coverage(),
      cg_csprng_regs.get_coverage(),
      cg_mixer_regs.get_coverage(),
      cg_entropy_handshake.get_coverage(),
      cg_errors.get_coverage(),
      cg_system_state_cross.get_coverage(),
      cg_seed_handshake.get_coverage(),
      cg_debug_delay.get_coverage(),
      cg_mixer_ctrl_write.get_coverage(),
      cg_csprng_rounds.get_coverage(),
      cg_noise.get_coverage()
    ), UVM_NONE)
  endfunction : report_phase

endclass : trng_subscriber

`endif // TRNG_SUBSCRIBER_SV

