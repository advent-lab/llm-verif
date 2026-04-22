//======================================================================
// trng_seq.sv
//
// UVM Sequence library for the True Random Number Generator (TRNG).
//
//  trng_base_seq           — Base class; send_item() convenience task.
//  trng_reset_seq          — Assert/release active-low reset.
//  trng_reg_read_seq       — Single register read transaction.
//  trng_reg_write_seq      — Single register write transaction.
//  trng_enable_mixer_seq   — Enable the SHA-512 entropy mixer.
//  trng_enable_csprng_seq  — Enable the ChaCha CSPRNG.
//  trng_set_rounds_seq     — Configure ChaCha round count [20..32].
//  trng_set_num_blocks_seq — Configure max blocks before reseed.
//  trng_read_rnd_seq       — Poll rnd_valid then read RND_DATA.
//  trng_debug_mode_seq     — Select debug mux and pulse debug_update.
//  trng_discard_seq        — Assert then clear the discard flush bit.
//  trng_test_mode_seq      — Enter / exit test mode safely.
//  trng_init_seq           — Full bringup: reset -> id read -> config ->
//                            enable CSPRNG -> enable mixer.
//  trng_rand_access_seq    — Fully-constrained random bus access.
//
// Fixes applied versus the previously generated trng_seq.sv:
//   [FIX-1]  trng_reset_seq: Added a mandatory post-reset idle window
//            (2 cycles) so internal registers finish settling before
//            the first register access. Matches reset_dut() in tb_trng.v
//            (#(2*CLK_PERIOD) after tb_reset_n=1) and do_reset() in
//            trng_tb.sv (repeat(2) @(posedge clk) after reset_n=1).
//
//   [FIX-2]  trng_read_rnd_seq: status_item.read_data is now valid
//            after finish_item() because the driver writes captured
//            read_data back into the item object. The poll logic itself
//            is correct but required the driver fix to function.
//            send_item_ret() introduced to return the item to the
//            caller, making the dependency explicit and type-safe.
//
//   [FIX-3]  trng_init_seq: Replaced the invalid `foreach` over an
//            inline constant array with three explicit read calls.
//            `foreach ('{a,b,c}[i])` is not legal SystemVerilog and
//            causes a compilation error on all major simulators.
//
//   [FIX-4]  trng_init_seq: CSPRNG is now enabled BEFORE the mixer.
//            The CSPRNG must be ready to accept seed_syn before the
//            mixer starts hashing. In the original order the mixer
//            could complete its first hash and assert seed_syn while
//            the CSPRNG was still in CTRL_IDLE (enable_reg=0), causing
//            the CTRL_SEED0 state to immediately branch to CTRL_CANCEL.
//
//   [FIX-5]  trng_base_seq send_item: Added send_item_ret() variant
//            that returns the populated item so callers can inspect
//            read_data / error without a separate monitor tap.
//======================================================================

import uvm_pkg::*;
`include "uvm_macros.svh"


//----------------------------------------------------------------------
// trng_base_seq
//----------------------------------------------------------------------
class trng_base_seq extends uvm_sequence #(trng_seq_item);
  `uvm_object_utils(trng_base_seq)

  function new(string name = "trng_base_seq");
    super.new(name);
  endfunction : new

  //--------------------------------------------------------------------
  // send_item
  // Create one item, constrain its fields to the supplied values, hand
  // it to the driver, and wait for completion.  After finish_item()
  // returns the driver has written read_data, error, security_error,
  // and debug back into the item.
  //--------------------------------------------------------------------
  task send_item(
    input bit        cs_i,
    input bit        we_i,
    input bit [11:0] address_i,
    input bit [31:0] write_data_i  = 32'h0,
    input bit        debug_upd_i   = 1'b0,
    input bit        noise_i       = 1'b0
  );
    trng_seq_item item;
    item = trng_seq_item::type_id::create("item");
    start_item(item);
    if (!item.randomize() with {
          cs              == cs_i;
          we              == we_i;
          address         == address_i;
          write_data      == write_data_i;
          debug_update    == debug_upd_i;
          avalanche_noise == noise_i;       // [FIX-5] explicit when provided
        })
      `uvm_fatal("RAND_FAIL", "trng_base_seq::send_item randomize failed")
    finish_item(item);
  endtask : send_item

  //--------------------------------------------------------------------
  // send_item_ret  [FIX-5]
  // Like send_item but returns the item so the caller can read back
  // the DUT response (read_data, error, etc.) after finish_item().
  //--------------------------------------------------------------------
  task send_item_ret(
    output trng_seq_item out_item,
    input  bit           cs_i,
    input  bit           we_i,
    input  bit [11:0]    address_i,
    input  bit [31:0]    write_data_i = 32'h0,
    input  bit           debug_upd_i  = 1'b0
  );
    trng_seq_item item;
    item = trng_seq_item::type_id::create("item");
    start_item(item);
    if (!item.randomize() with {
          cs           == cs_i;
          we           == we_i;
          address      == address_i;
          write_data   == write_data_i;
          debug_update == debug_upd_i;
        })
      `uvm_fatal("RAND_FAIL", "trng_base_seq::send_item_ret randomize failed")
    finish_item(item);
    out_item = item;
  endtask : send_item_ret

endclass : trng_base_seq


//----------------------------------------------------------------------
// trng_reset_seq
// Assert active-low reset for reset_cycles clocks, release it, then
// idle for settle_cycles clocks so DUT registers finish initialising.
//
// [FIX-1] settle_cycles post-reset window added.
//----------------------------------------------------------------------
class trng_reset_seq extends trng_base_seq;
  `uvm_object_utils(trng_reset_seq)

  int unsigned reset_cycles  = 4;  // Clocks to hold reset_n=0
  int unsigned settle_cycles = 2;  // [FIX-1] Post-reset idle clocks

  function new(string name = "trng_reset_seq");
    super.new(name);
  endfunction : new

  task body();
    trng_seq_item item;

    `uvm_info(get_type_name(), "Asserting reset", UVM_MEDIUM)

    // Assert reset: all bus signals idle, reset_n=0
    repeat (reset_cycles) begin
      item = trng_seq_item::type_id::create("rst_item");
      start_item(item);
      if (!item.randomize() with {
            cs         == 1'b0;
            we         == 1'b0;
            address    == 12'h0;
            write_data == 32'h0;
          })
        `uvm_fatal("RAND_FAIL", "trng_reset_seq assert randomize failed")
      item.reset_n = 1'b0;
      finish_item(item);
    end

    // De-assert reset
    item = trng_seq_item::type_id::create("rst_rel");
    start_item(item);
    if (!item.randomize() with {
          cs         == 1'b0;
          we         == 1'b0;
          address    == 12'h0;
          write_data == 32'h0;
        })
      `uvm_fatal("RAND_FAIL", "trng_reset_seq release randomize failed")
    item.reset_n = 1'b1;
    finish_item(item);

    // [FIX-1] Settle window — matches tb_trng.v reset_dut() which
    // waits #(2*CLK_PERIOD) after tb_reset_n=1, and trng_tb.sv
    // do_reset() which does repeat(2) @(posedge clk) after reset_n=1.
    repeat (settle_cycles) begin
      item = trng_seq_item::type_id::create("idle_item");
      start_item(item);
      if (!item.randomize() with {
            cs         == 1'b0;
            we         == 1'b0;
            address    == 12'h0;
            write_data == 32'h0;
          })
        `uvm_fatal("RAND_FAIL", "trng_reset_seq settle randomize failed")
      item.reset_n = 1'b1;
      finish_item(item);
    end

    `uvm_info(get_type_name(), "Reset released and settled", UVM_MEDIUM)
  endtask : body

endclass : trng_reset_seq


//----------------------------------------------------------------------
// trng_reg_read_seq
// Issues a single read and exposes the result in read_result.
//----------------------------------------------------------------------
class trng_reg_read_seq extends trng_base_seq;
  `uvm_object_utils(trng_reg_read_seq)

  bit [11:0] read_address;
  bit [31:0] read_result;   // Valid after body() completes

  function new(string name = "trng_reg_read_seq");
    super.new(name);
  endfunction : new

  task body();
    trng_seq_item item;

    `uvm_info(get_type_name(),
              $sformatf("Read addr=0x%03X", read_address), UVM_HIGH)

    send_item_ret(.out_item(item),
                  .cs_i(1'b1), .we_i(1'b0),
                  .address_i(read_address));
    read_result = item.read_data;
  endtask : body

endclass : trng_reg_read_seq


//----------------------------------------------------------------------
// trng_reg_write_seq
// Issues a single write transaction.
//----------------------------------------------------------------------
class trng_reg_write_seq extends trng_base_seq;
  `uvm_object_utils(trng_reg_write_seq)

  bit [11:0] write_address;
  bit [31:0] write_value;

  function new(string name = "trng_reg_write_seq");
    super.new(name);
  endfunction : new

  task body();
    `uvm_info(get_type_name(),
              $sformatf("Write addr=0x%03X data=0x%08X",
                        write_address, write_value), UVM_HIGH)
    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(write_address),
              .write_data_i(write_value));
  endtask : body

endclass : trng_reg_write_seq


//----------------------------------------------------------------------
// trng_enable_csprng_seq
// Writes CSPRNG_CTRL with enable=1 (bit 0).
//----------------------------------------------------------------------
class trng_enable_csprng_seq extends trng_base_seq;
  `uvm_object_utils(trng_enable_csprng_seq)

  function new(string name = "trng_enable_csprng_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_CSPRNG=4'hb | ADDR_CTRL=8'h10
    localparam bit [11:0] CSPRNG_CTRL_ADDR = {4'hb, 8'h10};
    `uvm_info(get_type_name(), "Enabling CSPRNG", UVM_MEDIUM)
    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(CSPRNG_CTRL_ADDR),
              .write_data_i(32'h0000_0001));
  endtask : body

endclass : trng_enable_csprng_seq


//----------------------------------------------------------------------
// trng_enable_mixer_seq
// Writes MIXER_CTRL with enable=1 (bit 0).
//----------------------------------------------------------------------
class trng_enable_mixer_seq extends trng_base_seq;
  `uvm_object_utils(trng_enable_mixer_seq)

  function new(string name = "trng_enable_mixer_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_MIXER=4'ha | ADDR_MIXER_CTRL=8'h10
    localparam bit [11:0] MIXER_CTRL_ADDR = {4'ha, 8'h10};
    `uvm_info(get_type_name(), "Enabling entropy mixer", UVM_MEDIUM)
    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(MIXER_CTRL_ADDR),
              .write_data_i(32'h0000_0001));
  endtask : body

endclass : trng_enable_mixer_seq


//----------------------------------------------------------------------
// trng_set_rounds_seq
// Configures ChaCha round count. Spec mandates minimum 20, maximum 32.
//----------------------------------------------------------------------
class trng_set_rounds_seq extends trng_base_seq;
  `uvm_object_utils(trng_set_rounds_seq)

  int unsigned num_rounds = 24;

  function new(string name = "trng_set_rounds_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_CSPRNG=4'hb | ADDR_NUM_ROUNDS=8'h40
    localparam bit [11:0] NUM_ROUNDS_ADDR = {4'hb, 8'h40};

    if (num_rounds < 20 || num_rounds > 32) begin
      `uvm_error(get_type_name(),
        $sformatf("num_rounds=%0d out of spec [20,32]; clamping to 24",
                  num_rounds))
      num_rounds = 24;
    end

    `uvm_info(get_type_name(),
              $sformatf("Setting ChaCha rounds=%0d", num_rounds), UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(NUM_ROUNDS_ADDR),
              .write_data_i(32'(num_rounds)));
  endtask : body

endclass : trng_set_rounds_seq


//----------------------------------------------------------------------
// trng_set_num_blocks_seq
// Configures the 64-bit max-blocks-before-reseed threshold.
//----------------------------------------------------------------------
class trng_set_num_blocks_seq extends trng_base_seq;
  `uvm_object_utils(trng_set_num_blocks_seq)

  // Default: DEFAULT_NUM_BLOCKS = 2**60
  bit [31:0] num_blocks_low  = 32'h0000_0000;
  bit [31:0] num_blocks_high = 32'h1000_0000;

  function new(string name = "trng_set_num_blocks_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_CSPRNG=4'hb | ADDR_NUM_BLOCKS_LOW=8'h41, HIGH=8'h42
    localparam bit [11:0] BLOCKS_LOW_ADDR  = {4'hb, 8'h41};
    localparam bit [11:0] BLOCKS_HIGH_ADDR = {4'hb, 8'h42};

    `uvm_info(get_type_name(),
              $sformatf("num_blocks high=0x%08X low=0x%08X",
                        num_blocks_high, num_blocks_low), UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(BLOCKS_LOW_ADDR),
              .write_data_i(num_blocks_low));

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(BLOCKS_HIGH_ADDR),
              .write_data_i(num_blocks_high));
  endtask : body

endclass : trng_set_num_blocks_seq


//----------------------------------------------------------------------
// trng_read_rnd_seq
// Polls CSPRNG STATUS until rnd_valid (bit 0) is asserted, then reads
// ADDR_RND_DATA. Repeats for num_words words.
//
// [FIX-2] Uses send_item_ret() so status_item.read_data is populated
// by the driver before the poll check executes.
//----------------------------------------------------------------------
class trng_read_rnd_seq extends trng_base_seq;
  `uvm_object_utils(trng_read_rnd_seq)

  int unsigned num_words    = 1;
  int unsigned poll_timeout = 2000;

  function new(string name = "trng_read_rnd_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_CSPRNG=4'hb | ADDR_STATUS=8'h11, ADDR_RND_DATA=8'h20
    localparam bit [11:0] CSPRNG_STATUS_ADDR = {4'hb, 8'h11};
    localparam bit [11:0] RND_DATA_ADDR      = {4'hb, 8'h20};

    trng_seq_item status_item;
    int unsigned  poll_count;

    for (int w = 0; w < num_words; w++) begin
      poll_count = 0;

      // Poll until rnd_valid=1. The driver writes vif.read_data back
      // into status_item after finish_item(), so status_item.read_data
      // reflects the live DUT response for this poll cycle. [FIX-2]
      forever begin
        send_item_ret(
          .out_item    (status_item),
          .cs_i        (1'b1),
          .we_i        (1'b0),
          .address_i   (CSPRNG_STATUS_ADDR)
        );

        if (status_item.read_data[0]) begin
          `uvm_info(get_type_name(),
            $sformatf("Word %0d: rnd_valid set after %0d polls",
                      w, poll_count), UVM_HIGH)
          break;
        end

        if (++poll_count >= poll_timeout) begin
          `uvm_error(get_type_name(),
            $sformatf("Timeout waiting for rnd_valid (word %0d)", w))
          break;
        end
      end

      // Reading ADDR_RND_DATA asserts rnd_ack internally, advancing
      // the FIFO mux pointer.
      send_item(.cs_i(1'b1), .we_i(1'b0), .address_i(RND_DATA_ADDR));
    end
  endtask : body

endclass : trng_read_rnd_seq


//----------------------------------------------------------------------
// trng_debug_mode_seq
// Selects a debug mux source then pulses debug_update obs_count times.
//----------------------------------------------------------------------
class trng_debug_mode_seq extends trng_base_seq;
  `uvm_object_utils(trng_debug_mode_seq)

  bit [2:0]    debug_mux_sel = 3'h4;  // Default: DBG_CSPRNG
  int unsigned obs_count     = 8;

  function new(string name = "trng_debug_mode_seq");
    super.new(name);
  endfunction : new

  task body();
    // PREFIX_TRNG=4'h0 | ADDR_DEBUG_CTRL=8'h12
    localparam bit [11:0] DEBUG_CTRL_ADDR = {4'h0, 8'h12};

    `uvm_info(get_type_name(),
              $sformatf("Debug mux_sel=%0d obs=%0d",
                        debug_mux_sel, obs_count), UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(DEBUG_CTRL_ADDR),
              .write_data_i({29'h0, debug_mux_sel}));

    repeat (obs_count)
      send_item(.cs_i(1'b0), .we_i(1'b0),
                .address_i(12'h0),
                .write_data_i(32'h0),
                .debug_upd_i(1'b1));
  endtask : body

endclass : trng_debug_mode_seq


//----------------------------------------------------------------------
// trng_discard_seq
// Asserts discard for one cycle then clears it.
//----------------------------------------------------------------------
class trng_discard_seq extends trng_base_seq;
  `uvm_object_utils(trng_discard_seq)

  function new(string name = "trng_discard_seq");
    super.new(name);
  endfunction : new

  task body();
    localparam bit [11:0] TRNG_CTRL_ADDR = {4'h0, 8'h10};

    `uvm_info(get_type_name(), "Asserting discard", UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(TRNG_CTRL_ADDR),
              .write_data_i(32'h0000_0001));  // bit0=discard

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(TRNG_CTRL_ADDR),
              .write_data_i(32'h0000_0000));  // clear

    `uvm_info(get_type_name(), "Discard cleared", UVM_MEDIUM)
  endtask : body

endclass : trng_discard_seq


//----------------------------------------------------------------------
// trng_test_mode_seq
// Enters test mode, idles, then exits (triggering a reseed).
//----------------------------------------------------------------------
class trng_test_mode_seq extends trng_base_seq;
  `uvm_object_utils(trng_test_mode_seq)

  int unsigned hold_cycles = 10;

  function new(string name = "trng_test_mode_seq");
    super.new(name);
  endfunction : new

  task body();
    localparam bit [11:0] TRNG_CTRL_ADDR = {4'h0, 8'h10};

    `uvm_info(get_type_name(), "Entering test mode", UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(TRNG_CTRL_ADDR),
              .write_data_i(32'h0000_0002));  // bit1=test_mode

    repeat (hold_cycles)
      send_item(.cs_i(1'b0), .we_i(1'b0),
                .address_i(12'h0), .write_data_i(32'h0));

    `uvm_info(get_type_name(), "Exiting test mode", UVM_MEDIUM)

    send_item(.cs_i(1'b1), .we_i(1'b1),
              .address_i(TRNG_CTRL_ADDR),
              .write_data_i(32'h0000_0000));  // clear test_mode
  endtask : body

endclass : trng_test_mode_seq


//----------------------------------------------------------------------
// trng_init_seq
// Full device bringup in the correct order for the TRNG design:
//   1. Reset + settle
//   2. Read NAME0, NAME1, VERSION    [FIX-3] explicit calls
//   3. Configure ChaCha rounds
//   4. Configure max blocks before reseed
//   5. Enable CSPRNG                 [FIX-4] before mixer
//   6. Enable mixer
//----------------------------------------------------------------------
class trng_init_seq extends trng_base_seq;
  `uvm_object_utils(trng_init_seq)

  int unsigned chacha_rounds   = 24;
  bit [31:0]   num_blocks_high = 32'h1000_0000;
  bit [31:0]   num_blocks_low  = 32'h0000_0000;

  function new(string name = "trng_init_seq");
    super.new(name);
  endfunction : new

  task body();
    trng_reset_seq          rst_seq;
    trng_reg_read_seq       rd_seq;
    trng_set_rounds_seq     rounds_seq;
    trng_set_num_blocks_seq blocks_seq;
    trng_enable_csprng_seq  csprng_seq;
    trng_enable_mixer_seq   mix_seq;

    `uvm_info(get_type_name(), "=== TRNG full initialisation ===", UVM_LOW)

    // 1. Reset + settle
    rst_seq = trng_reset_seq::type_id::create("rst_seq");
    rst_seq.start(m_sequencer);

    // 2a. Read NAME0 — [FIX-3] explicit instead of foreach on literal
    rd_seq = trng_reg_read_seq::type_id::create("rd_name0");
    rd_seq.read_address = {4'h0, 8'h00};
    rd_seq.start(m_sequencer);
    `uvm_info(get_type_name(),
              $sformatf("NAME0   = 0x%08X", rd_seq.read_result), UVM_MEDIUM)

    // 2b. Read NAME1
    rd_seq = trng_reg_read_seq::type_id::create("rd_name1");
    rd_seq.read_address = {4'h0, 8'h01};
    rd_seq.start(m_sequencer);
    `uvm_info(get_type_name(),
              $sformatf("NAME1   = 0x%08X", rd_seq.read_result), UVM_MEDIUM)

    // 2c. Read VERSION
    rd_seq = trng_reg_read_seq::type_id::create("rd_version");
    rd_seq.read_address = {4'h0, 8'h02};
    rd_seq.start(m_sequencer);
    `uvm_info(get_type_name(),
              $sformatf("VERSION = 0x%08X", rd_seq.read_result), UVM_MEDIUM)

    // 3. Configure ChaCha rounds
    rounds_seq = trng_set_rounds_seq::type_id::create("rounds_seq");
    rounds_seq.num_rounds = chacha_rounds;
    rounds_seq.start(m_sequencer);

    // 4. Configure max blocks
    blocks_seq = trng_set_num_blocks_seq::type_id::create("blocks_seq");
    blocks_seq.num_blocks_high = num_blocks_high;
    blocks_seq.num_blocks_low  = num_blocks_low;
    blocks_seq.start(m_sequencer);

    // 5. Enable CSPRNG first [FIX-4]
    // The CSPRNG must be in an enabled state before the mixer asserts
    // seed_syn. If the mixer is enabled first and completes a hash block
    // before the CSPRNG enable bit is set, the CSPRNG sees seed_syn
    // while enable_reg=0 and immediately cancels, stalling the pipeline.
    csprng_seq = trng_enable_csprng_seq::type_id::create("csprng_seq");
    csprng_seq.start(m_sequencer);

    // 6. Enable mixer — seed_syn may fire as soon as the first 1024-bit
    //    entropy block is complete; CSPRNG is already ready above.
    mix_seq = trng_enable_mixer_seq::type_id::create("mix_seq");
    mix_seq.start(m_sequencer);

    `uvm_info(get_type_name(), "=== Initialisation complete ===", UVM_LOW)
  endtask : body

endclass : trng_init_seq


//----------------------------------------------------------------------
// trng_rand_access_seq
// Fully-constrained random register access (regression utility).
//----------------------------------------------------------------------
class trng_rand_access_seq extends trng_base_seq;
  `uvm_object_utils(trng_rand_access_seq)

  int unsigned num_transactions = 50;

  function new(string name = "trng_rand_access_seq");
    super.new(name);
  endfunction : new

  task body();
    trng_seq_item item;

    `uvm_info(get_type_name(),
              $sformatf("Generating %0d random transactions",
                        num_transactions), UVM_MEDIUM)

    repeat (num_transactions) begin
      item = trng_seq_item::type_id::create("rand_item");
      start_item(item);
      if (!item.randomize())
        `uvm_fatal("RAND_FAIL", "trng_rand_access_seq randomize failed")
      finish_item(item);
    end
  endtask : body

endclass : trng_rand_access_seq

//======================================================================
// EOF trng_seq.sv
//======================================================================
