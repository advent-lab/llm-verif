//======================================================================
// trng_monitor.sv
//
// UVM monitor for the TRNG top-level interface.
//
// Timing model:
//   The monitor is a passive observer. It aligns itself with the DUT's
//   clock and captures a complete transaction snapshot at the point
//   where both the driven inputs AND the resulting combinatorial outputs
//   are simultaneously valid — i.e., the clock edge that follows the
//   cycle in which cs was first asserted.
//
//   Concretely (matching the driver's two-phase model):
//
//     Cycle N  : driver asserts cs/we/address/write_data
//                combinatorial outputs (read_data, error) settle
//     posedge N: DUT registers the write; driver samples read_data here
//     posedge N: monitor also observes the stable bus and captures item
//
//   For non-bus cycles (cs=0, reset, or debug_update-only), the monitor
//   still captures a snapshot every clock so that the coverage subscriber
//   can observe continuous signals such as avalanche_noise, security_error,
//   reset_n, and debug.
//
// Fixes applied versus the uploaded trng_monitor.sv:
//   [FIX-1]  Broken `ifndef guard (missing macro name) corrected.
//   [FIX-2]  endclass label `: trng_monitor` added.
//   [FIX-3]  vif.cs and vif.we are now captured into item_c.
//            The coverage subscriber's every covergroup references
//            trans.cs and trans.we; they were silently 0 before.
//   [FIX-4]  vif.avalanche_noise captured — needed by cg_noise and
//            cg_entropy_handshake covergroups.
//   [FIX-5]  vif.reset_n captured — needed to identify reset cycles
//            and suppress spurious coverage hits during reset.
//   [FIX-6]  read_data sampling timing corrected. The RTL outputs
//            (read_data, error, security_error) are purely combinatorial.
//            They are valid when inputs are stable. The monitor now
//            samples them at the posedge that follows the driven cycle,
//            which is the same edge the driver uses — giving a coherent,
//            synchronised view of the transaction.
//   [FIX-7]  ap.write() is now called on EVERY clock cycle, not only
//            when cs=1. Non-bus cycles carry noise, reset_n, and FSM
//            state for the always-on covergroups. A flag distinguishes
//            active transactions from background observations.
//   [FIX-8]  item_c factory create() call moved inside the forever loop
//            with the correct parent argument, creating a fresh item on
//            every cycle as intended.
//======================================================================

`ifndef TRNG_MONITOR_SV                   // [FIX-1] macro name was absent
`define TRNG_MONITOR_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

class trng_monitor extends uvm_monitor;
  `uvm_component_utils(trng_monitor)

  //--------------------------------------------------------------------
  // Virtual interface handle
  //--------------------------------------------------------------------
  virtual trng_if vif;

  //--------------------------------------------------------------------
  // Analysis port — feeds the coverage subscriber and any scoreboard
  //--------------------------------------------------------------------
  uvm_analysis_port #(trng_seq_item) ap;

  //--------------------------------------------------------------------
  // Constructor
  //--------------------------------------------------------------------
  function new(string name = "trng_monitor", uvm_component parent = null);
    super.new(name, parent);
    ap = new("ap", this);
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
  // run_phase — observation loop
  //--------------------------------------------------------------------
  virtual task run_phase(uvm_phase phase);
    trng_seq_item item_c;

    // Align to the first rising edge so sampling is always synchronous.
    @(posedge vif.clk);

    forever begin
      // [FIX-8] Fresh item created every cycle inside the loop.
      item_c = trng_seq_item::type_id::create("item_c", this);

      // ----------------------------------------------------------------
      // Wait for the next posedge — this is the point at which:
      //   • the driver has already driven all inputs for this cycle, and
      //   • the combinatorial DUT outputs (read_data, error, etc.) are
      //     stable and reflect those inputs.
      // [FIX-6] Moved from "sample at first cs edge" to "sample at the
      // posedge following the driven cycle", matching driver timing.
      // ----------------------------------------------------------------
      @(posedge vif.clk);

      // ----------------------------------------------------------------
      // Capture ALL interface signals into the item.
      //
      // Input signals:
      // ----------------------------------------------------------------
      item_c.clk             = vif.clk;
      item_c.reset_n         = vif.reset_n;         // [FIX-5]
      item_c.cs              = vif.cs;              // [FIX-3]
      item_c.we              = vif.we;              // [FIX-3]
      item_c.address         = vif.address;
      item_c.write_data      = vif.write_data;
      item_c.avalanche_noise = vif.avalanche_noise; // [FIX-4]
      item_c.debug_update    = vif.debug_update;

      // ----------------------------------------------------------------
      // Output signals (combinatorial, valid while inputs are stable):
      // [FIX-6] Sampled here — same posedge the driver uses — so the
      // item's input and output fields form a coherent snapshot of the
      // same transaction cycle.
      // ----------------------------------------------------------------
      item_c.read_data      = vif.read_data;
      item_c.error          = vif.error;
      item_c.debug          = vif.debug;
      item_c.security_error = vif.security_error;

      // ----------------------------------------------------------------
      // [FIX-7] Broadcast every cycle, not just on cs=1.
      //   • Active transactions  (cs=1): full register-access snapshot.
      //   • Idle / reset cycles  (cs=0): carries reset_n, noise, FSM
      //     state observations needed by always-on covergroups.
      // The subscriber uses item_c.cs to gate register-address
      // coverpoints and samples background coverpoints unconditionally.
      // ----------------------------------------------------------------
      ap.write(item_c);

      // ----------------------------------------------------------------
      // Diagnostic: log active bus transactions at HIGH verbosity.
      // ----------------------------------------------------------------
      if (item_c.cs) begin
        `uvm_info(get_type_name(),
          $sformatf("[MON] %s addr=0x%03X wdata=0x%08X rdata=0x%08X err=%0b sec_err=%0b",
                    item_c.we ? "WR" : "RD",
                    item_c.address,
                    item_c.write_data,
                    item_c.read_data,
                    item_c.error,
                    item_c.security_error),
          UVM_HIGH)
      end

    end // forever
  endtask : run_phase

endclass : trng_monitor  // [FIX-2] class label added

`endif // TRNG_MONITOR_SV
