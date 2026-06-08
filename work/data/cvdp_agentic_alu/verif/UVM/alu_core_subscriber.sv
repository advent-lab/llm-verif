/*######################################################################*\
## Class Name: alu_core_subscriber
## Description:
##   Functional coverage subscriber for alu_core
##   Uses alu_core_seq_item fields directly
\*######################################################################*/

import uvm_pkg::*;
`include "uvm_macros.svh"

class alu_core_subscriber extends uvm_subscriber #(alu_core_seq_item);

  `uvm_component_utils(alu_core_subscriber)

  // Local handle to sampled transaction
  alu_core_seq_item item;

  // ================================================================
  // Covergroup 1: Advanced ALU Functional Coverage
  // ================================================================

  covergroup cg_alu_advanced;

    option.per_instance = 1;

    // ------------------------------------------------------------
    // Opcode coverage
    // ------------------------------------------------------------
    cp_opcode: coverpoint item.opcode {
      bins add    = {4'h0};
      bins sub    = {4'h1};
      bins mul    = {4'h2};
      bins div    = {4'h3};
      bins and_op = {4'h4};
      bins or_op  = {4'h5};
      bins xor_op = {4'h6};
      bins invalid[] = {[4'h7:4'hF]};
    }

    // ------------------------------------------------------------
    // Operand1 coverage
    // ------------------------------------------------------------
    cp_operand1: coverpoint item.operand1 {
      bins zero    = {0};
      bins one     = {1};
      bins neg_one = {-1};
      bins max_pos = {32'sh7FFFFFFF};
      bins max_neg = {32'sh80000000};
      bins small_pos = {[2:100]};
      bins small_neg = {[-100:-2]};
    }

    // ------------------------------------------------------------
    // Operand2 coverage
    // ------------------------------------------------------------
    cp_operand2: coverpoint item.operand2 {
      bins zero    = {0};
      bins one     = {1};
      bins neg_one = {-1};
      bins max_pos = {32'sh7FFFFFFF};
      bins max_neg = {32'sh80000000};
    }

    // ------------------------------------------------------------
    // Operand3 coverage
    // ------------------------------------------------------------
    cp_operand3: coverpoint item.operand3 {
      bins zero    = {0};
      bins one     = {1};
      bins neg_one = {-1};
      bins max_pos = {32'sh7FFFFFFF};
      bins max_neg = {32'sh80000000};
    }

    // ------------------------------------------------------------
    // Result coverage
    // ------------------------------------------------------------
    cp_result: coverpoint item.result {
      bins zero    = {0};
      bins one     = {1};
      bins neg_one = {-1};
      bins max_pos = {32'sh7FFFFFFF};
      bins max_neg = {32'sh80000000};
      bins positive = {[2:32'sh7FFFFFFE]};
      bins negative = {[32'sh80000001:-2]};
    }

    // ------------------------------------------------------------
    // Arithmetic overflow cross
    // ------------------------------------------------------------
    cross_arith_overflow: cross cp_opcode, cp_operand1, cp_operand2 {
      ignore_bins non_arith =
        binsof(cp_opcode) intersect {[4'h3:4'hF]};
    }

    // ------------------------------------------------------------
    // Division corner cases
    // ------------------------------------------------------------
    cross_div_corner: cross cp_opcode, cp_operand2 {
      bins div_by_zero =
        binsof(cp_opcode.div) && binsof(cp_operand2.zero);

      bins div_by_one =
        binsof(cp_opcode.div) && binsof(cp_operand2.one);

      ignore_bins non_div =
        binsof(cp_opcode) intersect {[4'h0:4'h2], [4'h4:4'hF]};
    }

    // ------------------------------------------------------------
    // Bitwise pattern cross
    // ------------------------------------------------------------
    cross_bitwise_patterns: cross cp_opcode, cp_operand1, cp_operand2 {
      ignore_bins non_bitwise =
        binsof(cp_opcode) intersect {[4'h0:4'h3], [4'h7:4'hF]};
    }

  endgroup


  // ================================================================
  // Covergroup 2: Sign Combination Coverage
  // ================================================================

  covergroup cg_sign_combinations;

    option.per_instance = 1;

    cp_op1_sign: coverpoint item.operand1[31] {
      bins pos = {0};
      bins neg = {1};
    }

    cp_op2_sign: coverpoint item.operand2[31] {
      bins pos = {0};
      bins neg = {1};
    }

    cp_op3_sign: coverpoint item.operand3[31] {
      bins pos = {0};
      bins neg = {1};
    }

    cp_result_sign: coverpoint item.result[31] {
      bins pos = {0};
      bins neg = {1};
    }

    cross_all_signs: cross cp_op1_sign, cp_op2_sign, cp_op3_sign;
    cross_sign_transition: cross cp_op1_sign, cp_op2_sign, cp_result_sign;

  endgroup


  // ================================================================
  // Constructor
  // ================================================================

  function new(string name="alu_core_subscriber", uvm_component parent=null);
    super.new(name, parent);

    cg_alu_advanced      = new();
    cg_sign_combinations = new();
  endfunction


  // ================================================================
  // write() — called by monitor analysis port
  // ================================================================

  virtual function void write(alu_core_seq_item t);
    item = t;
    cg_alu_advanced.sample();
    cg_sign_combinations.sample();
  endfunction


  // ================================================================
  // Coverage Report
  // ================================================================

  function void report_phase(uvm_phase phase);
    real cov1, cov2, avg;

    cov1 = cg_alu_advanced.get_coverage();
    cov2 = cg_sign_combinations.get_coverage();
    avg  = (cov1 + cov2) / 2.0;

    `uvm_info("ALU_COVERAGE",
      $sformatf("Advanced=%0.2f%%  Sign=%0.2f%%  Avg=%0.2f%%",
                cov1, cov2, avg),
      UVM_NONE)
  endfunction

endclass
