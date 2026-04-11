//======================================================================
// trng_test.sv
//
// UVM test classes for the TRNG.
// trng_agent and trng_env are defined in their own files
// (trng_agent.sv, trng_env.sv) and must not be redeclared here.
//
// Component hierarchy:
//
//   trng_test  (uvm_test)
//   └── trng_env  (uvm_env)
//       ├── trng_agent  (uvm_agent)
//       │   ├── trng_driver    (uvm_driver)
//       │   ├── trng_monitor   (uvm_monitor)
//       │   └── uvm_sequencer  (uvm_sequencer)
//       └── trng_coverage_subscriber  (uvm_subscriber)
//
// Test classes (all extend trng_base_test):
//
//   trng_tc1_init_test
//     Full bringup via trng_init_seq: reset, identity reads,
//     round/block config, enable CSPRNG then mixer.
//
//   trng_tc2_rnd_gen_test
//     After init, poll and collect 16 random 32-bit words.
//     Uses the low num_blocks setting from tb_trng.v (value 2) so
//     the reseed path fires quickly during the collection loop.
//
//   trng_tc3_rounds_sweep_test
//     Re-initialises and exercises 20, 24, and 32 round counts,
//     collecting a word at each setting to confirm the CSPRNG
//     continues operating after reconfiguration.
//
//   trng_tc4_debug_mode_test
//     Exercises every debug mux source (0-4) with debug_update
//     pulses; verifies the discard flush path between observations.
//
//   trng_tc5_test_mode_test
//     Enters and exits test mode, verifying that the forced-reseed
//     path executes correctly on exit.
//
//   trng_tc6_discard_test
//     Issues discard while the CSPRNG is generating, then
//     re-enables and confirms recovery to normal operation.
//
//   trng_tc7_rand_access_test
//     Fully-constrained random bus access regression.
//     Runs after a clean init so the DUT is in a known good state.
//
//   trng_full_regression_test
//     Runs every test case in sequence, separated by inter-test
//     resets, providing a single pass/fail regression entry point.
//======================================================================

`ifndef TRNG_TEST_SV
`define TRNG_TEST_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

//======================================================================
// trng_base_test
// Common base for all TRNG test classes.
// Sets the virtual interface in the config DB and provides the
// run_idle_cycles() helper used between test phases.
//======================================================================
class trng_base_test extends uvm_test;
  `uvm_component_utils(trng_base_test)

  trng_env env;

  virtual trng_if vif;

  // Clock period in time units (ns at 1ns timescale, 100 MHz)
  localparam int CLK_PERIOD_NS = 10;

  function new(string name, uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    if(!uvm_config_db#(virtual trng_if)::get(this,"","vif",vif))
        `uvm_error("trng_base_test","Can't get vif from the config db")
    uvm_config_db#(virtual trng_if)::set(this,"env","vif",vif);

    env = trng_env::type_id::create("env", this);
  endfunction : build_phase

  //--------------------------------------------------------------------
  // run_seq
  // Convenience wrapper: start a sequence on the agent's sequencer
  // and wait for it to complete before returning.
  //--------------------------------------------------------------------
  task run_seq(uvm_sequence_base seq);
    seq.start(env.agent.sqr);
  endtask : run_seq

  //--------------------------------------------------------------------
  // separator
  // Prints a prominent banner between test cases for log readability.
  //--------------------------------------------------------------------
  function void separator(string tc_name);
    `uvm_info(get_type_name(), $sformatf(
      "\n╔══════════════════════════════════════════════╗\n║  %-44s  ║\n╚══════════════════════════════════════════════╝",
      tc_name), UVM_NONE)
  endfunction : separator

endclass : trng_base_test


//======================================================================
// trng_idle_seq
// Sends n idle (cs=0, we=0, reset_n=1) items through the sequencer.
// Used by all test classes as an inter-phase delay.
//
// The TRNG's internal pipelines have significant latency:
//   SHA-512:  ~80+ clock cycles per 1024-bit block compression
//   ChaCha:   20-32 rounds × pipeline depth per keystream block
//   Entropy:  ring-oscillator / avalanche rate-limited
// A 200-cycle inter-phase window covers all of these safely.
//======================================================================
class trng_idle_seq extends trng_base_seq;
  `uvm_object_utils(trng_idle_seq)

  int unsigned num_cycles = 200;  // Default: 200 idle clocks

  function new(string name = "trng_idle_seq");
    super.new(name);
  endfunction : new

  task body();
    repeat (num_cycles)
      send_item(.cs_i(1'b0), .we_i(1'b0),
                .address_i(12'h0), .write_data_i(32'h0));
  endtask : body

endclass : trng_idle_seq


//======================================================================
// TC1 — Full initialisation
//
// Exercises trng_init_seq end-to-end:
//   reset → identity register reads → round config → block config
//   → enable CSPRNG → enable mixer.
//
// Pass criteria (checked via log messages from trng_init_seq):
//   NAME0   == 32'h74726e67  ("trng")
//   NAME1   == 32'h20202020  ("    ")
//   VERSION == 32'h302e3031  ("0.01")
//======================================================================
class trng_tc1_init_test extends trng_base_test;
  `uvm_component_utils(trng_tc1_init_test)

  function new(string name = "trng_tc1_init_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq  init_seq;
    trng_idle_seq  idle_seq;

    phase.raise_objection(this);
    separator("TC1: Full Initialisation");

    // Bringup with default 24 ChaCha rounds and DEFAULT_NUM_BLOCKS
    init_seq = trng_init_seq::type_id::create("init_seq");
    init_seq.chacha_rounds   = 24;
    init_seq.num_blocks_high = 32'h1000_0000;  // 2**60 blocks
    init_seq.num_blocks_low  = 32'h0000_0000;
    run_seq(init_seq);

    // Allow the mixer and CSPRNG to begin warm-up processing.
    // The SHA-512 core takes O(80) cycles per block; give the entropy
    // sources time to provide their first 1024-bit block.
    idle_seq = trng_idle_seq::type_id::create("idle_after_init");
    idle_seq.num_cycles = 200;
    run_seq(idle_seq);

    `uvm_info(get_type_name(), "TC1 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc1_init_test


//======================================================================
// TC2 — Random number generation and forced reseed
//
// After a full init, sets num_blocks to 2 (matching tb_trng.v tc1)
// so the reseed path fires every 2 keystream blocks. Then reads 16
// random words, verifying the FIFO fills and drains correctly and
// that the CSPRNG reseeds without stalling.
//======================================================================
class trng_tc2_rnd_gen_test extends trng_base_test;
  `uvm_component_utils(trng_tc2_rnd_gen_test)

  function new(string name = "trng_tc2_rnd_gen_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq           init_seq;
    trng_set_num_blocks_seq blocks_seq;
    trng_idle_seq           idle_seq;
    trng_read_rnd_seq       rnd_seq;

    phase.raise_objection(this);
    separator("TC2: Random Number Generation + Forced Reseed");

    // --- Initialise with default round count -----------------------
    init_seq = trng_init_seq::type_id::create("init_seq");
    init_seq.chacha_rounds = 24;
    run_seq(init_seq);

    // --- Reconfigure num_blocks to 2 to force rapid reseeding ------
    // Matches tb_trng.v:
    //   write_word({CSPRNG_PREFIX, ADDR_CSPRNG_NUM_BLOCKS_LOW}, 32'h2)
    //   write_word({CSPRNG_PREFIX, ADDR_CSPRNG_NUM_BLOCKS_HIGH}, 32'h0)
    blocks_seq = trng_set_num_blocks_seq::type_id::create("blocks_seq");
    blocks_seq.num_blocks_low  = 32'h0000_0002;
    blocks_seq.num_blocks_high = 32'h0000_0000;
    run_seq(blocks_seq);

    // --- Wait for the CSPRNG to complete initial seeding -----------
    // The mixer needs to accumulate and hash 1024 bits twice (two
    // 512-bit digests for the ChaCha seed). With entropy sources
    // running at bus-speed, allow a generous window that covers
    // SHA-512 compression cycles + ChaCha init cycles.
    idle_seq = trng_idle_seq::type_id::create("idle_warm");
    idle_seq.num_cycles = 500;
    run_seq(idle_seq);

    // --- Read 16 random words, polling rnd_valid each time ---------
    // With num_blocks=2 the CSPRNG will reseed between every two
    // keystream blocks, exercising the full reseed handshake path
    // multiple times within this loop.
    rnd_seq = trng_read_rnd_seq::type_id::create("rnd_seq");
    rnd_seq.num_words    = 16;
    rnd_seq.poll_timeout = 2000;
    run_seq(rnd_seq);

    // --- Settling gap before the next test -------------------------
    idle_seq = trng_idle_seq::type_id::create("idle_tail");
    idle_seq.num_cycles = 50;
    run_seq(idle_seq);

    `uvm_info(get_type_name(), "TC2 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc2_rnd_gen_test


//======================================================================
// TC3 — ChaCha round count sweep
//
// Re-initialises the DUT three times, each time with a different
// round count (20, 24, 32). After each configuration, reads one
// random word to verify the CSPRNG continues operating correctly.
// This sweeps all three named bins in cg_csprng_rounds.
//======================================================================
class trng_tc3_rounds_sweep_test extends trng_base_test;
  `uvm_component_utils(trng_tc3_rounds_sweep_test)

  function new(string name = "trng_tc3_rounds_sweep_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq     init_seq;
    trng_idle_seq     idle_seq;
    trng_read_rnd_seq rnd_seq;

    // Round counts to exercise: min-spec (20), default (24), max (32)
    int unsigned rounds_under_test[3] = '{20, 24, 32};

    phase.raise_objection(this);
    separator("TC3: ChaCha Round Count Sweep (20 / 24 / 32)");

    foreach (rounds_under_test[i]) begin
      `uvm_info(get_type_name(),
        $sformatf("--- Round sweep iteration: %0d rounds ---",
                  rounds_under_test[i]), UVM_MEDIUM)

      // Full re-init with the target round count each iteration.
      // trng_init_seq performs reset internally so state is clean.
      init_seq = trng_init_seq::type_id::create(
                   $sformatf("init_r%0d", rounds_under_test[i]));
      init_seq.chacha_rounds = rounds_under_test[i];
      // Use a small num_blocks value so seeding completes quickly
      init_seq.num_blocks_high = 32'h0000_0000;
      init_seq.num_blocks_low  = 32'h0000_0010;  // 16 blocks
      run_seq(init_seq);

      // Wait for seeding — 32-round ChaCha is slower than 20-round;
      // scale the wait proportionally (baseline 300 cycles at 20
      // rounds, extra 40 cycles per additional round pair).
      idle_seq = trng_idle_seq::type_id::create("idle_seed");
      idle_seq.num_cycles = 300 + (rounds_under_test[i] - 20) * 40;
      run_seq(idle_seq);

      // Read one word to confirm the CSPRNG is generating
      rnd_seq = trng_read_rnd_seq::type_id::create("rnd_one");
      rnd_seq.num_words    = 1;
      rnd_seq.poll_timeout = 3000;
      run_seq(rnd_seq);

      // Short gap between iterations
      idle_seq = trng_idle_seq::type_id::create("idle_gap");
      idle_seq.num_cycles = 50;
      run_seq(idle_seq);
    end

    `uvm_info(get_type_name(), "TC3 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc3_rounds_sweep_test


//======================================================================
// TC4 — Debug mux sweep + discard flush
//
// After init, selects each of the five debug mux sources in turn
// (entropy0=0, entropy1=1, entropy2=2, mixer=3, csprng=4), pulsing
// debug_update 8 times per source. Between each source selection,
// issues a discard to exercise the flush path. This hits all bins
// in cg_debug_mux, cg_errors (debug_ctrl_wr), and cg_mixer_ctrl_fsm
// (discard_in_* cross bins).
//======================================================================
class trng_tc4_debug_mode_test extends trng_base_test;
  `uvm_component_utils(trng_tc4_debug_mode_test)

  function new(string name = "trng_tc4_debug_mode_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq      init_seq;
    trng_idle_seq      idle_seq;
    trng_debug_mode_seq dbg_seq;
    trng_discard_seq   disc_seq;

    // All five debug mux selections in order
    bit [2:0] mux_sels[5] = '{3'h0, 3'h1, 3'h2, 3'h3, 3'h4};

    phase.raise_objection(this);
    separator("TC4: Debug Mux Sweep + Discard Flush");

    init_seq = trng_init_seq::type_id::create("init_seq");
    run_seq(init_seq);

    // Allow mixer and CSPRNG to reach an active state before observing
    idle_seq = trng_idle_seq::type_id::create("idle_post_init");
    idle_seq.num_cycles = 300;
    run_seq(idle_seq);

    foreach (mux_sels[i]) begin
      `uvm_info(get_type_name(),
        $sformatf("Observing debug mux source %0d", mux_sels[i]), UVM_MEDIUM)

      // Select mux source and pulse debug_update 8 times
      dbg_seq = trng_debug_mode_seq::type_id::create(
                  $sformatf("dbg_mux%0d", mux_sels[i]));
      dbg_seq.debug_mux_sel = mux_sels[i];
      dbg_seq.obs_count     = 8;
      run_seq(dbg_seq);

      // Discard flush between observations — exercises discard path
      // while mixer/CSPRNG may be in various FSM states
      disc_seq = trng_discard_seq::type_id::create(
                   $sformatf("disc_%0d", i));
      run_seq(disc_seq);

      // Brief idle to allow the pipeline to drain after discard
      idle_seq = trng_idle_seq::type_id::create($sformatf("idle_disc_%0d", i));
      idle_seq.num_cycles = 30;
      run_seq(idle_seq);
    end

    `uvm_info(get_type_name(), "TC4 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc4_debug_mode_test


//======================================================================
// TC5 — Test mode enter/exit with forced reseed verification
//
// After init and initial random word generation, enters test mode
// (blocks random output per spec), idles inside test mode, then
// exits. On exit the hardware must force a reseed. Verifies that
// random number generation resumes correctly after the forced reseed
// by successfully reading a word.
//======================================================================
class trng_tc5_test_mode_test extends trng_base_test;
  `uvm_component_utils(trng_tc5_test_mode_test)

  function new(string name = "trng_tc5_test_mode_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq      init_seq;
    trng_idle_seq      idle_seq;
    trng_read_rnd_seq  rnd_seq;
    trng_test_mode_seq tmode_seq;

    phase.raise_objection(this);
    separator("TC5: Test Mode Enter / Exit + Forced Reseed");

    // Bring up the DUT and wait for it to generate at least one word
    init_seq = trng_init_seq::type_id::create("init_seq");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_warm");
    idle_seq.num_cycles = 400;
    run_seq(idle_seq);

    // Read one word to confirm normal operation before entering test mode
    rnd_seq = trng_read_rnd_seq::type_id::create("rnd_before");
    rnd_seq.num_words    = 1;
    rnd_seq.poll_timeout = 2000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_pre_tmode");
    idle_seq.num_cycles = 20;
    run_seq(idle_seq);

    // Enter test mode, hold for 20 cycles, exit
    // Per spec: random output blocked during test mode; forced reseed on exit
    tmode_seq = trng_test_mode_seq::type_id::create("tmode_seq");
    tmode_seq.hold_cycles = 20;
    run_seq(tmode_seq);

    // After exiting test mode the CSPRNG must reseed before it can
    // generate again. Allow time for the full reseed pipeline to complete:
    // SHA-512 compression (2 blocks) + ChaCha init + first keystream block.
    idle_seq = trng_idle_seq::type_id::create("idle_reseed");
    idle_seq.num_cycles = 600;
    run_seq(idle_seq);

    // Verify normal operation has resumed after the forced reseed
    rnd_seq = trng_read_rnd_seq::type_id::create("rnd_after");
    rnd_seq.num_words    = 4;
    rnd_seq.poll_timeout = 3000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_tail");
    idle_seq.num_cycles = 50;
    run_seq(idle_seq);

    `uvm_info(get_type_name(), "TC5 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc5_test_mode_test


//======================================================================
// TC6 — Discard during active generation + recovery
//
// Starts normal operation, lets the CSPRNG reach the MORE/NEXT states,
// then asserts discard to flush the pipeline. Verifies that the DUT
// recovers cleanly: re-enables mixer and CSPRNG and reads random words
// again. Exercises the cg_mixer_ctrl_fsm discard_in_* cross bins and
// the cg_csprng_fsm cancel_from_* cross bins.
//======================================================================
class trng_tc6_discard_test extends trng_base_test;
  `uvm_component_utils(trng_tc6_discard_test)

  function new(string name = "trng_tc6_discard_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq          init_seq;
    trng_idle_seq          idle_seq;
    trng_read_rnd_seq      rnd_seq;
    trng_discard_seq       disc_seq;
    trng_enable_csprng_seq csprng_seq;
    trng_enable_mixer_seq  mix_seq;

    phase.raise_objection(this);
    separator("TC6: Discard During Active Generation + Recovery");

    // Initial bringup
    init_seq = trng_init_seq::type_id::create("init_seq");
    run_seq(init_seq);

    // Wait until the CSPRNG has reached an active generation state
    // (NEXT/MORE states are entered after initial seeding completes)
    idle_seq = trng_idle_seq::type_id::create("idle_active");
    idle_seq.num_cycles = 400;
    run_seq(idle_seq);

    // Assert discard — flushes mixer and CSPRNG pipelines mid-operation
    disc_seq = trng_discard_seq::type_id::create("disc_seq");
    run_seq(disc_seq);

    // Allow time for discard to propagate through all FSMs
    idle_seq = trng_idle_seq::type_id::create("idle_post_disc");
    idle_seq.num_cycles = 20;
    run_seq(idle_seq);

    // Re-enable CSPRNG then mixer after the flush
    // (same order as trng_init_seq: CSPRNG before mixer)
    csprng_seq = trng_enable_csprng_seq::type_id::create("csprng_reen");
    run_seq(csprng_seq);

    mix_seq = trng_enable_mixer_seq::type_id::create("mix_reen");
    run_seq(mix_seq);

    // Wait for re-seeding to complete after re-enable
    idle_seq = trng_idle_seq::type_id::create("idle_reseed");
    idle_seq.num_cycles = 500;
    run_seq(idle_seq);

    // Verify recovery: read 8 words from the recovered CSPRNG
    rnd_seq = trng_read_rnd_seq::type_id::create("rnd_recovery");
    rnd_seq.num_words    = 8;
    rnd_seq.poll_timeout = 3000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_tail");
    idle_seq.num_cycles = 50;
    run_seq(idle_seq);

    `uvm_info(get_type_name(), "TC6 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc6_discard_test


//======================================================================
// TC7 — Fully-constrained random access regression
//
// After a clean init, fires 200 fully-randomised but constraint-legal
// bus transactions at the DUT. The seq_item constraints prevent
// illegal addresses and R/W direction violations, so every transaction
// is architecturally valid. Exercises the cg_api_prefix random bins
// and stress-tests the bus decoder.
//======================================================================
class trng_tc7_rand_access_test extends trng_base_test;
  `uvm_component_utils(trng_tc7_rand_access_test)

  function new(string name = "trng_tc7_rand_access_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    trng_init_seq         init_seq;
    trng_idle_seq         idle_seq;
    trng_rand_access_seq  rand_seq;

    phase.raise_objection(this);
    separator("TC7: Fully-Constrained Random Access Regression");

    // Clean init so the DUT is in a known good state before random traffic
    init_seq = trng_init_seq::type_id::create("init_seq");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_warm");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // Fire 200 constrained-random transactions
    rand_seq = trng_rand_access_seq::type_id::create("rand_seq");
    rand_seq.num_transactions = 200;
    run_seq(rand_seq);

    idle_seq = trng_idle_seq::type_id::create("idle_tail");
    idle_seq.num_cycles = 50;
    run_seq(idle_seq);

    `uvm_info(get_type_name(), "TC7 PASSED", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_tc7_rand_access_test


//======================================================================
// trng_full_regression_test
//
// Runs every test case in order, separated by inter-test resets.
// Each test case is replicated inline (rather than re-using the
// individual test classes) so that a single UVM test name triggers
// the complete regression from the simulator command line:
//
//   vcs +UVM_TESTNAME=trng_full_regression_test
//
// A 200-cycle idle window precedes each test case and a 100-cycle
// window follows it, providing deterministic state isolation.
//======================================================================
class trng_test extends trng_base_test;
  `uvm_component_utils(trng_test)

  function new(string name = "trng_test",
               uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  task run_phase(uvm_phase phase);
    // ----------------------------------------------------------------
    // Sequence handles — declared once, reused across TCs
    // ----------------------------------------------------------------
    trng_init_seq           init_seq;
    trng_idle_seq           idle_seq;
    trng_read_rnd_seq       rnd_seq;
    trng_set_num_blocks_seq blocks_seq;
    trng_debug_mode_seq     dbg_seq;
    trng_discard_seq        disc_seq;
    trng_test_mode_seq      tmode_seq;
    trng_rand_access_seq    rand_seq;
    trng_enable_csprng_seq  csprng_seq;
    trng_enable_mixer_seq   mix_seq;

    bit [2:0] mux_sels[5]              = '{3'h0, 3'h1, 3'h2, 3'h3, 3'h4};
    int unsigned rounds_under_test[3]  = '{20, 24, 32};

    phase.raise_objection(this);

    `uvm_info(get_type_name(),
      "\n╔══════════════════════════════════════════════╗\n║        TRNG FULL REGRESSION STARTED         ║\n╚══════════════════════════════════════════════╝",UVM_NONE)

    // ==============================================================
    // TC1 — Full Initialisation
    // ==============================================================
    separator("REGRESSION TC1: Full Initialisation");

    init_seq = trng_init_seq::type_id::create("tc1_init");
    init_seq.chacha_rounds   = 24;
    init_seq.num_blocks_high = 32'h1000_0000;
    init_seq.num_blocks_low  = 32'h0000_0000;
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("tc1_idle");
    idle_seq.num_cycles = 200;
    run_seq(idle_seq);

    // ==============================================================
    // TC2 — Random Number Generation + Forced Reseed
    // ==============================================================
    separator("REGRESSION TC2: RNG + Forced Reseed");

    // Re-init fresh for TC2
    init_seq = trng_init_seq::type_id::create("tc2_init");
    init_seq.chacha_rounds = 24;
    run_seq(init_seq);

    blocks_seq = trng_set_num_blocks_seq::type_id::create("tc2_blocks");
    blocks_seq.num_blocks_low  = 32'h0000_0002;
    blocks_seq.num_blocks_high = 32'h0000_0000;
    run_seq(blocks_seq);

    idle_seq = trng_idle_seq::type_id::create("tc2_idle_warm");
    idle_seq.num_cycles = 500;
    run_seq(idle_seq);

    rnd_seq = trng_read_rnd_seq::type_id::create("tc2_rnd");
    rnd_seq.num_words    = 16;
    rnd_seq.poll_timeout = 2000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("tc2_idle_tail");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // ==============================================================
    // TC3 — ChaCha Round Count Sweep (20 / 24 / 32)
    // ==============================================================
    separator("REGRESSION TC3: ChaCha Round Count Sweep");

    foreach (rounds_under_test[i]) begin
      init_seq = trng_init_seq::type_id::create(
                   $sformatf("tc3_init_r%0d", rounds_under_test[i]));
      init_seq.chacha_rounds   = rounds_under_test[i];
      init_seq.num_blocks_high = 32'h0000_0000;
      init_seq.num_blocks_low  = 32'h0000_0010;
      run_seq(init_seq);

      idle_seq = trng_idle_seq::type_id::create(
                   $sformatf("tc3_idle_r%0d", rounds_under_test[i]));
      idle_seq.num_cycles = 300 + (rounds_under_test[i] - 20) * 40;
      run_seq(idle_seq);

      rnd_seq = trng_read_rnd_seq::type_id::create(
                  $sformatf("tc3_rnd_r%0d", rounds_under_test[i]));
      rnd_seq.num_words    = 1;
      rnd_seq.poll_timeout = 3000;
      run_seq(rnd_seq);

      idle_seq = trng_idle_seq::type_id::create(
                   $sformatf("tc3_gap_r%0d", rounds_under_test[i]));
      idle_seq.num_cycles = 50;
      run_seq(idle_seq);
    end

    // ==============================================================
    // TC4 — Debug Mux Sweep + Discard Flush
    // ==============================================================
    separator("REGRESSION TC4: Debug Mux Sweep + Discard");

    init_seq = trng_init_seq::type_id::create("tc4_init");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("tc4_idle_post_init");
    idle_seq.num_cycles = 300;
    run_seq(idle_seq);

    foreach (mux_sels[i]) begin
      dbg_seq = trng_debug_mode_seq::type_id::create(
                  $sformatf("tc4_dbg%0d", mux_sels[i]));
      dbg_seq.debug_mux_sel = mux_sels[i];
      dbg_seq.obs_count     = 8;
      run_seq(dbg_seq);

      disc_seq = trng_discard_seq::type_id::create(
                   $sformatf("tc4_disc%0d", i));
      run_seq(disc_seq);

      idle_seq = trng_idle_seq::type_id::create(
                   $sformatf("tc4_idle_disc%0d", i));
      idle_seq.num_cycles = 30;
      run_seq(idle_seq);
    end

    idle_seq = trng_idle_seq::type_id::create("tc4_tail");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // ==============================================================
    // TC5 — Test Mode Enter / Exit + Forced Reseed
    // ==============================================================
    separator("REGRESSION TC5: Test Mode + Forced Reseed");

    init_seq = trng_init_seq::type_id::create("tc5_init");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("tc5_idle_warm");
    idle_seq.num_cycles = 400;
    run_seq(idle_seq);

    rnd_seq = trng_read_rnd_seq::type_id::create("tc5_rnd_before");
    rnd_seq.num_words    = 1;
    rnd_seq.poll_timeout = 2000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("tc5_idle_pre");
    idle_seq.num_cycles = 20;
    run_seq(idle_seq);

    tmode_seq = trng_test_mode_seq::type_id::create("tc5_tmode");
    tmode_seq.hold_cycles = 20;
    run_seq(tmode_seq);

    idle_seq = trng_idle_seq::type_id::create("tc5_idle_reseed");
    idle_seq.num_cycles = 600;
    run_seq(idle_seq);

    rnd_seq = trng_read_rnd_seq::type_id::create("tc5_rnd_after");
    rnd_seq.num_words    = 4;
    rnd_seq.poll_timeout = 3000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("tc5_tail");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // ==============================================================
    // TC6 — Discard During Active Generation + Recovery
    // ==============================================================
    separator("REGRESSION TC6: Discard + Recovery");

    init_seq = trng_init_seq::type_id::create("tc6_init");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("tc6_idle_active");
    idle_seq.num_cycles = 400;
    run_seq(idle_seq);

    disc_seq = trng_discard_seq::type_id::create("tc6_disc");
    run_seq(disc_seq);

    idle_seq = trng_idle_seq::type_id::create("tc6_idle_post_disc");
    idle_seq.num_cycles = 20;
    run_seq(idle_seq);

    csprng_seq = trng_enable_csprng_seq::type_id::create("tc6_csprng_reen");
    run_seq(csprng_seq);

    mix_seq = trng_enable_mixer_seq::type_id::create("tc6_mix_reen");
    run_seq(mix_seq);

    idle_seq = trng_idle_seq::type_id::create("tc6_idle_reseed");
    idle_seq.num_cycles = 500;
    run_seq(idle_seq);

    rnd_seq = trng_read_rnd_seq::type_id::create("tc6_rnd_recovery");
    rnd_seq.num_words    = 8;
    rnd_seq.poll_timeout = 3000;
    run_seq(rnd_seq);

    idle_seq = trng_idle_seq::type_id::create("tc6_tail");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // ==============================================================
    // TC7 — Fully-Constrained Random Access Regression
    // ==============================================================
    separator("REGRESSION TC7: Constrained Random Access");

    init_seq = trng_init_seq::type_id::create("tc7_init");
    run_seq(init_seq);

    idle_seq = trng_idle_seq::type_id::create("tc7_idle_warm");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    rand_seq = trng_rand_access_seq::type_id::create("tc7_rand");
    rand_seq.num_transactions = 200;
    run_seq(rand_seq);

    idle_seq = trng_idle_seq::type_id::create("tc7_tail");
    idle_seq.num_cycles = 100;
    run_seq(idle_seq);

    // ==============================================================
    // Done
    // ==============================================================
    `uvm_info(get_type_name(),
      "\n╔══════════════════════════════════════════════╗\n║       TRNG FULL REGRESSION COMPLETE         ║\n╚══════════════════════════════════════════════╝",UVM_NONE)

    phase.drop_objection(this);
  endtask : run_phase

endclass : trng_test

`endif // TRNG_TEST_SV
