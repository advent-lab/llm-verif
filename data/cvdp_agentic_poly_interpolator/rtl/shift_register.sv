module shift_register #(
  parameter TAPS       = 8,
  parameter DATA_WIDTH = 16
)
(
  input  logic                  clk,
  input  logic                  arst_n,
  input  logic                  load,      // Assert to load a new sample
  input  logic [DATA_WIDTH-1:0] new_sample,
  output logic [DATA_WIDTH-1:0] data_out [0:TAPS-1],
  output logic                  data_out_val  // New valid signal for data_out
);

  // Internal register array for storing the samples.
  logic [DATA_WIDTH-1:0] reg_array [0:TAPS-1];
  integer i;

  always_ff @(posedge clk or negedge arst_n) begin
    if (!arst_n)
    begin
      for (i = 0; i < TAPS; i = i + 1)
        reg_array[i] <= '0;
      data_out_val <= 1'b0;
    end
    else if (load)
    begin
      reg_array[0] <= new_sample;
      for (i = TAPS-1; i > 0; i = i - 1)
        reg_array[i] <= reg_array[i-1];
      data_out_val <= 1'b1;
    end
    else
    begin
      data_out_val <= 1'b0;
    end
  end

  // Continuous assignment of the register values to the output.
  generate
    for (genvar j = 0; j < TAPS; j = j + 1)
    begin : assign_output
      assign data_out[j] = reg_array[j];
    end
  endgenerate

endmodule