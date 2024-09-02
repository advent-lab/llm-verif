
module byte_en_reg (
    clk,
    rst,
    we,
    en,
    d,
    q
    );

parameter DATA_W = 32;
parameter INIT_VAL = {DATA_W{1'b0}};

input clk;
input rst;
input we;
input [(DATA_W-1)/8:0] en;
input [DATA_W-1:0] d;
output reg [DATA_W-1:0] q;

integer i;

always @(posedge clk or posedge rst)
begin
    if (rst == 1)
        q <= INIT_VAL;
    else
        for (i = 0; i < DATA_W; i = i + 1)
            if (we && en[i/8])
                q[i] <= d[i];
end

endmodule
