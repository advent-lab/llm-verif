module adder_tree #(
  parameter NUM_INPUTS = 8,
  parameter WIDTH = 32
)
(
  input  logic                                     clk,
  input  logic                                     arst_n,
  input  logic                                     valid_in,
  input  logic [WIDTH-1:0]                         data_in [NUM_INPUTS],
  output logic [WIDTH+$clog2(NUM_INPUTS)-1:0]      sum_out,
  output logic                                     valid_out
);

  // The number of pipeline stages required:
  localparam NUM_STAGES = $clog2(NUM_INPUTS);

  // Pipeline registers
  logic [WIDTH+$clog2(NUM_INPUTS)-1:0] stage_reg [0:NUM_STAGES][0:NUM_INPUTS-1];
  logic valid_stage [0:NUM_STAGES];

  integer i, s;

  // Stage 0: Register input data
  always_ff @(posedge clk or negedge arst_n)
  begin
    if (!arst_n)
    begin
      for (i = 0; i < NUM_INPUTS; i = i + 1)
        stage_reg[0][i] <= '0;
      valid_stage[0] <= 1'b0;
    end
    else if (valid_in)
    begin
      for (i = 0; i < NUM_INPUTS; i = i + 1)
        stage_reg[0][i] <= {{($clog2(NUM_INPUTS)){data_in[i][WIDTH-1]}}, data_in[i]};
      valid_stage[0] <= 1'b1;
    end 
    else
    begin
      valid_stage[0] <= 1'b0;
    end
  end

  // Subsequent pipeline stages: each stage halves the number of values.
  generate
    for (genvar s = 1; s <= NUM_STAGES; s = s + 1)
    begin : stage_pipeline
      localparam int NUM_ELEMS = NUM_INPUTS >> s;
      always_ff @(posedge clk or negedge arst_n)
      begin
        if (!arst_n)
        begin
          for (int j = 0; j < NUM_ELEMS; j = j + 1)
            stage_reg[s][j] <= '0;
          valid_stage[s] <= 1'b0;
        end
        else if (valid_stage[s-1])
        begin
          for (int j = 0; j < NUM_ELEMS; j = j + 1)
            stage_reg[s][j] <= stage_reg[s-1][2*j] + stage_reg[s-1][2*j+1];
          valid_stage[s] <= 1'b1;
        end
        else
        begin
          valid_stage[s] <= 1'b0;
        end
      end
    end
  endgenerate

  assign sum_out  = stage_reg[NUM_STAGES][0];
  assign valid_out = valid_stage[NUM_STAGES];

endmodule