module multiplexer #(
    parameter DATA_WIDTH = 8,
    parameter NUM_INPUTS = 4,
    parameter REGISTER_OUTPUT = 0,
    parameter HAS_DEFAULT = 0,
    parameter [DATA_WIDTH-1:0] DEFAULT_VALUE = {DATA_WIDTH{1'b0}}
)(
    input  wire clk,
    input  wire rst_n,
    input  wire [(DATA_WIDTH*NUM_INPUTS)-1:0] inp,
    input  wire [$clog2(NUM_INPUTS)-1:0]       sel,
    input  wire bypass,
    output reg  [DATA_WIDTH-1:0] out
);

wire [DATA_WIDTH-1:0] inp_array [0:NUM_INPUTS-1];
genvar i;
generate
    for (i = 0; i < NUM_INPUTS; i = i + 1) begin : GEN_INP
        assign inp_array[i] = inp[(i+1)*DATA_WIDTH-1 : i*DATA_WIDTH];
    end
endgenerate

wire [DATA_WIDTH-1:0] sel_out =
    (HAS_DEFAULT && sel >= NUM_INPUTS) ? DEFAULT_VALUE : inp_array[sel];

wire [DATA_WIDTH-1:0] mux_out = bypass ? inp_array[0] : sel_out;

generate
    if (REGISTER_OUTPUT) begin
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) out <= {DATA_WIDTH{1'b0}};
            else        out <= mux_out;
        end
    end else begin
        always @* out = mux_out;
    end
endgenerate

endmodule