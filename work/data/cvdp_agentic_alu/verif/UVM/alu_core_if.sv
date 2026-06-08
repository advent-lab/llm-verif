interface alu_core_if #(parameter int DATA_WIDTH = 32) ();

  // input/output signals
  logic [3:0] opcode;

  logic signed [DATA_WIDTH-1:0] operand1;
  logic signed [DATA_WIDTH-1:0] operand2;
  logic signed [DATA_WIDTH-1:0] operand3;

  logic signed [DATA_WIDTH-1:0] result;

  logic clk;

  // design modport
  modport DUT (
    input  opcode, operand1, operand2, operand3, clk,
    output result
  );

endinterface : alu_core_if
