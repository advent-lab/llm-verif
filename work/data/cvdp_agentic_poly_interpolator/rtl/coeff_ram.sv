module coeff_ram #(
  parameter NUM_COEFFS  = 32,
  parameter DATA_WIDTH  = 16
)
(
  input  logic                          clk,
  input  logic [$clog2(NUM_COEFFS)-1:0] addr,
  output logic [DATA_WIDTH-1:0]         data_out
);

  // Memory array for coefficients.
  logic [DATA_WIDTH-1:0] mem [0:NUM_COEFFS-1];
  integer i;

  // Synchronous read.
  always_ff @(posedge clk)
  begin
    data_out <= mem[addr];
  end

endmodule