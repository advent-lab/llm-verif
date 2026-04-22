`ifndef SHA1_SEQ_ITEM_SV
`define SHA1_SEQ_ITEM_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

// =============================================================================
// sha1_seq_item
//   Base transaction item carrying the external bus interface signals.
//   Used by the driver, sequencer, scoreboard, and original analysis port.
// =============================================================================
class sha1_seq_item extends uvm_sequence_item;

  // Clock and reset (never randomized)
  bit clk;
  bit reset_n;

  // Input signals (randomized)
  rand bit        cs;             // Chip select
  rand bit        we;             // Write enable
  rand bit [7:0]  address;        // Address bus
  rand bit [31:0] write_data;     // Write data bus

  // Output signals (not randomized — populated by monitor)
  bit [31:0] read_data;           // Read data bus
  bit        error;               // Error signal

  // ------------------------------------------------------------------
  // Address map constants
  // ------------------------------------------------------------------
  localparam int ADDR_NAME0    = 8'h00;
  localparam int ADDR_NAME1    = 8'h01;
  localparam int ADDR_VERSION  = 8'h02;
  localparam int ADDR_CONTROL  = 8'h08;
  localparam int ADDR_STATUS   = 8'h09;
  localparam int ADDR_BLOCK0   = 8'h10;
  localparam int ADDR_BLOCK15  = 8'h1F;
  localparam int ADDR_DIGEST0  = 8'h20;
  localparam int ADDR_DIGEST4  = 8'h24;
  localparam int ADDR_STATE0   = 8'h30;
  localparam int ADDR_STATE4   = 8'h34;

  // Register access type encoding
  typedef enum bit [1:0] {REG_READ, REG_WRITE, REG_RW, REG_RESERVED} reg_access_e;

  // ------------------------------------------------------------------
  // UVM field registration
  // ------------------------------------------------------------------
  `uvm_object_utils_begin(sha1_seq_item)
    `uvm_field_int(clk,        UVM_ALL_ON)
    `uvm_field_int(reset_n,    UVM_ALL_ON)
    `uvm_field_int(cs,         UVM_ALL_ON)
    `uvm_field_int(we,         UVM_ALL_ON)
    `uvm_field_int(address,    UVM_ALL_ON)
    `uvm_field_int(write_data, UVM_ALL_ON)
    `uvm_field_int(read_data,  UVM_ALL_ON)
    `uvm_field_int(error,      UVM_ALL_ON)
  `uvm_object_utils_end

  // ------------------------------------------------------------------
  // Constructor
  // ------------------------------------------------------------------
  function new(string name = "sha1_seq_item");
    super.new(name);
    clk        = 0;
    reset_n    = 1;
    cs         = 0;
    we         = 0;
    address    = '0;
    write_data = '0;
    read_data  = '0;
    error      = 0;
  endfunction

  // ------------------------------------------------------------------
  // Constraints
  // ------------------------------------------------------------------

  // Valid address space — includes state registers (0x30-0x34) and
  // reserved holes so error-path coverage bins can be hit.
  constraint c_addr_range {
    address inside {
      [ADDR_NAME0:ADDR_NAME1],    // 0x00-0x01
      ADDR_VERSION,               // 0x02
      ADDR_CONTROL,               // 0x08
      ADDR_STATUS,                // 0x09
      [ADDR_BLOCK0:ADDR_BLOCK15], // 0x10-0x1F
      [ADDR_DIGEST0:ADDR_DIGEST4],// 0x20-0x24
      [ADDR_STATE0:ADDR_STATE4],  // 0x30-0x34
      // Reserved holes — allow occasionally to exercise error flag
      [8'h03:8'h07],
      [8'h0A:8'h0F],
      [8'h25:8'h2F],
      [8'h35:8'hFF]
    };
  }

  // Writes only permitted to writable registers
  constraint c_we_access {
    if (address inside {ADDR_NAME0, ADDR_NAME1, ADDR_VERSION})
      we == 0;
    else
      we inside {0, 1};
  }

  // write_data only meaningful on write cycles
  constraint c_write_data_valid {
    if (!we) write_data == 32'h0;
  }

  // cs always asserted — deselected cycles not modelled at item level
  constraint c_cs_active {
    cs == 1;
  }

  // reset_n asserted for normal operation
  constraint c_reset_n_active {
    reset_n == 1;
  }

endclass : sha1_seq_item


// =============================================================================
// sha1_coverage_item
//   Extends sha1_seq_item with monitor-populated fields for internal DUT
//   signals not visible on the external bus.  These fields are NEVER
//   randomized — the monitor writes them after probing the DUT each cycle.
//   Consumed exclusively by sha1_subscriber via the monitor's ap_cov port.
//
//   Fields added:
//     ctrl_init    — write_data[0] latched on a ctrl-register write cycle
//     ctrl_next    — write_data[1] latched on a ctrl-register write cycle
//     ctrl_set     — write_data[2] latched on a ctrl-register write cycle
//     status_ready — dut.ready_reg
//     status_valid — dut.digest_valid_reg
//     fsm_state    — dut.core.sha1_ctrl_reg  (2-bit: 0=IDLE,1=ROUNDS,2=DONE)
//     round_ctr    — dut.core.round_ctr_reg  (7-bit: 0-79)
//     digest       — dut.digest_reg          (160-bit)
//
// Note on UVM macros:
//   `uvm_object_utils_begin/end is intentionally NOT used here.
//   Using it on a derived class re-declares type_id, get_type, create,
//   and other factory symbols that the parent already generated, causing
//   IPD (identifier previously declared) compile errors.  The child's
//   additional fields are instead covered by do_copy, do_compare, and
//   do_print overrides below.
// =============================================================================
class sha1_coverage_item extends sha1_seq_item;

  `uvm_object_utils(sha1_coverage_item)

  // ------------------------------------------------------------------
  // Monitor-populated fields — NOT rand
  // ------------------------------------------------------------------
  bit         ctrl_init;    // decoded from write_data[0] on ctrl-reg write
  bit         ctrl_next;    // decoded from write_data[1] on ctrl-reg write
  bit         ctrl_set;     // decoded from write_data[2] on ctrl-reg write

  bit         status_ready; // dut.ready_reg
  bit         status_valid; // dut.digest_valid_reg

  bit [1:0]   fsm_state;    // dut.core.sha1_ctrl_reg (0=IDLE,1=ROUNDS,2=DONE)
  bit [6:0]   round_ctr;    // dut.core.round_ctr_reg (0-79)
  bit [159:0] digest;       // dut.digest_reg

  // ------------------------------------------------------------------
  // Constructor
  // ------------------------------------------------------------------
  function new(string name = "sha1_coverage_item");
    super.new(name);
    ctrl_init    = 0;
    ctrl_next    = 0;
    ctrl_set     = 0;
    status_ready = 0;
    status_valid = 0;
    fsm_state    = 2'b00;
    round_ctr    = 7'd0;
    digest       = 160'h0;
  endfunction

  // ------------------------------------------------------------------
  // do_copy — propagates child fields through copy/clone operations
  // ------------------------------------------------------------------
  virtual function void do_copy(uvm_object rhs);
    sha1_coverage_item rhs_;
    super.do_copy(rhs);
    if (!$cast(rhs_, rhs))
      `uvm_fatal("DO_COPY", "Cast failed in sha1_coverage_item::do_copy")
    ctrl_init    = rhs_.ctrl_init;
    ctrl_next    = rhs_.ctrl_next;
    ctrl_set     = rhs_.ctrl_set;
    status_ready = rhs_.status_ready;
    status_valid = rhs_.status_valid;
    fsm_state    = rhs_.fsm_state;
    round_ctr    = rhs_.round_ctr;
    digest       = rhs_.digest;
  endfunction

  // ------------------------------------------------------------------
  // do_compare — includes child fields in equality checks
  // ------------------------------------------------------------------
  virtual function bit do_compare(uvm_object rhs, uvm_comparer comparer);
    sha1_coverage_item rhs_;
    if (!$cast(rhs_, rhs)) return 0;
    return (super.do_compare(rhs, comparer)  &&
            ctrl_init    === rhs_.ctrl_init    &&
            ctrl_next    === rhs_.ctrl_next    &&
            ctrl_set     === rhs_.ctrl_set     &&
            status_ready === rhs_.status_ready &&
            status_valid === rhs_.status_valid &&
            fsm_state    === rhs_.fsm_state    &&
            round_ctr    === rhs_.round_ctr    &&
            digest       === rhs_.digest);
  endfunction

  // ------------------------------------------------------------------
  // do_print — includes child fields in UVM printer/logger output
  // ------------------------------------------------------------------
  virtual function void do_print(uvm_printer printer);
    super.do_print(printer);
    printer.print_field_int("ctrl_init",    ctrl_init,    1);
    printer.print_field_int("ctrl_next",    ctrl_next,    1);
    printer.print_field_int("ctrl_set",     ctrl_set,     1);
    printer.print_field_int("status_ready", status_ready, 1);
    printer.print_field_int("status_valid", status_valid, 1);
    printer.print_field_int("fsm_state",    fsm_state,    2);
    printer.print_field_int("round_ctr",    round_ctr,    7);
    printer.print_field_int("digest",       digest,       160);
  endfunction

endclass : sha1_coverage_item

`endif // SHA1_SEQ_ITEM_SV
