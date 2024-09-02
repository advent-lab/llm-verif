module monostable_domain_cross(
    input rst,
    input clk_a,
    input in, 
    input clk_b,
    output out
);

// this changes level when the in is seen in clk_a
reg toggle_clk_a;
always @(posedge clk_a or posedge rst)
begin
    if (rst)
        toggle_clk_a <= 0;
    else
        toggle_clk_a <= toggle_clk_a ^ in;
end

// which can then be sync-ed to clk_b
reg [2:0] sync_clk_b;
always @(posedge clk_b or posedge rst)
begin
    if (rst)
        sync_clk_b <= 0;
    else
        sync_clk_b <= {sync_clk_b[1:0], toggle_clk_a};
end

// and recreate the flag in clk_b
assign out = (sync_clk_b[2] ^ sync_clk_b[1]);

endmodule 
