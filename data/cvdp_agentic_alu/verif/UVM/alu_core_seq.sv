
import uvm_pkg::*;
`include "uvm_macros.svh"

// =============================================================
// alu_core_base_sequence: Base sequence for ALU Core
// =============================================================
class alu_core_base_sequence extends uvm_sequence #(alu_core_seq_item);
  `uvm_object_utils(alu_core_base_sequence)

  // Constructor
  function new(string name = "alu_core_base_sequence");
    super.new(name);
  endfunction

  // Base sequence: generates a single random legal transaction
  virtual task body();
    alu_core_seq_item seq_item;
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    // Randomize all input fields with constraints from seq_item
    if (!seq_item.randomize()) begin
      `uvm_error(get_type_name(), "Randomization failed in base sequence")
    end
    start_item(seq_item);
    finish_item(seq_item);
  endtask
endclass

// =============================================================
// alu_core_rand_sequence: Generates many random legal transactions
// =============================================================
class alu_core_rand_sequence extends alu_core_base_sequence;
  `uvm_object_utils(alu_core_rand_sequence)

  function new(string name = "alu_core_rand_sequence");
    super.new(name);
  endfunction

  // Generate 2500 random legal transactions
  virtual task body();
    alu_core_seq_item seq_item;
    repeat (2500) begin
      seq_item = alu_core_seq_item::type_id::create("seq_item");
      if (!seq_item.randomize()) begin
        `uvm_error(get_type_name(), "Randomization failed in rand_sequence")
      end
      start_item(seq_item);
      finish_item(seq_item);
    end
  endtask
endclass

// =============================================================
// alu_core_directed_sequence: Directed and boundary-value tests
// =============================================================
class alu_core_directed_sequence extends alu_core_base_sequence;
  `uvm_object_utils(alu_core_directed_sequence)

  function new(string name = "alu_core_directed_sequence");
    super.new(name);
  endfunction

  // Helper: assign all fields for a directed transaction
  task send_directed(
    logic [3:0] opcode,
    logic signed [31:0] operand1,
    logic signed [31:0] operand2,
    logic signed [31:0] operand3
  );
    alu_core_seq_item seq_item;
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    seq_item.opcode   = opcode;
    seq_item.operand1 = operand1;
    seq_item.operand2 = operand2;
    seq_item.operand3 = operand3;
    start_item(seq_item);
    finish_item(seq_item);
  endtask

  // Main body: send all directed and boundary testpoints
  virtual task body();
    // ---------------------------------------------------------
    // 1. Directed-value tests from alu_core_testcase.txt
    // (Only those compliant with seq_item constraints)
    // ---------------------------------------------------------
    // FUNC_ADD_01: Addition
    send_directed(4'h0, 32'h0000_0001, 32'h0000_0002, 32'h0000_0003);
    // FUNC_SUB_02: Subtraction
    send_directed(4'h1, 32'h0000_0005, 32'h0000_0002, 32'h0000_0001);
    // FUNC_MUL_03: Multiplication
    send_directed(4'h2, 32'h0000_0002, 32'h0000_0003, 32'h0000_0004);
    // FUNC_DIV_04: Division (no div by zero)
    send_directed(4'h3, 32'h0000_0024, 32'h0000_0004, 32'h0000_0002);
    // FUNC_AND_05: Bitwise AND
    send_directed(4'h4, 32'hFFFF_0000, 32'h0FFF_0000, 32'h00FF_0000);
    // FUNC_OR_06: Bitwise OR
    send_directed(4'h5, 32'h0000_0001, 32'h0000_0002, 32'h0000_0004);
    // FUNC_XOR_07: Bitwise XOR
    send_directed(4'h6, 32'hAAAA_AAAA, 32'h5555_5555, 32'hFFFF_FFFF);
    // FUNC_IDLE_08: Unsupported opcode (output zero)
    send_directed(4'h8, 32'h1234_5678, 32'h9ABC_DEF0, 32'h0000_0001);
    // BOUND_ZERO_09: All zeros
    send_directed(4'h0, 32'h0000_0000, 32'h0000_0000, 32'h0000_0000);
    // BOUND_MAX_10: All maximum positive
    send_directed(4'h0, 32'h7FFF_FFFF, 32'h7FFF_FFFF, 32'h7FFF_FFFF);
    // BOUND_MIN_11: All minimum negative
    send_directed(4'h1, 32'h8000_0000, 32'h8000_0000, 32'h8000_0000);
    // BOUND_MIXED_12: Mixed max/min/zero
    send_directed(4'h2, 32'h7FFF_FFFF, 32'h8000_0000, 32'h0000_0000);
    // BOUND_ALLONES_13: All ones for AND
    send_directed(4'h4, 32'hFFFF_FFFF, 32'hFFFF_FFFF, 32'hFFFF_FFFF);
    // BOUND_ALLZEROS_14: All zeros for OR
    send_directed(4'h5, 32'h0000_0000, 32'h0000_0000, 32'h0000_0000);
    // BOUND_ALT_15: Alternating bits for XOR
    send_directed(4'h6, 32'hAAAA_AAAA, 32'hAAAA_AAAA, 32'hAAAA_AAAA);
    // FUNC_NEG_20: Negative values for addition
    send_directed(4'h0, 32'hFFFF_FFFF, 32'hFFFF_FFFE, 32'h0000_0001);

    // ---------------------------------------------------------
    // 2. Additional boundary and mid-value tests
    // ---------------------------------------------------------
    // Mid-range values (0, 1, -1, max/2, min/2)
    send_directed(4'h0, 32'd0, 32'd1, -32'd1); // add: 0+1+(-1)
    send_directed(4'h1, 32'd100, 32'd50, 32'd25); // sub: 100-50-25
    send_directed(4'h2, 32'd1000, -32'd2, 32'd3); // mul: 1000*-2*3
    send_directed(4'h3, 32'd100, 32'd10, 32'd2); // div: 100/10/2

    // Max/2, Min/2
    send_directed(4'h4, 32'h3FFF_FFFF, 32'h4000_0000, 32'h7FFF_FFFF); // AND
    send_directed(4'h5, 32'hC000_0000, 32'h8000_0000, 32'h4000_0000); // OR
    send_directed(4'h6, 32'h5555_5555, 32'hAAAA_AAAA, 32'h0000_0000); // XOR

    // ---------------------------------------------------------
    // 3. Error/invalid opcode and division edge cases
    // ---------------------------------------------------------
    // ERR_OPCODE_19: Invalid opcode (output zero)
    send_directed(4'hF, 32'h0000_0001, 32'h0000_0002, 32'h0000_0003);

    // ERR_DIVMINUS1_18: Division of min negative by -1 (allowed by constraints)
    send_directed(4'h3, 32'h8000_0000, 32'hFFFF_FFFF, 32'h0000_0001);

    // Note: ERR_DIVZERO_16 and ERR_DIVZERO2_17 are NOT included,
    // as they violate the constraint that operand2/operand3 != 0 for division.

    // ---------------------------------------------------------
    // 4. Supplement: For each opcode, test with min/max/zero/typical values
    // ---------------------------------------------------------
    // Addition: min, max, zero
    send_directed(4'h0, 32'h8000_0000, 32'h7FFF_FFFF, 32'd0);
    // Subtraction: min, max, zero
    send_directed(4'h1, 32'h7FFF_FFFF, 32'h8000_0000, 32'd0);
    // Multiplication: min, max, zero
    send_directed(4'h2, 32'h8000_0000, 32'h7FFF_FFFF, 32'd1);
    // Division: min, max, typical (avoid zero divisor)
    send_directed(4'h3, 32'h7FFF_FFFF, 32'd2, 32'd2);

    // Bitwise AND: all zeros, all ones, mixed
    send_directed(4'h4, 32'h0000_0000, 32'hFFFF_FFFF, 32'hAAAA_AAAA);
    // Bitwise OR: all zeros, all ones, mixed
    send_directed(4'h5, 32'h0000_0000, 32'hFFFF_FFFF, 32'h5555_5555);
    // Bitwise XOR: all zeros, all ones, mixed
    send_directed(4'h6, 32'h0000_0000, 32'hFFFF_FFFF, 32'hAAAA_AAAA);

    // Default/idle: random values, unsupported opcode
    send_directed(4'h9, 32'hDEAD_BEEF, 32'h1234_5678, 32'h0BAD_F00D);

    // ---------------------------------------------------------
    // 5. Randomized boundary and corner cases (min/max/zero)
    // ---------------------------------------------------------
    alu_core_seq_item seq_item;
    // Randomize with min values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    void'(seq_item.randomize() with {
      opcode inside {[4'h0:4'h6]};
      operand1 == -2147483648;
      operand2 == -2147483648;
      operand3 == -2147483648;
    });
    start_item(seq_item); finish_item(seq_item);

    // Randomize with max values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    void'(seq_item.randomize() with {
      opcode inside {[4'h0:4'h6]};
      operand1 == 2147483647;
      operand2 == 2147483647;
      operand3 == 2147483647;
    });
    start_item(seq_item); finish_item(seq_item);

    // Randomize with zeros
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    void'(seq_item.randomize() with {
      opcode inside {[4'h0:4'h6]};
      operand1 == 0;
      operand2 == 0;
      operand3 == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // Randomize with mixed values
    seq_item = alu_core_seq_item::type_id::create("seq_item");
    void'(seq_item.randomize() with {
      opcode inside {[4'h0:4'h6]};
      operand1 == 2147483647;
      operand2 == -2147483648;
      operand3 == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // ---------------------------------------------------------
    // 6. Additional random legal transactions (for robustness)
    // ---------------------------------------------------------
    repeat (20) begin
      seq_item = alu_core_seq_item::type_id::create("seq_item");
      if (!seq_item.randomize()) begin
        `uvm_error(get_type_name(), "Randomization failed in directed_sequence")
      end
      start_item(seq_item);
      finish_item(seq_item);
    end
  endtask
endclass

// =============================================================
// alu_core_full_coverage_sequence: Mix of random and directed
// =============================================================
class alu_core_full_coverage_sequence extends alu_core_base_sequence;
  `uvm_object_utils(alu_core_full_coverage_sequence)

  function new(string name = "alu_core_full_coverage_sequence");
    super.new(name);
  endfunction

  virtual task body();
    // First, run the directed sequence
    alu_core_directed_sequence directed_seq;
    directed_seq = alu_core_directed_sequence::type_id::create("directed_seq");
    directed_seq.start(m_sequencer);

    // Then, run a large number of random transactions
    alu_core_rand_sequence rand_seq;
    rand_seq = alu_core_rand_sequence::type_id::create("rand_seq");
    rand_seq.start(m_sequencer);
  endtask
endclass
