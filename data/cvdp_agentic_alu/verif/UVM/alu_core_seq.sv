
import uvm_pkg::*;
`include "uvm_macros.svh"

// ALU Core Base Sequence: Generates basic functional transactions
class alu_core_base_sequence extends uvm_sequence #(alu_core_seq_item);
  `uvm_object_utils(alu_core_base_sequence)

  // Constructor
  function new(string name = "alu_core_base_sequence");
    super.new(name);
  endfunction

  // Main sequence body
  virtual task body();
    alu_core_seq_item seq_item;
    // Generate a single basic transaction with random values (within constraints)
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    // Randomize all input fields (constraints in seq_item ensure validity)
    if (!seq_item.randomize()) begin
      `uvm_error(get_type_name(), "Randomization failed in alu_core_base_sequence")
    end
    start_item(seq_item);
    finish_item(seq_item);
  endtask
endclass

// ALU Core Full Functional Sequence: Generates random and directed transactions for full coverage
class alu_core_full_functional_sequence extends alu_core_base_sequence;
  `uvm_object_utils(alu_core_full_functional_sequence)

  // Constructor
  function new(string name = "alu_core_full_functional_sequence");
    super.new(name);
  endfunction

  // Main sequence body
  virtual task body();
    alu_core_seq_item seq_item;
    int i;

    // 1. Constrained Random Transactions (High Coverage)
    // Generate 2500 random transactions covering all legal opcodes and operand values
    repeat (2500) begin
      seq_item = alu_core_seq_item::type_id::create("seq_item");
      if (!seq_item.randomize()) begin
        `uvm_error(get_type_name(), "Randomization failed in random transaction loop")
      end
      start_item(seq_item);
      finish_item(seq_item);
    end

    // 2. Directed Transactions (from alu_core_testcase.txt and boundary/mid-range)
    // Each test point is implemented as a directed transaction

    // ADD_0001: Addition mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h0;
    seq_item.operand1 = 32'h0000_0001;
    seq_item.operand2 = 32'h0000_0002;
    seq_item.operand3 = 32'h0000_0003;
    start_item(seq_item);
    finish_item(seq_item);

    // SUB_0002: Subtraction mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h1;
    seq_item.operand1 = 32'h0000_000A;
    seq_item.operand2 = 32'h0000_0003;
    seq_item.operand3 = 32'h0000_0002;
    start_item(seq_item);
    finish_item(seq_item);

    // MUL_0003: Multiplication mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h2;
    seq_item.operand1 = 32'h0000_0002;
    seq_item.operand2 = 32'h0000_0003;
    seq_item.operand3 = 32'h0000_0004;
    start_item(seq_item);
    finish_item(seq_item);

    // DIV_0004: Division mode, typical values (no division by zero)
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h3;
    seq_item.operand1 = 32'h0000_0020;
    seq_item.operand2 = 32'h0000_0004;
    seq_item.operand3 = 32'h0000_0002;
    start_item(seq_item);
    finish_item(seq_item);

    // AND_0005: Bitwise AND mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h4;
    seq_item.operand1 = 32'hFFFF_0000;
    seq_item.operand2 = 32'h0FFF_0000;
    seq_item.operand3 = 32'h00FF_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // OR_0006: Bitwise OR mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h5;
    seq_item.operand1 = 32'h0000_00FF;
    seq_item.operand2 = 32'h0000_0F00;
    seq_item.operand3 = 32'h0000_F000;
    start_item(seq_item);
    finish_item(seq_item);

    // XOR_0007: Bitwise XOR mode, typical values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h6;
    seq_item.operand1 = 32'hAAAA_AAAA;
    seq_item.operand2 = 32'h5555_5555;
    seq_item.operand3 = 32'hFFFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // DEF_0008: Default/idle mode, random values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'hF;
    seq_item.operand1 = 32'h1234_5678;
    seq_item.operand2 = 32'h8765_4321;
    seq_item.operand3 = 32'h0000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // ADD_BND_MAX_0009: Addition mode, max positive values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h0;
    seq_item.operand1 = 32'h7FFF_FFFF;
    seq_item.operand2 = 32'h7FFF_FFFF;
    seq_item.operand3 = 32'h7FFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // ADD_BND_MIN_0010: Addition mode, min negative values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h0;
    seq_item.operand1 = 32'h8000_0000;
    seq_item.operand2 = 32'h8000_0000;
    seq_item.operand3 = 32'h8000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // SUB_BND_OVF_0011: Subtraction mode, overflow scenario
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h1;
    seq_item.operand1 = 32'h8000_0000;
    seq_item.operand2 = 32'h7FFF_FFFF;
    seq_item.operand3 = 32'h7FFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // MUL_BND_OVF_0012: Multiplication mode, overflow scenario
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h2;
    seq_item.operand1 = 32'h7FFF_FFFF;
    seq_item.operand2 = 32'h0000_0002;
    seq_item.operand3 = 32'h0000_0002;
    start_item(seq_item);
    finish_item(seq_item);

    // DIV_BND_ZERO_0013: Division mode, division by zero (invalid, skip as per constraints)
    // Skipped: operand2 == 0 not allowed by seq_item constraint

    // DIV_BND_ZERO2_0014: Division mode, division by zero (invalid, skip as per constraints)
    // Skipped: operand3 == 0 not allowed by seq_item constraint

    // AND_BND_ALL1_0015: Bitwise AND mode, all ones
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h4;
    seq_item.operand1 = 32'hFFFF_FFFF;
    seq_item.operand2 = 32'hFFFF_FFFF;
    seq_item.operand3 = 32'hFFFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // AND_BND_ALL0_0016: Bitwise AND mode, all zeros and ones
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h4;
    seq_item.operand1 = 32'h0000_0000;
    seq_item.operand2 = 32'hFFFF_FFFF;
    seq_item.operand3 = 32'hFFFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // XOR_BND_ALT_0017: Bitwise XOR mode, alternating bits
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h6;
    seq_item.operand1 = 32'hAAAA_AAAA;
    seq_item.operand2 = 32'hAAAA_AAAA;
    seq_item.operand3 = 32'hAAAA_AAAA;
    start_item(seq_item);
    finish_item(seq_item);

    // OR_BND_ALL0_0018: Bitwise OR mode, all zeros
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h5;
    seq_item.operand1 = 32'h0000_0000;
    seq_item.operand2 = 32'h0000_0000;
    seq_item.operand3 = 32'h0000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // DEF_BND_0019: Default/idle mode, boundary values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h7;
    seq_item.operand1 = 32'h7FFF_FFFF;
    seq_item.operand2 = 32'h8000_0000;
    seq_item.operand3 = 32'h0000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // ALL_NEG_0020: Subtraction mode, all -1
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h1;
    seq_item.operand1 = 32'hFFFF_FFFF;
    seq_item.operand2 = 32'hFFFF_FFFF;
    seq_item.operand3 = 32'hFFFF_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // 3. Additional Boundary and Mid-range Value Tests

    // Addition: mid-range values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h0;
    seq_item.operand1 = 32'h4000_0000;
    seq_item.operand2 = 32'h2000_0000;
    seq_item.operand3 = 32'h1000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // Subtraction: mid-range values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h1;
    seq_item.operand1 = 32'h4000_0000;
    seq_item.operand2 = 32'h2000_0000;
    seq_item.operand3 = 32'h1000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // Multiplication: one operand is zero
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h2;
    seq_item.operand1 = 32'h0000_0000;
    seq_item.operand2 = 32'h0000_0001;
    seq_item.operand3 = 32'h0000_0002;
    start_item(seq_item);
    finish_item(seq_item);

    // Division: mid-range, no division by zero
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h3;
    seq_item.operand1 = 32'h4000_0000;
    seq_item.operand2 = 32'h0000_0002;
    seq_item.operand3 = 32'h0000_0002;
    start_item(seq_item);
    finish_item(seq_item);

    // Bitwise AND: mixed values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h4;
    seq_item.operand1 = 32'h0F0F_0F0F;
    seq_item.operand2 = 32'hF0F0_F0F0;
    seq_item.operand3 = 32'hFFFF_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // Bitwise OR: mixed values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h5;
    seq_item.operand1 = 32'h0F0F_0F0F;
    seq_item.operand2 = 32'hF0F0_F0F0;
    seq_item.operand3 = 32'h0000_FFFF;
    start_item(seq_item);
    finish_item(seq_item);

    // Bitwise XOR: mixed values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h6;
    seq_item.operand1 = 32'h0F0F_0F0F;
    seq_item.operand2 = 32'hF0F0_F0F0;
    seq_item.operand3 = 32'hFFFF_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // Default/idle opcode, mid-range values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = 4'h8;
    seq_item.operand1 = 32'h4000_0000;
    seq_item.operand2 = 32'h2000_0000;
    seq_item.operand3 = 32'h1000_0000;
    start_item(seq_item);
    finish_item(seq_item);

    // 4. Additional: For each opcode, generate a few random legal transactions
	for (int op = 0; op < 16; op++) begin
	  repeat (2) begin
	    seq_item = alu_core_seq_item::type_id::create("seq_item");
	    if (!seq_item.randomize() with { opcode == op; }) begin
	      `uvm_error(get_type_name(), $sformatf("Randomization failed for opcode %0d", op))
	    end
	    start_item(seq_item);
	    finish_item(seq_item);
	  end
	end

  endtask
endclass
