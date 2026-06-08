//======================================================================
// trng_seq_item.sv
//
// UVM Sequence Item for the True Random Number Generator (TRNG) core.
//
// Encapsulates all bus transactions and control signals needed to
// drive and monitor the top-level trng module interface.
//
// Top-level port map (trng.v):
//   Inputs  : clk, reset_n, avalanche_noise, cs, we, address[11:0],
//             write_data[31:0], debug_update
//   Outputs : read_data[31:0], error, debug[7:0], security_error
//
// Address space (address[11:8] prefix selects subsystem):
//   4'h0  - TRNG top-level registers
//   4'h5  - Entropy1 (avalanche) registers
//   4'h6  - Entropy2 (ROSC) registers
//   4'hA  - Mixer registers
//   4'hB  - CSPRNG registers
//
// TRNG register offsets (address[7:0]):
//   8'h00 - ADDR_NAME0     (RO)
//   8'h01 - ADDR_NAME1     (RO)
//   8'h02 - ADDR_VERSION   (RO)
//   8'h10 - ADDR_TRNG_CTRL (RW) [bit0=discard, bit1=test_mode]
//   8'h11 - ADDR_TRNG_STATUS (RO)
//   8'h12 - ADDR_DEBUG_CTRL  (RW) [bits2:0 = debug_mux select]
//   8'h13 - ADDR_DEBUG_DELAY (RW)
//
// Mixer register offsets (address[7:0]):
//   8'h10 - ADDR_MIXER_CTRL   (RW) [bit0=enable, bit1=restart]
//   8'h11 - ADDR_MIXER_STATUS (RO)
//   8'h20 - ADDR_MIXER_TIMEOUT (RW)
//
// CSPRNG register offsets (address[7:0]):
//   8'h10 - ADDR_CTRL           (RW) [bit0=enable, bit1=seed]
//   8'h11 - ADDR_STATUS         (RO) [bit0=rnd_valid]
//   8'h20 - ADDR_RND_DATA       (RO)
//   8'h40 - ADDR_NUM_ROUNDS     (RW)
//   8'h41 - ADDR_NUM_BLOCKS_LOW  (RW)
//   8'h42 - ADDR_NUM_BLOCKS_HIGH (RW)
//======================================================================

import uvm_pkg::*;
`include "uvm_macros.svh"

class trng_seq_item extends uvm_sequence_item;

  //--------------------------------------------------------------------
  // Address prefix parameters (address[11:8])
  //--------------------------------------------------------------------
  parameter TRNG_PREFIX    = 4'h0;
  parameter ENTROPY1_PREFIX = 4'h5;
  parameter ENTROPY2_PREFIX = 4'h6;
  parameter MIXER_PREFIX   = 4'ha;
  parameter CSPRNG_PREFIX  = 4'hb;

  //--------------------------------------------------------------------
  // TRNG top-level register address offsets (address[7:0])
  //--------------------------------------------------------------------
  parameter ADDR_NAME0         = 8'h00;
  parameter ADDR_NAME1         = 8'h01;
  parameter ADDR_VERSION       = 8'h02;
  parameter ADDR_TRNG_CTRL     = 8'h10;
  parameter ADDR_TRNG_STATUS   = 8'h11;
  parameter ADDR_DEBUG_CTRL    = 8'h12;
  parameter ADDR_DEBUG_DELAY   = 8'h13;

  //--------------------------------------------------------------------
  // CSPRNG register address offsets (address[7:0])
  //--------------------------------------------------------------------
  parameter ADDR_CSPRNG_CTRL        = 8'h10;
  parameter ADDR_CSPRNG_STATUS      = 8'h11;
  parameter ADDR_RND_DATA           = 8'h20;
  parameter ADDR_NUM_ROUNDS         = 8'h40;
  parameter ADDR_NUM_BLOCKS_LOW     = 8'h41;
  parameter ADDR_NUM_BLOCKS_HIGH    = 8'h42;

  //--------------------------------------------------------------------
  // Mixer register address offsets (address[7:0])
  //--------------------------------------------------------------------
  parameter ADDR_MIXER_CTRL    = 8'h10;
  parameter ADDR_MIXER_STATUS  = 8'h11;
  parameter ADDR_MIXER_TIMEOUT = 8'h20;

  //--------------------------------------------------------------------
  // Valid ChaCha round counts per specification (minimum 20, up to 32)
  //--------------------------------------------------------------------
  parameter MIN_ROUNDS = 5'h14;   // 20 rounds
  parameter MAX_ROUNDS = 6'h20;   // 32 rounds (6 bits needed: decimal 32 = 6'b100000)

  //--------------------------------------------------------------------
  // Debug mux select encoding
  //--------------------------------------------------------------------
  parameter DEBUG_ENTROPY0 = 3'h0;
  parameter DEBUG_ENTROPY1 = 3'h1;
  parameter DEBUG_ENTROPY2 = 3'h2;
  parameter DEBUG_MIXER    = 3'h3;
  parameter DEBUG_CSPRNG   = 3'h4;

  //--------------------------------------------------------------------
  // Clock and reset signals
  // Declared as 'bit' type, NOT randomized (driven by testbench infra)
  //--------------------------------------------------------------------
  bit clk;
  bit reset_n;

  //--------------------------------------------------------------------
  // Input signals — declared as 'rand' for randomized stimulus
  //--------------------------------------------------------------------

  // Physical noise input for the avalanche entropy source
  rand bit        avalanche_noise;

  // Bus interface inputs
  rand bit        cs;             // Chip select (active high)
  rand bit        we;             // Write enable (1=write, 0=read)
  rand bit [11:0] address;        // 12-bit address: [11:8]=prefix, [7:0]=offset
  rand bit [31:0] write_data;     // 32-bit write data bus

  // Debug port input
  rand bit        debug_update;   // Pulse to latch debug output

  //--------------------------------------------------------------------
  // Output signals — NOT randomized (captured from DUT response)
  //--------------------------------------------------------------------
  bit [31:0] read_data;      // 32-bit read data bus
  bit        error;          // Transaction error flag
  bit [7:0]  debug;          // 8-bit debug observation bus
  bit        security_error; // Asserted on entropy source health failure

  //--------------------------------------------------------------------
  // UVM factory registration and field automation
  //--------------------------------------------------------------------
  `uvm_object_utils_begin(trng_seq_item)
    // Clock / reset — not randomized, included for full visibility
    `uvm_field_int(clk,            UVM_ALL_ON)
    `uvm_field_int(reset_n,        UVM_ALL_ON)

    // Randomizable inputs
    `uvm_field_int(avalanche_noise, UVM_ALL_ON)
    `uvm_field_int(cs,              UVM_ALL_ON)
    `uvm_field_int(we,              UVM_ALL_ON)
    `uvm_field_int(address,         UVM_ALL_ON)
    `uvm_field_int(write_data,      UVM_ALL_ON)
    `uvm_field_int(debug_update,    UVM_ALL_ON)

    // DUT outputs (observed, not driven)
    `uvm_field_int(read_data,       UVM_ALL_ON)
    `uvm_field_int(error,           UVM_ALL_ON)
    `uvm_field_int(debug,           UVM_ALL_ON)
    `uvm_field_int(security_error,  UVM_ALL_ON)
  `uvm_object_utils_end

  //--------------------------------------------------------------------
  // Constructor
  //--------------------------------------------------------------------
  function new(string name = "trng_seq_item");
    super.new(name);
  endfunction : new

  //====================================================================
  // CONSTRAINTS
  //====================================================================

  //--------------------------------------------------------------------
  // Address prefix constraint
  // Only the five defined subsystem prefixes are legal.
  //--------------------------------------------------------------------
  constraint valid_address_prefix_c {
    address[11:8] inside {
      TRNG_PREFIX,
      ENTROPY1_PREFIX,
      ENTROPY2_PREFIX,
      MIXER_PREFIX,
      CSPRNG_PREFIX
    };
  }

  //--------------------------------------------------------------------
  // Register offset constraints per subsystem
  // Prevents targeting undefined/reserved register holes.
  //--------------------------------------------------------------------
  constraint valid_trng_reg_offset_c {
    (address[11:8] == TRNG_PREFIX) ->
      address[7:0] inside {
        ADDR_NAME0,
        ADDR_NAME1,
        ADDR_VERSION,
        ADDR_TRNG_CTRL,
        ADDR_TRNG_STATUS,
        ADDR_DEBUG_CTRL,
        ADDR_DEBUG_DELAY
      };
  }

  constraint valid_mixer_reg_offset_c {
    (address[11:8] == MIXER_PREFIX) ->
      address[7:0] inside {
        ADDR_MIXER_CTRL,
        ADDR_MIXER_STATUS,
        ADDR_MIXER_TIMEOUT
      };
  }

  constraint valid_csprng_reg_offset_c {
    (address[11:8] == CSPRNG_PREFIX) ->
      address[7:0] inside {
        ADDR_CSPRNG_CTRL,
        ADDR_CSPRNG_STATUS,
        ADDR_RND_DATA,
        ADDR_NUM_ROUNDS,
        ADDR_NUM_BLOCKS_LOW,
        ADDR_NUM_BLOCKS_HIGH
      };
  }

  //--------------------------------------------------------------------
  // Read-only register guard
  // Status, name, version and RND_DATA registers must not be written.
  //--------------------------------------------------------------------
  constraint read_only_regs_c {
    // TRNG read-only registers
    (address[11:8] == TRNG_PREFIX &&
     address[7:0] inside {ADDR_NAME0, ADDR_NAME1,
                           ADDR_VERSION, ADDR_TRNG_STATUS}) ->
      we == 1'b0;

    // Mixer status is read-only
    (address[11:8] == MIXER_PREFIX &&
     address[7:0] == ADDR_MIXER_STATUS) ->
      we == 1'b0;

    // CSPRNG status and RND_DATA are read-only
    (address[11:8] == CSPRNG_PREFIX &&
     address[7:0] inside {ADDR_CSPRNG_STATUS, ADDR_RND_DATA}) ->
      we == 1'b0;
  }

  //--------------------------------------------------------------------
  // Bus transaction validity
  // A write or read operation only makes sense when cs is asserted.
  // When cs=0, we and write_data should be idle.
  //--------------------------------------------------------------------
  constraint bus_idle_when_no_cs_c {
    (!cs) -> (we == 1'b0);
  }

  //--------------------------------------------------------------------
  // TRNG control register write data
  // Bits [31:2] are reserved; only bits [1:0] carry meaning.
  //   bit 0 — discard
  //   bit 1 — test_mode
  //--------------------------------------------------------------------
  constraint trng_ctrl_write_data_c {
    (address[11:8] == TRNG_PREFIX &&
     address[7:0]  == ADDR_TRNG_CTRL &&
     we            == 1'b1) ->
      write_data[31:2] == 30'h0;
  }

  //--------------------------------------------------------------------
  // Debug control register write data
  // Only three-bit mux select is meaningful (bits [2:0]).
  // Valid values: 0–4 (see DEBUG_* parameters above).
  //--------------------------------------------------------------------
  constraint debug_ctrl_write_data_c {
    (address[11:8] == TRNG_PREFIX &&
     address[7:0]  == ADDR_DEBUG_CTRL &&
     we            == 1'b1) ->
      write_data inside {
        32'(DEBUG_ENTROPY0),
        32'(DEBUG_ENTROPY1),
        32'(DEBUG_ENTROPY2),
        32'(DEBUG_MIXER),
        32'(DEBUG_CSPRNG)
      };
  }

  //--------------------------------------------------------------------
  // CSPRNG control register write data
  // Bits [31:2] reserved.
  //   bit 0 — enable
  //   bit 1 — force seed
  //--------------------------------------------------------------------
  constraint csprng_ctrl_write_data_c {
    (address[11:8] == CSPRNG_PREFIX &&
     address[7:0]  == ADDR_CSPRNG_CTRL &&
     we            == 1'b1) ->
      write_data[31:2] == 30'h0;
  }

  //--------------------------------------------------------------------
  // ChaCha round count constraint
  // Specification mandates at least 20 rounds; hardware upper limit
  // is 32 rounds. Values outside [20,32] are architecturally invalid.
  //--------------------------------------------------------------------
  constraint valid_num_rounds_c {
    (address[11:8] == CSPRNG_PREFIX &&
     address[7:0]  == ADDR_NUM_ROUNDS &&
     we            == 1'b1) ->
      write_data[4:0] inside {[MIN_ROUNDS:MAX_ROUNDS]};
  }

  //--------------------------------------------------------------------
  // Mixer control register write data
  // Bits [31:2] reserved.
  //   bit 0 — enable
  //   bit 1 — restart
  //--------------------------------------------------------------------
  constraint mixer_ctrl_write_data_c {
    (address[11:8] == MIXER_PREFIX &&
     address[7:0]  == ADDR_MIXER_CTRL &&
     we            == 1'b1) ->
      write_data[31:2] == 30'h0;
  }

  //--------------------------------------------------------------------
  // Debug update pulse constraint
  // debug_update should be a single-cycle pulse in most transactions.
  // Bias toward not asserting to reduce noise on the debug bus.
  //--------------------------------------------------------------------
  constraint debug_update_distribution_c {
    debug_update dist {1'b0 := 90, 1'b1 := 10};
  }

  //--------------------------------------------------------------------
  // Avalanche noise distribution
  // Physical noise should exhibit roughly balanced bit transitions.
  //--------------------------------------------------------------------
  constraint avalanche_noise_distribution_c {
    avalanche_noise dist {1'b0 := 50, 1'b1 := 50};
  }

endclass : trng_seq_item

//======================================================================
// EOF trng_seq_item.sv
//======================================================================
