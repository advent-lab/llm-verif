
import uvm_pkg::*;
`include "uvm_macros.svh"

// Sequence item for ALU Core module
class alu_core_seq_item extends uvm_sequence_item;

  // Clock signal (not randomized)
  bit clk;

  // Input signals (randomized)
  rand logic [3:0] opcode;
  rand logic signed [31:0] operand1;
  rand logic signed [31:0] operand2;
  rand logic signed [31:0] operand3;

  // Output signal (not randomized)
  logic signed [31:0] result;

  // UVM automation macros for field registration
  `uvm_object_utils_begin(alu_core_seq_item)
    `uvm_field_int(clk,         UVM_ALL_ON)
    `uvm_field_int(opcode,      UVM_ALL_ON)
    `uvm_field_int(operand1,    UVM_ALL_ON)
    `uvm_field_int(operand2,    UVM_ALL_ON)
    `uvm_field_int(operand3,    UVM_ALL_ON)
    `uvm_field_int(result,      UVM_ALL_ON)
  `uvm_object_utils_end

  // Constructor
  function new(string name = "alu_core_seq_item");
    super.new(name);
  endfunction

  // Constraints for valid stimulus generation

  // 1. opcode can be any 4-bit value (0x0 to 0xF)
  constraint opcode_range_c {
    opcode inside {[4'b0000:4'b1111]};
  }

  // 2. operand1, operand2, operand3: full 32-bit signed range
  // (No need for explicit constraint; default randomization covers full range)

  // 3. Prevent division by zero when opcode is division (0x3)
  constraint division_by_zero_c {
    if (opcode == 4'h3) {
      operand2 != 0;
      operand3 != 0;
    }
  }

  // 4. For multiplication (0x2), allow all values including zero (no constraint)
  // 5. For bitwise and arithmetic ops, all values allowed (no constraint)
  // 6. For default/idle opcodes (0x7–0xF), all operand values allowed

  // 7. Prevent overflow/underflow constraints are not required as per spec (wrap-around allowed)

  // 8. No constraints on clk or result (not randomized)

endclass
