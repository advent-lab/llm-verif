module bistable_domain_cross(
    rst,
    clk_a,
    in,
    clk_b,
    out
);
parameter width = 1;
input rst;
input clk_a;
input [width-1:0] in;
input clk_b;
output [width-1:0] out;

// We use a two-stages shift-register to synchronize in to the clk_b clock domain
reg [width-1:0] sync_clk_b [1:0];
always @(posedge clk_b or posedge rst)
begin
    if (rst == 1) begin
        sync_clk_b[0] <= 0;
        sync_clk_b[1] <= 0;
    end else begin
        sync_clk_b[0] <= in;
        sync_clk_b[1] <= sync_clk_b[0];
    end
end

assign out = sync_clk_b[1];  // new signal synchronized to (=ready to be used in) clk_b domain

endmodule 
