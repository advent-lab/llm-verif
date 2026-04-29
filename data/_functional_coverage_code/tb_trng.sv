`timescale 1ns/1ps

module tb_llm;

  // -----------------------------------------------------------------------
  // Address map constants
  // -----------------------------------------------------------------------
  // Top-level prefix  (address[11:8])
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

  // MIXER sub-addresses
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

  // Debug mux selections (written into TRNG_DEBUG_CTRL[2:0])
  localparam DBG_ENTROPY0 = 3'h0;
  localparam DBG_ENTROPY1 = 3'h1;
  localparam DBG_ENTROPY2 = 3'h2;
  localparam DBG_MIXER    = 3'h3;
  localparam DBG_CSPRNG   = 3'h4;

  localparam CLK_PERIOD = 10; // 100 MHz

  // -----------------------------------------------------------------------
  // DUT interface signals
  // -----------------------------------------------------------------------
  reg        clk;
  reg        reset_n;
  reg        avalanche_noise;
  reg        cs;
  reg        we;
  reg [11:0] address;
  reg [31:0] write_data;
  wire [31:0] read_data;
  wire        error;
  wire  [7:0] debug;
  reg         debug_update;
  wire        security_error;

  // -----------------------------------------------------------------------
  // DUT instantiation
  // -----------------------------------------------------------------------
  trng dut (
    .clk            (clk),
    .reset_n        (reset_n),
    .avalanche_noise(avalanche_noise),
    .cs             (cs),
    .we             (we),
    .address        (address),
    .write_data     (write_data),
    .read_data      (read_data),
    .error          (error),
    .debug          (debug),
    .debug_update   (debug_update),
    .security_error (security_error)
  );

  // -----------------------------------------------------------------------
  // Clock generation
  // -----------------------------------------------------------------------
  initial clk = 0;
  always  #(CLK_PERIOD/2) clk = ~clk;

  // -----------------------------------------------------------------------
  // Sampled signals for context-aware coverage
  // (all derived from interface signals only — no DUT hierarchy)
  // -----------------------------------------------------------------------
  reg [3:0] sampled_prefix;
  reg       sampled_we;
  reg [7:0] sampled_subaddr;
  reg       sampled_error;
  reg       sampled_sec_err;

  always @(posedge clk) begin
    if (cs) begin
      sampled_prefix  <= address[11:8];
      sampled_we      <= we;
      sampled_subaddr <= address[7:0];
    end
    sampled_error   <= error;
    sampled_sec_err <= security_error;
  end

  // =========================================================================
  // COVERGROUPS  —  all coverpoints reference only DUT interface signals
  // =========================================================================

  // -------------------------------------------------------------------------
  // 1. API address prefix × read/write — which subsystem is accessed
  // -------------------------------------------------------------------------
  covergroup cg_api_prefix @(posedge clk iff cs);
    option.cross_auto_bin_max = 0;

    cp_prefix: coverpoint address[11:8] {
      bins trng_prefix   = {PREFIX_TRNG};
      bins ent1_prefix   = {PREFIX_ENT1};
      bins ent2_prefix   = {PREFIX_ENT2};
      bins mixer_prefix  = {PREFIX_MIXER};
      bins csprng_prefix = {PREFIX_CSPRNG};
      bins other[]       = default;
    }

    cp_rw: coverpoint we {
      bins read  = {1'b0};
      bins write = {1'b1};
    }

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

  // -------------------------------------------------------------------------
  // 2. TRNG register addresses × read/write
  // -------------------------------------------------------------------------
  covergroup cg_trng_regs @(posedge clk iff (cs && address[11:8] == PREFIX_TRNG));
    option.cross_auto_bin_max = 0;

    cp_addr: coverpoint address[7:0] {
      bins name0       = {TRNG_NAME0};
      bins name1       = {TRNG_NAME1};
      bins version     = {TRNG_VERSION};
      bins ctrl        = {TRNG_CTRL};
      bins status      = {TRNG_STATUS};
      bins debug_ctrl  = {TRNG_DEBUG_CTRL};
      bins debug_delay = {TRNG_DEBUG_DELAY};
      bins other[]     = default;
    }

    cp_we: coverpoint we {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    cx_trng_addr_rw: cross cp_addr, cp_we {
      bins ctrl_wr        = binsof(cp_addr.ctrl)        && binsof(cp_we.wr);
      bins ctrl_rd        = binsof(cp_addr.ctrl)        && binsof(cp_we.rd);
      bins status_rd      = binsof(cp_addr.status)      && binsof(cp_we.rd);
      bins debug_ctrl_wr  = binsof(cp_addr.debug_ctrl)  && binsof(cp_we.wr);
      bins debug_ctrl_rd  = binsof(cp_addr.debug_ctrl)  && binsof(cp_we.rd);
      bins debug_delay_wr = binsof(cp_addr.debug_delay) && binsof(cp_we.wr);
      bins debug_delay_rd = binsof(cp_addr.debug_delay) && binsof(cp_we.rd);
      bins name0_rd       = binsof(cp_addr.name0)       && binsof(cp_we.rd);
      bins version_rd     = binsof(cp_addr.version)     && binsof(cp_we.rd);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 3. TRNG_CTRL write — enable, test-mode and discard bit combinations
  // -------------------------------------------------------------------------
  covergroup cg_trng_ctrl_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_TRNG && address[7:0] == TRNG_CTRL));
    option.cross_auto_bin_max = 0;

    cp_enable: coverpoint write_data[0] {
      bins disable = {1'b0};
      bins enable  = {1'b1};
    }

    cp_test_mode: coverpoint write_data[1] {
      bins normal    = {1'b0};
      bins test_mode = {1'b1};
    }

    cp_discard: coverpoint write_data[2] {
      bins no_discard = {1'b0};
      bins discard    = {1'b1};
    }

    cx_enable_testmode: cross cp_enable, cp_test_mode {
      bins enabled_normal  = binsof(cp_enable.enable)  && binsof(cp_test_mode.normal);
      bins enabled_test    = binsof(cp_enable.enable)  && binsof(cp_test_mode.test_mode);
      bins disabled_normal = binsof(cp_enable.disable) && binsof(cp_test_mode.normal);
      bins disabled_test   = binsof(cp_enable.disable) && binsof(cp_test_mode.test_mode);
    }

    cx_discard_mode: cross cp_discard, cp_test_mode {
      bins discard_normal = binsof(cp_discard.discard) && binsof(cp_test_mode.normal);
      bins discard_test   = binsof(cp_discard.discard) && binsof(cp_test_mode.test_mode);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 4. TRNG_DEBUG_CTRL write — which debug source is muxed out
  // -------------------------------------------------------------------------
  covergroup cg_debug_ctrl_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_TRNG && address[7:0] == TRNG_DEBUG_CTRL));
    option.cross_auto_bin_max = 0;

    cp_dbg_src: coverpoint write_data[2:0] {
      bins entropy0 = {DBG_ENTROPY0};
      bins entropy1 = {DBG_ENTROPY1};
      bins entropy2 = {DBG_ENTROPY2};
      bins mixer    = {DBG_MIXER};
      bins csprng   = {DBG_CSPRNG};
      bins other[]  = default;
    }
  endgroup

  // -------------------------------------------------------------------------
  // 5. TRNG_DEBUG_DELAY write — delay timer value ranges
  // -------------------------------------------------------------------------
  covergroup cg_debug_delay_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_TRNG && address[7:0] == TRNG_DEBUG_DELAY));
    option.cross_auto_bin_max = 0;

    cp_delay_val: coverpoint write_data {
      bins zero_delay  = {32'h0};
      bins short_delay = {[32'h00000001:32'h0000FFFF]};
      bins mid_delay   = {[32'h00010000:32'h002624FF]};
      bins dflt_delay  = {32'h002625A0};   // DEFAULT_DEBUG_DELAY value
      bins long_delay  = {[32'h002625A1:32'hFFFFFFFF]};
    }
  endgroup

  // -------------------------------------------------------------------------
  // 6. TRNG_STATUS read — ready bit patterns and transitions
  // -------------------------------------------------------------------------
  covergroup cg_trng_status_read @(posedge clk iff
      (cs && !we && address[11:8] == PREFIX_TRNG && address[7:0] == TRNG_STATUS));
    option.cross_auto_bin_max = 0;

    cp_ready: coverpoint read_data[0] {
      bins not_ready = {1'b0};
      bins ready     = {1'b1};
    }

    cp_ready_trans: coverpoint read_data[0] {
      bins became_ready   = (1'b0 => 1'b1);
      bins became_unready = (1'b1 => 1'b0);
      bins stay_ready     = (1'b1 => 1'b1);
      bins stay_unready   = (1'b0 => 1'b0);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 7. MIXER register addresses × read/write
  // -------------------------------------------------------------------------
  covergroup cg_mixer_regs @(posedge clk iff (cs && address[11:8] == PREFIX_MIXER));
    option.cross_auto_bin_max = 0;

    cp_addr: coverpoint address[7:0] {
      bins ctrl    = {MIXER_CTRL};
      bins status  = {MIXER_STATUS};
      bins timeout = {MIXER_TIMEOUT};
      bins other[] = default;
    }

    cp_we: coverpoint we {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    cx_mixer_addr_rw: cross cp_addr, cp_we {
      bins ctrl_wr    = binsof(cp_addr.ctrl)    && binsof(cp_we.wr);
      bins ctrl_rd    = binsof(cp_addr.ctrl)    && binsof(cp_we.rd);
      bins status_rd  = binsof(cp_addr.status)  && binsof(cp_we.rd);
      bins timeout_wr = binsof(cp_addr.timeout) && binsof(cp_we.wr);
      bins timeout_rd = binsof(cp_addr.timeout) && binsof(cp_we.rd);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 8. MIXER_CTRL write — enable and restart bit combinations
  // -------------------------------------------------------------------------
  covergroup cg_mixer_ctrl_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_MIXER && address[7:0] == MIXER_CTRL));
    option.cross_auto_bin_max = 0;

    cp_enable_bit: coverpoint write_data[0] {
      bins mixer_off = {1'b0};
      bins mixer_on  = {1'b1};
    }

    cp_restart_bit: coverpoint write_data[1] {
      bins no_restart = {1'b0};
      bins restart    = {1'b1};
    }

    cx_enable_restart: cross cp_enable_bit, cp_restart_bit {
      bins enable_no_restart  = binsof(cp_enable_bit.mixer_on)  && binsof(cp_restart_bit.no_restart);
      bins disable_no_restart = binsof(cp_enable_bit.mixer_off) && binsof(cp_restart_bit.no_restart);
      bins enable_restart     = binsof(cp_enable_bit.mixer_on)  && binsof(cp_restart_bit.restart);
      bins disable_restart    = binsof(cp_enable_bit.mixer_off) && binsof(cp_restart_bit.restart);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 9. MIXER_STATUS read — status bit patterns and transitions
  // -------------------------------------------------------------------------
  covergroup cg_mixer_status_read @(posedge clk iff
      (cs && !we && address[11:8] == PREFIX_MIXER && address[7:0] == MIXER_STATUS));
    option.cross_auto_bin_max = 0;

    cp_mixer_ready: coverpoint read_data[0] {
      bins not_ready = {1'b0};
      bins ready     = {1'b1};
    }

    cp_mixer_ready_trans: coverpoint read_data[0] {
      bins became_ready   = (1'b0 => 1'b1);
      bins became_unready = (1'b1 => 1'b0);
      bins stay_ready     = (1'b1 => 1'b1);
      bins stay_busy      = (1'b0 => 1'b0);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 10. CSPRNG register addresses × read/write
  // -------------------------------------------------------------------------
  covergroup cg_csprng_regs @(posedge clk iff (cs && address[11:8] == PREFIX_CSPRNG));
    option.cross_auto_bin_max = 0;

    cp_addr: coverpoint address[7:0] {
      bins ctrl           = {CSPRNG_CTRL};
      bins status         = {CSPRNG_STATUS};
      bins rnd_data       = {CSPRNG_RND_DATA};
      bins num_rounds     = {CSPRNG_NUM_ROUNDS};
      bins num_blocks_low = {CSPRNG_NUM_BLOCKS_LOW};
      bins num_blocks_hi  = {CSPRNG_NUM_BLOCKS_HIGH};
      bins other[]        = default;
    }

    cp_we: coverpoint we {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    cx_csprng_addr_rw: cross cp_addr, cp_we {
      bins rnd_data_rd       = binsof(cp_addr.rnd_data)       && binsof(cp_we.rd);
      bins ctrl_wr           = binsof(cp_addr.ctrl)           && binsof(cp_we.wr);
      bins ctrl_rd           = binsof(cp_addr.ctrl)           && binsof(cp_we.rd);
      bins status_rd         = binsof(cp_addr.status)         && binsof(cp_we.rd);
      bins num_rounds_wr     = binsof(cp_addr.num_rounds)     && binsof(cp_we.wr);
      bins num_blocks_low_wr = binsof(cp_addr.num_blocks_low) && binsof(cp_we.wr);
      bins num_blocks_hi_wr  = binsof(cp_addr.num_blocks_hi)  && binsof(cp_we.wr);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 11. CSPRNG_CTRL write — enable and re-seed bit combinations
  // -------------------------------------------------------------------------
  covergroup cg_csprng_ctrl_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_CTRL));
    option.cross_auto_bin_max = 0;

    cp_enable: coverpoint write_data[0] {
      bins csprng_off = {1'b0};
      bins csprng_on  = {1'b1};
    }

    cp_seed: coverpoint write_data[1] {
      bins no_seed = {1'b0};
      bins seed    = {1'b1};
    }

    cx_enable_seed: cross cp_enable, cp_seed {
      bins on_no_seed  = binsof(cp_enable.csprng_on)  && binsof(cp_seed.no_seed);
      bins on_seed     = binsof(cp_enable.csprng_on)  && binsof(cp_seed.seed);
      bins off_no_seed = binsof(cp_enable.csprng_off) && binsof(cp_seed.no_seed);
      bins off_seed    = binsof(cp_enable.csprng_off) && binsof(cp_seed.seed);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 12. CSPRNG_STATUS read — ready and data-available bit patterns
  // -------------------------------------------------------------------------
  covergroup cg_csprng_status_read @(posedge clk iff
      (cs && !we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_STATUS));
    option.cross_auto_bin_max = 0;

    cp_ready: coverpoint read_data[0] {
      bins not_ready = {1'b0};
      bins ready     = {1'b1};
    }

    cp_data_avail: coverpoint read_data[1] {
      bins no_data   = {1'b0};
      bins has_data  = {1'b1};
    }

    cp_ready_trans: coverpoint read_data[0] {
      bins became_ready   = (1'b0 => 1'b1);
      bins became_unready = (1'b1 => 1'b0);
      bins stay_ready     = (1'b1 => 1'b1);
      bins stay_busy      = (1'b0 => 1'b0);
    }

    // Ready and data available in combination
    cx_ready_data: cross cp_ready, cp_data_avail {
      bins ready_with_data    = binsof(cp_ready.ready)     && binsof(cp_data_avail.has_data);
      bins ready_no_data      = binsof(cp_ready.ready)     && binsof(cp_data_avail.no_data);
      bins not_ready_has_data = binsof(cp_ready.not_ready) && binsof(cp_data_avail.has_data);
      bins not_ready_no_data  = binsof(cp_ready.not_ready) && binsof(cp_data_avail.no_data);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 13. CSPRNG_RND_DATA read — random output value distribution
  // -------------------------------------------------------------------------
  covergroup cg_csprng_rnd_read @(posedge clk iff
      (cs && !we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_RND_DATA));
    option.cross_auto_bin_max = 0;

    cp_rnd_val: coverpoint read_data {
      bins all_zeros = {32'h00000000};
      bins all_ones  = {32'hFFFFFFFF};
      bins q1        = {[32'h00000001:32'h3FFFFFFF]};
      bins q2        = {[32'h40000000:32'h7FFFFFFF]};
      bins q3        = {[32'h80000000:32'hBFFFFFFF]};
      bins q4        = {[32'hC0000000:32'hFFFFFFFE]};
    }

    cp_rnd_trans: coverpoint read_data[31] {
      bins msb_low  = {1'b0};
      bins msb_high = {1'b1};
    }
  endgroup

  // -------------------------------------------------------------------------
  // 14. CSPRNG_NUM_ROUNDS write — ChaCha round count values
  // -------------------------------------------------------------------------
  covergroup cg_csprng_rounds_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_NUM_ROUNDS));
    option.cross_auto_bin_max = 0;

    cp_rounds: coverpoint write_data[4:0] {
      bins min_rounds  = {5'h08};   // 8 rounds (minimum ChaCha)
      bins mid_rounds  = {[5'h09:5'h17]};
      bins default_rnd = {5'h18};   // 24 rounds (DEFAULT_NUM_ROUNDS)
      bins max_rounds  = {5'h1f};
      bins other[]     = default;
    }
  endgroup

  // -------------------------------------------------------------------------
  // 15. CSPRNG_NUM_BLOCKS_LOW write — reseed threshold low-word values
  // -------------------------------------------------------------------------
  covergroup cg_csprng_blocks_low_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_NUM_BLOCKS_LOW));
    option.cross_auto_bin_max = 0;

    cp_blocks_low: coverpoint write_data {
      bins zero        = {32'h00000000};
      bins small_count = {[32'h00000001:32'h000000FF]};
      bins mid_count   = {[32'h00000100:32'h0FFFFFFF]};
      bins default_val = {32'h10000000};   // DEFAULT_NUM_BLOCKS low word
      bins large_count = {[32'h10000001:32'hFFFFFFFF]};
    }
  endgroup

  // -------------------------------------------------------------------------
  // 16. CSPRNG_NUM_BLOCKS_HIGH write — reseed threshold high-word values
  // -------------------------------------------------------------------------
  covergroup cg_csprng_blocks_high_write @(posedge clk iff
      (cs && we && address[11:8] == PREFIX_CSPRNG && address[7:0] == CSPRNG_NUM_BLOCKS_HIGH));
    option.cross_auto_bin_max = 0;

    cp_blocks_high: coverpoint write_data {
      bins zero        = {32'h00000000};
      bins nonzero[]   = default;
    }
  endgroup

  // -------------------------------------------------------------------------
  // 17. Debug output — debug[7:0] value patterns and debug_update input
  // -------------------------------------------------------------------------
  covergroup cg_debug_output @(posedge clk);
    option.cross_auto_bin_max = 0;

    cp_debug: coverpoint debug {
      bins all_zero  = {8'h00};
      bins all_ones  = {8'hFF};
      bins low_val   = {[8'h01:8'h3F]};
      bins mid_val   = {[8'h40:8'hBF]};
      bins high_val  = {[8'hC0:8'hFE]};
    }

    cp_debug_update: coverpoint debug_update {
      bins no_update = {1'b0};
      bins update    = {1'b1};
    }

    cp_debug_update_trans: coverpoint debug_update {
      bins update_pulse   = (1'b0 => 1'b1);
      bins update_release = (1'b1 => 1'b0);
    }

    // Debug value seen at the moment of an update pulse
    cx_debug_at_update: cross cp_debug, cp_debug_update {
      bins update_nonzero = binsof(cp_debug_update.update) && !binsof(cp_debug.all_zero);
      bins update_low     = binsof(cp_debug_update.update) && binsof(cp_debug.low_val);
      bins update_mid     = binsof(cp_debug_update.update) && binsof(cp_debug.mid_val);
      bins update_high    = binsof(cp_debug_update.update) && binsof(cp_debug.high_val);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 18. Avalanche noise input — entropy source toggle patterns
  // -------------------------------------------------------------------------
  covergroup cg_noise @(posedge clk);
    option.cross_auto_bin_max = 0;

    cp_noise: coverpoint avalanche_noise {
      bins low  = {1'b0};
      bins high = {1'b1};
    }

    cp_noise_trans: coverpoint avalanche_noise {
      bins noise_rise  = (1'b0 => 1'b1);
      bins noise_fall  = (1'b1 => 1'b0);
      bins noise_high  = (1'b1 => 1'b1);
      bins noise_low   = (1'b0 => 1'b0);
    }

    // Noise level while a register transaction is in flight
    cp_cs_active: coverpoint cs {
      bins cs_off = {1'b0};
      bins cs_on  = {1'b1};
    }

    cx_noise_cs: cross cp_noise, cp_cs_active {
      bins noise_high_cs = binsof(cp_noise.high) && binsof(cp_cs_active.cs_on);
      bins noise_low_cs  = binsof(cp_noise.low)  && binsof(cp_cs_active.cs_on);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 19. Error and security_error output coverage with address context
  // -------------------------------------------------------------------------
  covergroup cg_errors @(posedge clk);
    option.cross_auto_bin_max = 0;

    cp_error: coverpoint error {
      bins no_error  = {1'b0};
      bins has_error = {1'b1};
    }

    cp_sec_error: coverpoint security_error {
      bins no_sec_err  = {1'b0};
      bins has_sec_err = {1'b1};
    }

    // Error observed from each address prefix (sampled_prefix is derived
    // from address[11:8] when cs was last active — no DUT hierarchy)
    cp_err_prefix: coverpoint sampled_prefix iff (sampled_error) {
      bins trng_err   = {PREFIX_TRNG};
      bins ent1_err   = {PREFIX_ENT1};
      bins ent2_err   = {PREFIX_ENT2};
      bins mixer_err  = {PREFIX_MIXER};
      bins csprng_err = {PREFIX_CSPRNG};
    }

    // Error on read vs write
    cp_err_rw: coverpoint sampled_we iff (sampled_error) {
      bins read_error  = {1'b0};
      bins write_error = {1'b1};
    }

    // Both error types simultaneously
    cx_both_errors: cross cp_error, cp_sec_error {
      bins api_err_only = binsof(cp_error.has_error)  && binsof(cp_sec_error.no_sec_err);
      bins sec_err_only = binsof(cp_error.no_error)   && binsof(cp_sec_error.has_sec_err);
      bins both_errors  = binsof(cp_error.has_error)  && binsof(cp_sec_error.has_sec_err);
    }

    // Security error transitions (latching / clearing)
    cp_sec_err_trans: coverpoint security_error {
      bins sec_err_rise  = (1'b0 => 1'b1);
      bins sec_err_hold  = (1'b1 => 1'b1);
      bins sec_err_clear = (1'b1 => 1'b0);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 20. CS transaction patterns — access sequencing
  // -------------------------------------------------------------------------
  covergroup cg_cs_transactions @(posedge clk);
    option.cross_auto_bin_max = 0;

    cp_cs: coverpoint cs {
      bins inactive = {1'b0};
      bins active   = {1'b1};
    }

    cp_cs_trans: coverpoint cs {
      bins cs_rise      = (1'b0 => 1'b1);   // start of new transaction
      bins cs_fall      = (1'b1 => 1'b0);   // end of transaction
      bins cs_sustained = (1'b1 => 1'b1);   // back-to-back access
      bins cs_idle      = (1'b0 => 1'b0);   // inter-transaction gap
    }

    cp_we: coverpoint we {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    // Active transaction type
    cx_cs_we: cross cp_cs, cp_we {
      bins active_write = binsof(cp_cs.active) && binsof(cp_we.wr);
      bins active_read  = binsof(cp_cs.active) && binsof(cp_we.rd);
    }
  endgroup

  // =========================================================================
  // Covergroup instantiation
  // =========================================================================
  cg_api_prefix              cov_api_prefix;
  cg_trng_regs               cov_trng_regs;
  cg_trng_ctrl_write         cov_trng_ctrl_write;
  cg_debug_ctrl_write        cov_debug_ctrl_write;
  cg_debug_delay_write       cov_debug_delay_write;
  cg_trng_status_read        cov_trng_status_read;
  cg_mixer_regs              cov_mixer_regs;
  cg_mixer_ctrl_write        cov_mixer_ctrl_write;
  cg_mixer_status_read       cov_mixer_status_read;
  cg_csprng_regs             cov_csprng_regs;
  cg_csprng_ctrl_write       cov_csprng_ctrl_write;
  cg_csprng_status_read      cov_csprng_status_read;
  cg_csprng_rnd_read         cov_csprng_rnd_read;
  cg_csprng_rounds_write     cov_csprng_rounds_write;
  cg_csprng_blocks_low_write cov_csprng_blocks_low_write;
  cg_csprng_blocks_high_write cov_csprng_blocks_high_write;
  cg_debug_output            cov_debug_output;
  cg_noise                   cov_noise;
  cg_errors                  cov_errors;
  cg_cs_transactions         cov_cs_transactions;

  initial begin
    cov_api_prefix               = new();
    cov_trng_regs                = new();
    cov_trng_ctrl_write          = new();
    cov_debug_ctrl_write         = new();
    cov_debug_delay_write        = new();
    cov_trng_status_read         = new();
    cov_mixer_regs               = new();
    cov_mixer_ctrl_write         = new();
    cov_mixer_status_read        = new();
    cov_csprng_regs              = new();
    cov_csprng_ctrl_write        = new();
    cov_csprng_status_read       = new();
    cov_csprng_rnd_read          = new();
    cov_csprng_rounds_write      = new();
    cov_csprng_blocks_low_write  = new();
    cov_csprng_blocks_high_write = new();
    cov_debug_output             = new();
    cov_noise                    = new();
    cov_errors                   = new();
    cov_cs_transactions          = new();
  end

  // BEGIN_STIMULUS
  initial begin
    // Stimulus goes here

    $finish;
  end
  // END_STIMULUS

  // =========================================================================
  // Timeout watchdog
  // =========================================================================
  initial begin
    #5_000_000; // 5 ms at 1 ns resolution
    $display("WATCHDOG TIMEOUT – simulation did not finish");
    $finish;
  end

endmodule
