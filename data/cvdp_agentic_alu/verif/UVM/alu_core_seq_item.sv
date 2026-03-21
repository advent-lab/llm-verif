
import uvm_pkg::*;
`include "uvm_macros.svh"

// Sequence item for ALU Core module
class alu_core_seq_item extends uvm_sequence_item;

  // Clock signal (from interface, not randomized)
  bit clk;

  // Input signals (randomized)
  rand logic [3:0]  opcode;
  rand logic signed [31:0] operand1;
  rand logic signed [31:0] operand2;
  rand logic signed [31:0] operand3;

  // Output signal (not randomized)
  logic signed [31:0] result;

  // UVM automation macros for field registration
  `uvm_object_utils_begin(alu_core_seq_item)
    `uvm_field_int(clk,        UVM_ALL_ON)
    `uvm_field_int(opcode,     UVM_ALL_ON)
    `uvm_field_int(operand1,   UVM_ALL_ON)
    `uvm_field_int(operand2,   UVM_ALL_ON)
    `uvm_field_int(operand3,   UVM_ALL_ON)
    `uvm_field_int(result,     UVM_ALL_ON)
  `uvm_object_utils_end

  // Constructor
  function new(string name = "alu_core_seq_item");
    super.new(name);
    clk = 0;
    opcode = 0;
    operand1 = 0;
    operand2 = 0;
    operand3 = 0;
    result = 0;
  endfunction

  // Constraints for valid input stimulus

  // Operand range constraints (signed 32-bit)
  constraint operand1_range_c {
    operand1 inside {[-2147483648:2147483647]};
  }
  constraint operand2_range_c {
    operand2 inside {[-2147483648:2147483647]};
  }
  constraint operand3_range_c {
    operand3 inside {[-2147483648:2147483647]};
  }

  // Opcode range constraint (0x0 to 0xF)
  constraint opcode_range_c {
    opcode inside {[4'h0:4'hF]};
  }

  // Division by zero avoidance for opcode 0x3 (division)
  constraint div_by_zero_c {
    // If opcode is division, operand2 and operand3 must not be zero
    !(opcode == 4'h3 && operand2 == 0);
    !(opcode == 4'h3 && operand3 == 0);
  }

  // Prevent multiplication overflow for opcode 0x2 (optional, can be relaxed for overflow testing)
  // (No constraint here, as overflow is allowed per spec)

  // For bitwise operations, allow all values (no extra constraint needed)

  // For default/idle opcodes (0x7-0xF), operands can be any value

  // Example: For addition, subtraction, multiplication, division, and bitwise, allow all operand values
  // No further field-to-field constraints required per spec

endclass
