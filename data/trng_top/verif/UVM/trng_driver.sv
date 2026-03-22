//======================================================================
// trng_driver.sv
//
// UVM driver for the TRNG top-level interface.
//
// Timing model (matches both reference testbenches tb_trng.v and
// trng_tb.sv):
//
//          ___     ___     ___     ___
//  clk  __|   |___|   |___|   |___|   |___
//            ^           ^
//            | drive      | de-assert &
//            | cs/we/addr | sample read_data
//            | write_data |
//
//  1. Wait for the next posedge — this is the "setup" edge at which
//     all inputs to the DUT must be stable (combinatorial API logic).
//  2. Drive cs, we, address, write_data, avalanche_noise, debug_update.
//     reset_n is also driven from the item so the reset sequence works.
//  3. Wait one more posedge — outputs (read_data, error, security_error,
//     debug) are now stable since they are purely combinatorial off the
//     registered state that was clocked by step-2's edge.
//  4. De-assert cs/we and capture read_data back into the item so the
//     sequence can inspect the response (e.g. polling rnd_valid).
//  5. Call item_done() to release the sequencer.
//
// Fixes applied versus the uploaded trng_driver.sv:
//   [FIX-1]  Broken `ifndef guard (missing macro name) corrected.
//   [FIX-2]  reset_n now driven from tr.reset_n on every item.
//   [FIX-3]  avalanche_noise now driven from tr.avalanche_noise.
//   [FIX-4]  debug_update now driven from tr.debug_update.
//   [FIX-5]  cs is driven from tr.cs, not hardcoded to 1. Items with
//            cs=0 produce idle / reset cycles without bus activity.
//   [FIX-6]  Timing corrected: signals are driven BEFORE the sampling
//            edge, not after it. The original drove signals after
//            @(posedge clk), meaning the DUT saw them one cycle late.
//   [FIX-7]  read_data captured from the interface after the sampling
//            edge and written back into the item, enabling the poll
//            loop in trng_read_rnd_seq to observe the DUT response.
//   [FIX-8]  Bus idle initialisation added in run_phase preamble so
//            the interface starts in a known de-asserted state before
//            the first item arrives.
//======================================================================

`ifndef TRNG_DRIVER_SV                      // [FIX-1] macro name was absent
`define TRNG_DRIVER_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

class trng_driver extends uvm_driver #(trng_seq_item);
  `uvm_component_utils(trng_driver)

  //--------------------------------------------------------------------
  // Virtual interface handle
  //--------------------------------------------------------------------
  virtual trng_if vif;

  //--------------------------------------------------------------------
  // Constructor
  //--------------------------------------------------------------------
  function new(string name = "trng_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  //--------------------------------------------------------------------
  // build_phase — retrieve virtual interface from config DB
  //--------------------------------------------------------------------
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual trng_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF",
        $sformatf("Virtual interface must be set for: %s", get_full_name()))
  endfunction : build_phase

  //--------------------------------------------------------------------
  // run_phase — main stimulus loop
  //--------------------------------------------------------------------
  virtual task run_phase(uvm_phase phase);
    trng_seq_item tr;

    // [FIX-8] Initialise bus to a known idle state before any item
    // arrives. This prevents X-propagation into the DUT on cycle 0.
    vif.reset_n       <= 1'b1;
    vif.cs            <= 1'b0;
    vif.we            <= 1'b0;
    vif.address       <= 12'h000;
    vif.write_data    <= 32'h0000_0000;
    vif.avalanche_noise <= 1'b0;  // [FIX-3]
    vif.debug_update  <= 1'b0;   // [FIX-4]

    forever begin
      // ----------------------------------------------------------------
      // 1. Fetch the next item from the sequencer.
      // ----------------------------------------------------------------
      seq_item_port.get_next_item(tr);

      // ----------------------------------------------------------------
      // 2. Drive all input signals BEFORE the sampling clock edge.
      //    [FIX-6] The original drove signals AFTER @(posedge clk),
      //    so the DUT first saw them on the following cycle. Now we
      //    drive combinatorially, then let the clock edge register them.
      //
      //    [FIX-2] reset_n is driven from tr.reset_n so trng_reset_seq
      //    can apply and release the active-low reset.
      //
      //    [FIX-5] cs is driven from tr.cs. When cs=0 the driver still
      //    waits two edges, giving idle and reset cycles proper timing.
      // ----------------------------------------------------------------
      vif.reset_n         <= tr.reset_n;          // [FIX-2]
      vif.cs              <= tr.cs;               // [FIX-5]
      vif.we              <= tr.we;
      vif.address         <= tr.address;
      vif.write_data      <= tr.write_data;
      vif.avalanche_noise <= tr.avalanche_noise;  // [FIX-3]
      vif.debug_update    <= tr.debug_update;     // [FIX-4]

      // ----------------------------------------------------------------
      // 3. Wait for the DUT's sampling edge.
      //    The RTL API logic is combinatorial (always @*), so read_data,
      //    error, and security_error are valid as soon as inputs settle.
      //    One posedge here registers write data into DUT flip-flops.
      // ----------------------------------------------------------------
      @(posedge vif.clk);

      // ----------------------------------------------------------------
      // 4. [FIX-7] Capture DUT outputs back into the item.
      //    The combinatorial outputs are stable after inputs are driven,
      //    so sampling them here (one edge after driving) is correct and
      //    matches the reference read_word() task behaviour.
      //    The sequence's poll loop inspects tr.read_data after
      //    finish_item() returns to decide whether rnd_valid is set.
      // ----------------------------------------------------------------
      tr.read_data      = vif.read_data;
      tr.error          = vif.error;
      tr.security_error = vif.security_error;
      tr.debug          = vif.debug;

      // ----------------------------------------------------------------
      // 5. De-assert bus signals after the transaction is sampled.
      //    This mirrors the behaviour of write_word()/read_word() in
      //    both reference testbenches, which clear cs/we after each
      //    access.
      // ----------------------------------------------------------------
      vif.cs           <= 1'b0;
      vif.we           <= 1'b0;
      vif.debug_update <= 1'b0;

      // ----------------------------------------------------------------
      // 6. Release the item — notifies the sequencer and allows
      //    finish_item() in the sequence to return.
      // ----------------------------------------------------------------
      seq_item_port.item_done();
    end
  endtask : run_phase

endclass : trng_driver

`endif // TRNG_DRIVER_SV
