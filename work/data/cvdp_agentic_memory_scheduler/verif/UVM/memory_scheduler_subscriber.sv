/*######################################################################*\
## Class Name: memory_scheduler_subscriber
## Notes:
##  - Covergroups simplified and corrected for functional accuracy.
##  - illegal_bins multi_grant fixed: original used a range [4'b0011:4'b1111]
##    which includes all valid one-hot grant values with numeric value >= 3
##    (i.e. grant3 = 4'b1000 = 8). This caused an FCIBH fatal error every time
##    requester 3 was granted. Fixed to explicitly enumerate only the 11
##    non-one-hot, non-zero patterns that are genuinely illegal DUT outputs.
##  - cross_qos_grant_prio removed: crossing four 4-bin coverpoints against
##    cp_grant produces 4^4 * 5 = 1280 cross bins, most of which are
##    unreachable, generating spurious coverage holes.
##  - cp_qos_combined overlap bins fixed: 'ascending' and 'all_different'
##    shared 8'b11_10_01_00; 'descending' and 'all_different' shared
##    8'b00_01_10_11. Duplicate values across bins cause simulator warnings
##    and double-counting. Removed the redundant 'all_different' bin.
\*######################################################################*/

class memory_scheduler_subscriber extends uvm_subscriber #(memory_scheduler_seq_item);
  `uvm_component_utils(memory_scheduler_subscriber)

  memory_scheduler_seq_item item;

  // Helper views of packed QoS field
  bit [1:0] qos0, qos1, qos2, qos3;

  function void unpack_qos();
    qos0 = item.qos[1:0];
    qos1 = item.qos[3:2];
    qos2 = item.qos[5:4];
    qos3 = item.qos[7:6];
  endfunction

  // ============================================================
  // COVERGROUP: cg_scheduler_advanced
  // ============================================================
  covergroup cg_scheduler_advanced;
    option.per_instance = 1;

    // All request patterns
    cp_request: coverpoint item.request {
      bins no_request            = {4'b0000};
      bins single_req0           = {4'b0001};
      bins single_req1           = {4'b0010};
      bins single_req2           = {4'b0100};
      bins single_req3           = {4'b1000};
      bins two_req_adjacent[]    = {4'b0011, 4'b0110, 4'b1100};
      bins two_req_nonadjacent[] = {4'b0101, 4'b1010, 4'b1001};
      bins three_req[]           = {4'b0111, 4'b1011, 4'b1101, 4'b1110};
      bins all_req               = {4'b1111};
    }

    // Grant must always be one-hot or zero — anything else is a DUT bug.
    // FIX: original used illegal_bins multi_grant = {[4'b0011:4'b1111]}.
    // The range [3:15] includes the valid one-hot value 4'b1000 (=8, grant3),
    // causing a fatal FCIBH error every time requester 3 was granted.
    // Corrected to explicitly list only the 11 non-one-hot non-zero patterns.
    cp_grant: coverpoint item.grant {
      bins no_grant = {4'b0000};
      bins grant0   = {4'b0001};
      bins grant1   = {4'b0010};
      bins grant2   = {4'b0100};
      bins grant3   = {4'b1000};
      illegal_bins multi_grant = {
        4'b0011, 4'b0101, 4'b0110, 4'b0111,
        4'b1001, 4'b1010, 4'b1011,
        4'b1100, 4'b1101, 4'b1110, 4'b1111
      };
    }

    // Individual QoS levels per requester
    cp_qos0: coverpoint qos0 { bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11}; }
    cp_qos1: coverpoint qos1 { bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11}; }
    cp_qos2: coverpoint qos2 { bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11}; }
    cp_qos3: coverpoint qos3 { bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11}; }

    // QoS combined patterns.
    // FIX: original 'all_different' bin contained 8'b11_10_01_00 and
    // 8'b00_01_10_11, which were already covered by 'ascending' and
    // 'descending' respectively. Duplicate values across bins cause
    // simulator warnings; removed the redundant 'all_different' entry.
    cp_qos_combined: coverpoint item.qos {
      bins all_same_high      = {8'b11_11_11_11};
      bins all_same_low       = {8'b00_00_00_00};
      bins all_same_mid_low   = {8'b01_01_01_01};
      bins all_same_mid_high  = {8'b10_10_10_10};
      bins ascending          = {8'b11_10_01_00};
      bins descending         = {8'b00_01_10_11};
      bins alternating_hl[]   = {8'b11_00_11_00, 8'b00_11_00_11};
      bins two_high_two_low[] = {8'b11_11_00_00, 8'b00_00_11_11};
    }

    // Memory command valid
    cp_mem_cmd_valid: coverpoint item.mem_cmd_valid {
      bins inactive = {1'b0};
      bins active   = {1'b1};
    }

    // Memory acknowledge
    cp_mem_ack: coverpoint item.mem_ack {
      bins no_ack = {1'b0};
      bins ack    = {1'b1};
    }

    // Output address range coverage
    cp_address: coverpoint item.mem_address {
      bins zero       = {32'h0000_0000};
      bins low_range  = {[32'h0000_0001:32'h0000_00FF]};
      bins aligned_4k = {32'h0000_1000, 32'h0000_2000, 32'h0000_3000};
      bins aligned_64k[]= {32'h0001_0000, 32'h0002_0000, 32'h0003_0000};
      bins high_addr  = {[32'hFFFF_0000:32'hFFFF_FFFF]};
      bins mid_range  = {[32'h0001_0000:32'h7FFF_FFFF]};
    }

    // Cross: request pattern vs QoS to verify priority arbitration
    cross_req_qos_prio: cross cp_request, cp_qos_combined {
      bins all_req_same_prio = binsof(cp_request.all_req) &&
        (binsof(cp_qos_combined.all_same_high)    ||
         binsof(cp_qos_combined.all_same_low)     ||
         binsof(cp_qos_combined.all_same_mid_low) ||
         binsof(cp_qos_combined.all_same_mid_high));
      ignore_bins no_contention = binsof(cp_request.no_request);
    }

    // Cross: memory handshake protocol
    cross_mem_handshake: cross cp_mem_cmd_valid, cp_mem_ack, cp_grant {
      bins valid_and_ack_with_grant =
        binsof(cp_mem_cmd_valid.active) && binsof(cp_mem_ack.ack) &&
        (binsof(cp_grant.grant0) || binsof(cp_grant.grant1) ||
         binsof(cp_grant.grant2) || binsof(cp_grant.grant3));
      bins valid_no_ack =
        binsof(cp_mem_cmd_valid.active) && binsof(cp_mem_ack.no_ack);
      bins idle_state =
        binsof(cp_mem_cmd_valid.inactive) && binsof(cp_mem_ack.no_ack) &&
        binsof(cp_grant.no_grant);
    }

    // Cross: grant source vs output address
    cross_grant_address: cross cp_grant, cp_address {
      bins grant0_addr = binsof(cp_grant.grant0);
      bins grant1_addr = binsof(cp_grant.grant1);
      bins grant2_addr = binsof(cp_grant.grant2);
      bins grant3_addr = binsof(cp_grant.grant3);
      ignore_bins no_grant = binsof(cp_grant.no_grant);
    }

  endgroup : cg_scheduler_advanced

  // ============================================================
  // COVERGROUP: cg_transitions
  // ============================================================
  covergroup cg_transitions;
    option.per_instance = 1;

    cp_grant_trans: coverpoint item.grant {
      bins grant_rise_0    = (4'b0000 => 4'b0001);
      bins grant_rise_1    = (4'b0000 => 4'b0010);
      bins grant_rise_2    = (4'b0000 => 4'b0100);
      bins grant_rise_3    = (4'b0000 => 4'b1000);
      bins grant_fall_0    = (4'b0001 => 4'b0000);
      bins grant_fall_1    = (4'b0010 => 4'b0000);
      bins grant_fall_2    = (4'b0100 => 4'b0000);
      bins grant_fall_3    = (4'b1000 => 4'b0000);
      bins grant_switch_01 = (4'b0001 => 4'b0010);
      bins grant_switch_12 = (4'b0010 => 4'b0100);
      bins grant_switch_23 = (4'b0100 => 4'b1000);
      bins grant_switch_30 = (4'b1000 => 4'b0001);
    }

  endgroup : cg_transitions

  // ============================================================
  // COVERGROUP: cg_arbitration_fairness
  // Sampled only when grant != 0 (see write() below).
  // ============================================================
  covergroup cg_arbitration_fairness;
    option.per_instance = 1;

    cp_granted_requestor: coverpoint item.grant {
      bins req0_served = {4'b0001};
      bins req1_served = {4'b0010};
      bins req2_served = {4'b0100};
      bins req3_served = {4'b1000};
    }

    cp_grant_sequence: coverpoint item.grant {
      bins rr_01   = (4'b0001 => 4'b0010);
      bins rr_12   = (4'b0010 => 4'b0100);
      bins rr_23   = (4'b0100 => 4'b1000);
      bins rr_30   = (4'b1000 => 4'b0001);
      bins rr_10   = (4'b0010 => 4'b0001);
      bins rr_21   = (4'b0100 => 4'b0010);
      bins rr_32   = (4'b1000 => 4'b0100);
      bins rr_03   = (4'b0001 => 4'b1000);
      bins skip_02 = (4'b0001 => 4'b0100);
      bins skip_13 = (4'b0010 => 4'b1000);
    }

  endgroup : cg_arbitration_fairness

  // ============================================================
  // COVERGROUP: cg_edge_cases
  // ============================================================
  covergroup cg_edge_cases;
    option.per_instance = 1;

    cp_req_during_valid: coverpoint item.request iff (item.mem_cmd_valid) {
      bins req_present         = {[4'b0001:4'b1111]};
      bins no_req_during_valid = {4'b0000};
    }

    cp_qos_during_valid: coverpoint item.qos iff (item.mem_cmd_valid) {
      bins qos_values = {[8'h00:8'hFF]};
    }

  endgroup : cg_edge_cases

  // ------------------------------------------------------------
  // Constructor / write / report
  // ------------------------------------------------------------
  function new(string name="memory_scheduler_subscriber", uvm_component parent=null);
    super.new(name, parent);
    cg_scheduler_advanced   = new();
    cg_transitions          = new();
    cg_arbitration_fairness = new();
    cg_edge_cases           = new();
  endfunction

  virtual function void write(memory_scheduler_seq_item t);
    item = t;
    unpack_qos();

    cg_scheduler_advanced.sample();
    cg_transitions.sample();

    if (item.grant != 4'b0000)
      cg_arbitration_fairness.sample();

    cg_edge_cases.sample();
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("COV", $sformatf(
      "Coverage summary:\n  cg_scheduler_advanced   = %0.2f%%\n  cg_transitions          = %0.2f%%\n  cg_arbitration_fairness = %0.2f%%\n  cg_edge_cases           = %0.2f%%",
      cg_scheduler_advanced.get_coverage(),
      cg_transitions.get_coverage(),
      cg_arbitration_fairness.get_coverage(),
      cg_edge_cases.get_coverage()
    ), UVM_NONE)
  endfunction

endclass : memory_scheduler_subscriber
