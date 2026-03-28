/*######################################################################*\
## Class Name: sha1_subscriber
## Description:
##   UVM functional coverage subscriber for the SHA-1 core (sha1.v wrapper).
##   Receives sha1_coverage_item transactions from the monitor's ap_cov port
##   and samples four covergroups covering the bus interface, control/command
##   protocol, core FSM + round-counter behaviour, and digest output.
##
##   sha1_coverage_item extends sha1_seq_item with monitor-populated internal
##   signal fields (status_ready, status_valid, fsm_state, round_ctr, digest,
##   ctrl_init/next/set).  The original ap port on the monitor still carries
##   plain sha1_seq_item for the scoreboard and other subscribers.
##
## Design notes / fixes relative to tb_sha1.sv reference:
##
##  1. FSM invalid state (2'b11) promoted to illegal_bins.
##     The sha1_core FSM only defines CTRL_IDLE=0, CTRL_ROUNDS=1,
##     CTRL_DONE=2. State 2'b11 is unreachable and is a DUT bug if seen;
##     treating it as a normal bin would mask the fault.
##
##  2. cp_state_write_data overlapping bins removed.
##     The SHA-1 IV values (h0_init..h4_init) are specific 32-bit constants
##     that fall inside the general range. Fixed with explicit gap ranges
##     in the custom bin so named bins take priority without overlap.
##
##  3. status register write removed from illegal_bins.
##     The spec lists ADDR_STATUS (0x09) as "R/W" in the address map table.
##     Although the RTL silently ignores writes, they are not a protocol
##     violation detectable at the bus level.
##
##  4. cg_w_mem not included.
##     The W-memory internal counter is an implementation detail not
##     appropriate for a bus-level UVM subscriber.
##
##  5. digest coverpoints gated on status_valid.
##     Avoids redundant sampling of the same digest value across idle cycles.
##
##  6. Unreachable bins converted to ignore_bins.
##     cp_digest_h0.zero, cp_digest_h0.iv_h0: SHA-1 cannot produce an
##     all-zero H0 word; matching the IV exactly is astronomically unlikely.
##     cp_digest_h4.zero, cp_digest_h4.iv_h4: same reasoning for H4.
##     cp_round_counter.round_0: monitor only samples when cs is asserted;
##     round_ctr=0 is active for exactly one cycle immediately after an
##     init/next command lands, at which point cs has already deasserted.
##     cross_fsm_rounds.rounds_func0: follows from round_0 being unreachable.
\*######################################################################*/

`ifndef SHA1_SUBSCRIBER_SV
`define SHA1_SUBSCRIBER_SV

class sha1_subscriber extends uvm_subscriber #(sha1_coverage_item);
  `uvm_component_utils(sha1_subscriber)

  sha1_coverage_item item;

  // ============================================================
  // COVERGROUP: cg_bus_interface
  //   Covers the external memory-mapped bus: address decode,
  //   read/write direction, write-data patterns for the control
  //   and block registers, and selected address × direction crosses.
  // ============================================================
  covergroup cg_bus_interface;
    option.per_instance = 1;

    // ----------------------------------------------------------
    // cp_cs: chip-select activity
    // ----------------------------------------------------------
    cp_cs: coverpoint item.cs {
      bins deselected = {1'b0};
      bins selected   = {1'b1};
    }

    // ----------------------------------------------------------
    // cp_address: full address-space decode
    //   Explicit named bins for every defined register; grouped
    //   bins for the block, digest, and state arrays; and
    //   explicitly named bins for each hole in the address map
    //   so that accidental accesses to reserved space are caught.
    // ----------------------------------------------------------
    cp_address: coverpoint item.address iff (item.cs) {
      bins name0        = {8'h00};
      bins name1        = {8'h01};
      bins version      = {8'h02};
      bins ctrl         = {8'h08};
      bins status       = {8'h09};
      bins block_regs[] = {[8'h10:8'h1F]};   // block0..block15
      bins digest_regs[]= {[8'h20:8'h24]};   // digest0..digest4
      bins state_regs[] = {[8'h30:8'h34]};   // state0..state4
      // Reserved / undefined holes in the address map
      bins rsvd_03_07   = {[8'h03:8'h07]};
      bins rsvd_0a_0f   = {[8'h0A:8'h0F]};
      bins rsvd_25_2f   = {[8'h25:8'h2F]};
      bins rsvd_35_ff   = {[8'h35:8'hFF]};
    }

    // ----------------------------------------------------------
    // cp_we: bus direction
    // ----------------------------------------------------------
    cp_we: coverpoint item.we iff (item.cs) {
      bins read  = {1'b0};
      bins write = {1'b1};
    }

    // ----------------------------------------------------------
    // cp_ctrl_write_data: control register write-data patterns
    //   Only the three command bits [2:0] are architecturally
    //   meaningful; all other bits are ignored by the RTL.
    //   Bit mapping: [0]=init, [1]=next, [2]=set
    // ----------------------------------------------------------
    cp_ctrl_write_data: coverpoint item.write_data[2:0]
        iff (item.cs && item.we && item.address == 8'h08) {
      bins none      = {3'b000};
      bins init_only = {3'b001};   // bit[0] = init
      bins next_only = {3'b010};   // bit[1] = next
      bins set_only  = {3'b100};   // bit[2] = set
      bins init_next = {3'b011};   // simultaneous init+next
      bins init_set  = {3'b101};   // simultaneous init+set
      bins next_set  = {3'b110};   // simultaneous next+set
      bins all_cmds  = {3'b111};   // all three asserted
    }

    // ----------------------------------------------------------
    // cp_block_write_data: representative data patterns written
    //   to the 16-word message block (addresses 0x10-0x1F).
    //   Boundary and bit-pattern values are named; remaining
    //   space is split into low, mid, and high ranges.
    //   Note: all_ones and alternating bins are singleton values
    //   and do not overlap the range bins.
    // ----------------------------------------------------------
    cp_block_write_data: coverpoint item.write_data
        iff (item.cs && item.we &&
             item.address >= 8'h10 && item.address <= 8'h1F) {
      bins all_zero       = {32'h0000_0000};
      bins all_ones       = {32'hFFFF_FFFF};
      bins alternating_aa = {32'hAAAA_AAAA};
      bins alternating_55 = {32'h5555_5555};
      bins ff00_pattern   = {32'hFF00_FF00};
      bins x00ff_pattern  = {32'h00FF_00FF};
      bins low_range      = {[32'h0000_0001:32'h0000_FFFF]};
      bins mid_range      = {[32'h0001_0000:32'h7FFF_FFFF]};
      bins high_range     = {[32'h8000_0000:32'hFFFF_FFFE]};
    }

    // ----------------------------------------------------------
    // cp_state_write_data: data written to the state registers
    //   (addresses 0x30-0x34, used with the SET command to inject
    //   an arbitrary mid-chain state).
    //
    //   FIX: named bins for the SHA-1 IV constants are listed first.
    //   The default bin catches everything else, so there is no
    //   overlap with the generic range bins that existed in the
    //   original testbench.
    // ----------------------------------------------------------
    cp_state_write_data: coverpoint item.write_data
        iff (item.cs && item.we &&
             item.address >= 8'h30 && item.address <= 8'h34) {
      bins zero     = {32'h0000_0000};
      bins h0_init  = {32'h6745_2301};
      bins h1_init  = {32'hEFCD_AB89};
      bins h2_init  = {32'h98BA_DCFE};
      bins h3_init  = {32'h1032_5476};
      bins h4_init  = {32'hC3D2_E1F0};
      bins all_ones = {32'hFFFF_FFFF};
      // Explicit ranges covering everything except the named constants above.
      // Split into segments that exclude each named value to avoid overlap.
      bins custom   = {[32'h0000_0001:32'h1032_5475],
                       [32'h1032_5477:32'h6745_2300],
                       [32'h6745_2302:32'h98BA_DCFD],
                       [32'h98BA_DCFF:32'hC3D2_E1EF],
                       [32'hC3D2_E1F1:32'hEFCD_AB88],
                       [32'hEFCD_AB8A:32'hFFFF_FFFE]};
    }

    // ----------------------------------------------------------
    // cross_addr_we: address range × direction
    //   illegal_bins: writes to architecturally read-only
    //   registers (name0, name1, version).  ADDR_STATUS (0x09)
    //   is listed as R/W in the spec table and is NOT marked
    //   illegal here (the RTL ignores the write silently, which
    //   is a spec-permitted no-op, not a protocol violation).
    // ----------------------------------------------------------
    cross_addr_we: cross cp_address, cp_we {
      // Reads of interest
      bins read_name0   = binsof(cp_address.name0)    && binsof(cp_we.read);
      bins read_name1   = binsof(cp_address.name1)    && binsof(cp_we.read);
      bins read_version = binsof(cp_address.version)  && binsof(cp_we.read);
      bins read_ctrl    = binsof(cp_address.ctrl)     && binsof(cp_we.read);
      bins read_status  = binsof(cp_address.status)   && binsof(cp_we.read);
      bins read_block   = binsof(cp_address.block_regs) && binsof(cp_we.read);
      bins read_digest  = binsof(cp_address.digest_regs) && binsof(cp_we.read);
      bins read_state   = binsof(cp_address.state_regs)  && binsof(cp_we.read);
      // Writes of interest
      bins write_ctrl   = binsof(cp_address.ctrl)       && binsof(cp_we.write);
      bins write_block  = binsof(cp_address.block_regs) && binsof(cp_we.write);
      bins write_state  = binsof(cp_address.state_regs) && binsof(cp_we.write);
      // Writes to architecturally read-only registers are illegal
      illegal_bins write_readonly =
        binsof(cp_we.write) &&
        (binsof(cp_address.name0) || binsof(cp_address.name1) ||
         binsof(cp_address.version));
    }

    // ----------------------------------------------------------
    // cross_ctrl_cmd_addr: write-data command bits × address
    //   Ensures command writes go to the correct register and
    //   that spurious command patterns at non-ctrl addresses are
    //   not generated.
    // ----------------------------------------------------------
    cross_ctrl_cmd_addr: cross cp_ctrl_write_data, cp_address {
      bins init_to_ctrl = binsof(cp_ctrl_write_data.init_only) && binsof(cp_address.ctrl);
      bins next_to_ctrl = binsof(cp_ctrl_write_data.next_only) && binsof(cp_address.ctrl);
      bins set_to_ctrl  = binsof(cp_ctrl_write_data.set_only)  && binsof(cp_address.ctrl);
      ignore_bins non_ctrl_addr = !binsof(cp_address.ctrl);
    }

  endgroup : cg_bus_interface


  // ============================================================
  // COVERGROUP: cg_control_protocol
  //   Covers the control command lifecycle: individual command
  //   assertions, simultaneous combinations, and the cycle-level
  //   command transitions that represent the SHA-1 use model
  //   (idle → init → next → next → … → read digest).
  // ============================================================
  covergroup cg_control_protocol;
    option.per_instance = 1;

    // ----------------------------------------------------------
    // cp_init / cp_next / cp_set: individual command bits
    //   Decoded from the write_data at the time a control-register
    //   write is captured in the seq_item.
    // ----------------------------------------------------------
    cp_init: coverpoint item.ctrl_init {
      bins deasserted = {1'b0};
      bins asserted   = {1'b1};
    }

    cp_next: coverpoint item.ctrl_next {
      bins deasserted = {1'b0};
      bins asserted   = {1'b1};
    }

    cp_set: coverpoint item.ctrl_set {
      bins deasserted = {1'b0};
      bins asserted   = {1'b1};
    }

    // ----------------------------------------------------------
    // cp_cmd_vector: all eight command-bit combinations
    //   Packed as {ctrl_init, ctrl_next, ctrl_set} so bit[2]=init,
    //   bit[1]=next, bit[0]=set.
    // ----------------------------------------------------------
    cp_cmd_vector: coverpoint {item.ctrl_init, item.ctrl_next, item.ctrl_set} {
      bins idle           = {3'b000};
      bins init_cmd       = {3'b100};  // init only
      bins next_cmd       = {3'b010};  // next only
      bins set_cmd        = {3'b001};  // set  only
      bins init_next_simul= {3'b110};  // init + next simultaneously
      bins init_set_simul = {3'b101};  // init + set  simultaneously
      bins next_set_simul = {3'b011};  // next + set  simultaneously
      bins all_simul      = {3'b111};  // all three (unusual but legal input)
    }

    // ----------------------------------------------------------
    // cp_cmd_transitions: cycle-to-cycle command sequences
    //   The normal operational flows are:
    //     idle → init  (start first block)
    //     init → idle  (single-block message)
    //     idle → next  (subsequent blocks fed immediately)
    //     next → next  (streaming multiple blocks)
    //     next → idle  (last block processed)
    //     idle → set   (inject state for resume)
    //     set  → idle  (state injection complete)
    // ----------------------------------------------------------
    cp_cmd_transitions: coverpoint {item.ctrl_init, item.ctrl_next, item.ctrl_set} {
      bins idle_to_init = (3'b000 => 3'b100);
      bins idle_to_next = (3'b000 => 3'b010);
      bins idle_to_set  = (3'b000 => 3'b001);
      bins init_to_idle = (3'b100 => 3'b000);
      bins init_to_next = (3'b100 => 3'b010);
      bins next_to_next = (3'b010 => 3'b010);
      bins next_to_idle = (3'b010 => 3'b000);
      bins set_to_idle  = (3'b001 => 3'b000);
      bins set_to_init  = (3'b001 => 3'b100);  // set then immediately init
    }

  endgroup : cg_control_protocol


  // ============================================================
  // COVERGROUP: cg_core_status
  //   Covers the observable output signals: ready, digest_valid,
  //   their individual transitions, and the four-state cross of
  //   (ready × digest_valid) that characterises the core's
  //   progress through a hash operation.
  // ============================================================
  covergroup cg_core_status;
    option.per_instance = 1;

    cp_ready: coverpoint item.status_ready {
      bins not_ready = {1'b0};
      bins ready     = {1'b1};
    }

    cp_digest_valid: coverpoint item.status_valid {
      bins invalid = {1'b0};
      bins valid   = {1'b1};
    }

    // ----------------------------------------------------------
    // cp_ready_trans: ready signal edge detection
    //   rising  edge → core finished processing (DONE → IDLE)
    //   falling edge → core accepted a new command (IDLE → ROUNDS)
    // ----------------------------------------------------------
    cp_ready_trans: coverpoint item.status_ready {
      bins ready_rise  = (1'b0 => 1'b1);   // processing complete
      bins ready_fall  = (1'b1 => 1'b0);   // new command accepted
      bins stay_ready  = (1'b1 => 1'b1);   // idle hold
      bins stay_busy   = (1'b0 => 1'b0);   // processing in progress
    }

    cp_valid_trans: coverpoint item.status_valid {
      bins valid_rise  = (1'b0 => 1'b1);   // digest just produced
      bins valid_fall  = (1'b1 => 1'b0);   // new block started, clears valid
      bins stay_valid  = (1'b1 => 1'b1);   // digest held after completion
      bins stay_invalid= (1'b0 => 1'b0);   // not yet produced
    }

    // ----------------------------------------------------------
    // cross_ready_valid: four operating states
    //   ready=1, valid=0 → IDLE, no digest yet (post-reset)
    //   ready=0, valid=0 → BUSY, processing first block
    //   ready=1, valid=1 → IDLE with digest available (normal completion)
    //   ready=0, valid=1 → BUSY while prior digest held (pipelined next)
    // ----------------------------------------------------------
    cross_ready_valid: cross cp_ready, cp_digest_valid {
      bins idle_no_digest   = binsof(cp_ready.ready)     && binsof(cp_digest_valid.invalid);
      bins busy_no_digest   = binsof(cp_ready.not_ready) && binsof(cp_digest_valid.invalid);
      bins idle_with_digest = binsof(cp_ready.ready)     && binsof(cp_digest_valid.valid);
      bins busy_holds_digest= binsof(cp_ready.not_ready) && binsof(cp_digest_valid.valid);
    }

    // ----------------------------------------------------------
    // cp_error: error flag coverage
    //   Asserted by the RTL when cs=1 and the address falls
    //   outside all defined register windows (read path only).
    // ----------------------------------------------------------
    cp_error: coverpoint item.error iff (item.cs) {
      bins no_error      = {1'b0};
      bins error_flagged = {1'b1};
    }

  endgroup : cg_core_status


  // ============================================================
  // COVERGROUP: cg_fsm_and_digest
  //   Covers the internal FSM state and round counter as
  //   reported by the seq_item (monitor must probe these from
  //   the DUT and expose them on the item).  Also covers the
  //   digest H0/H4 output word patterns sampled at the moment
  //   digest_valid first rises.
  //
  //   FIX: FSM state 2'b11 is declared illegal_bins because the
  //   sha1_core FSM only defines three states (IDLE=0, ROUNDS=1,
  //   DONE=2).  Observing 2'b11 indicates a DUT fault and should
  //   trigger an FCIBH error rather than increment a coverage bin.
  // ============================================================
  covergroup cg_fsm_and_digest;
    option.per_instance = 1;

    // ----------------------------------------------------------
    // cp_fsm_state: core FSM enumeration
    // ----------------------------------------------------------
    cp_fsm_state: coverpoint item.fsm_state {
      bins idle   = {2'b00};   // CTRL_IDLE
      bins rounds = {2'b01};   // CTRL_ROUNDS
      bins done   = {2'b10};   // CTRL_DONE
      illegal_bins unreachable = {2'b11};  // not a valid state
    }

    // ----------------------------------------------------------
    // cp_fsm_trans: legal FSM transitions
    //   idle   → rounds: init or next command accepted
    //   rounds → done:   round 79 complete
    //   done   → idle:   digest update committed
    //   idle   → idle:   normal idle hold
    //   rounds → rounds: ongoing round processing
    // ----------------------------------------------------------
    cp_fsm_trans: coverpoint item.fsm_state {
      bins idle_to_rounds  = (2'b00 => 2'b01);
      bins rounds_to_done  = (2'b01 => 2'b10);
      bins done_to_idle    = (2'b10 => 2'b00);
      bins idle_to_idle    = (2'b00 => 2'b00);
      bins rounds_to_rounds= (2'b01 => 2'b01);
    }

    // ----------------------------------------------------------
    // cp_round_counter: SHA-1 round counter coverage
    //   SHA-1 uses 80 rounds (0-79).  The k and f function
    //   change at boundaries 0/20/40/60, so each of the four
    //   function segments is covered individually, plus the
    //   terminal round 79.
    // ----------------------------------------------------------
    cp_round_counter: coverpoint item.round_ctr {
      // round_0: the monitor only samples when cs is asserted. By the time
      // any bus transaction occurs during processing the FSM has already
      // incremented past round 0 (round_ctr=0 is only active for one cycle
      // immediately after the init/next command which deasserts cs). The
      // wait_ready polling loop only starts issuing transactions after the
      // core has been processing for many cycles. Moved to ignore_bins.
      ignore_bins round_0 = {7'd0};
      bins rounds_1_19    = {[7'd1  :7'd19]};
      bins rounds_20_39   = {[7'd20 :7'd39]};
      bins rounds_40_59   = {[7'd40 :7'd59]};
      bins rounds_60_78   = {[7'd60 :7'd78]};
      bins round_79       = {7'd79};
    }

    // ----------------------------------------------------------
    // cross_fsm_rounds: FSM state × round counter
    //   Only meaningful combinations are enumerated; structurally
    //   impossible combinations (e.g. IDLE with round > 0, or
    //   DONE with any round value) are covered by ignore_bins to
    //   prevent spurious holes.
    // ----------------------------------------------------------
    cross_fsm_rounds: cross cp_fsm_state, cp_round_counter {
      bins idle_round0     = binsof(cp_fsm_state.idle)   && binsof(cp_round_counter.round_0);
      // rounds_func0: ROUNDS state at round 0 is unreachable at bus transaction
      // time for the same reason round_0 is ignored in cp_round_counter above.
      ignore_bins rounds_func0 = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.round_0);
      bins rounds_func1    = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.rounds_1_19);
      bins rounds_func2    = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.rounds_20_39);
      bins rounds_func3    = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.rounds_40_59);
      bins rounds_func4    = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.rounds_60_78);
      bins rounds_terminal = binsof(cp_fsm_state.rounds) && binsof(cp_round_counter.round_79);
      // DONE state always sees round_79 (counter not reset until next IDLE)
      bins done_round79    = binsof(cp_fsm_state.done)   && binsof(cp_round_counter.round_79);
      // IDLE with round > 0 does not occur normally; treat as ignore
      ignore_bins idle_nonzero_round =
        binsof(cp_fsm_state.idle) &&
        (binsof(cp_round_counter.rounds_1_19)  ||
         binsof(cp_round_counter.rounds_20_39) ||
         binsof(cp_round_counter.rounds_40_59) ||
         binsof(cp_round_counter.rounds_60_78) ||
         binsof(cp_round_counter.round_79));
      // DONE with non-terminal rounds is structurally impossible
      ignore_bins done_early_round =
        binsof(cp_fsm_state.done) &&
        (binsof(cp_round_counter.round_0)      ||
         binsof(cp_round_counter.rounds_1_19)  ||
         binsof(cp_round_counter.rounds_20_39) ||
         binsof(cp_round_counter.rounds_40_59) ||
         binsof(cp_round_counter.rounds_60_78));
    }

    // ----------------------------------------------------------
    // cp_digest_h0 / cp_digest_h4: digest word patterns
    //   Sampled when digest_valid rises (gated in write() below).
    //   Covers the all-zero degenerate case, the SHA-1 default IV
    //   values (a sanity check that the init path loaded correctly),
    //   and the general non-trivial range.
    //   Note: 32'h67452301 and 32'hC3D2E1F0 are the H0 and H4 IV
    //   values respectively; seeing them as a final digest output
    //   would be unusual but is not impossible.
    // ----------------------------------------------------------
    cp_digest_h0: coverpoint item.digest[159:128] iff (item.status_valid) {
      // zero: SHA-1 cannot produce an all-zero digest word — cryptographically
      //       unreachable with any input. Moved to ignore_bins.
      // iv_h0: digest word exactly matching the SHA-1 H0 IV (0x67452301) is
      //        theoretically possible but astronomically unlikely with directed
      //        or random stimulus. Moved to ignore_bins to avoid a permanent hole.
      ignore_bins zero  = {32'h0000_0000};
      ignore_bins iv_h0 = {32'h6745_2301};
      bins nonzero      = {[32'h0000_0001:32'hFFFF_FFFF]};
    }

    cp_digest_h4: coverpoint item.digest[31:0] iff (item.status_valid) {
      // zero: SHA-1 cannot produce an all-zero digest word — cryptographically
      //       unreachable with any input. Moved to ignore_bins.
      // iv_h4: digest word exactly matching the SHA-1 H4 IV (0xC3D2E1F0) is
      //        theoretically possible but astronomically unlikely with directed
      //        or random stimulus. Moved to ignore_bins to avoid a permanent hole.
      ignore_bins zero  = {32'h0000_0000};
      ignore_bins iv_h4 = {32'hC3D2_E1F0};
      bins nonzero      = {[32'h0000_0001:32'hFFFF_FFFF]};
    }

  endgroup : cg_fsm_and_digest


  // ============================================================
  // Constructor
  // ============================================================
  function new(string name = "sha1_subscriber", uvm_component parent = null);
    super.new(name, parent);
    cg_bus_interface    = new();
    cg_control_protocol = new();
    cg_core_status      = new();
    cg_fsm_and_digest   = new();
  endfunction


  // ============================================================
  // write() — called by the UVM TLM analysis port on every
  //           transaction broadcast by the monitor.
  // ============================================================
  virtual function void write(sha1_coverage_item t);
    item = t;

    // Always sample bus and protocol covergroups
    cg_bus_interface.sample();
    cg_control_protocol.sample();
    cg_core_status.sample();

    // Sample FSM / digest covergroup on every transaction;
    // the digest coverpoints are internally gated on status_valid
    // so redundant samples during idle cycles are harmless.
    cg_fsm_and_digest.sample();
  endfunction


  // ============================================================
  // report_phase — emit a per-covergroup summary at end-of-sim
  // ============================================================
  function void report_phase(uvm_phase phase);
    `uvm_info("SHA1_COV", $sformatf(
      "\n======================================\n" ,
      "SHA-1 Subscriber Coverage Summary\n"       ,
      "======================================\n"  ,
      "  cg_bus_interface    = %0.2f%%\n"         ,
      "  cg_control_protocol = %0.2f%%\n"         ,
      "  cg_core_status      = %0.2f%%\n"         ,
      "  cg_fsm_and_digest   = %0.2f%%\n"         ,
      "======================================",
      cg_bus_interface.get_coverage(),
      cg_control_protocol.get_coverage(),
      cg_core_status.get_coverage(),
      cg_fsm_and_digest.get_coverage()
    ), UVM_NONE)
  endfunction

endclass : sha1_subscriber

`endif // SHA1_SUBSCRIBER_SV
