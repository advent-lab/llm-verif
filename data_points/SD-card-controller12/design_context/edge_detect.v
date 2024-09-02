module sd_edge_detect (
    input rst,
    input clk, 
    input sig,
    output rise,
    output fall
);

reg [1:0] sig_reg;

always @(posedge clk or posedge rst)
    if (rst == 1'b1)
        sig_reg <= 2'b00;
    else
        sig_reg <= {sig_reg[0], sig};

assign rise = sig_reg[0] == 1'b1 && sig_reg[1] == 1'b0 ? 1'b1 : 1'b0;
assign fall = sig_reg[0] == 1'b0 && sig_reg[1] == 1'b1 ? 1'b1 : 1'b0;

endmodule