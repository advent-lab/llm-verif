module cntclk2
#(
    parameter WIDTH = 16
) (
    output reg o_clk,
    output wire o_match,
    inout wire [WIDTH-1:0] o_value,
    input wire i_clk,
    input wire i_rst_n,
    input wire i_desc,
    input wire [WIDTH-1:0] i_setup
);

    counter2 #(.WIDTH(WIDTH)) inner_counter (
        .o_value(o_value),
        .o_match(o_match),
        .i_clk(i_clk),
        .i_rst_n(i_rst_n),
        .i_desc(i_desc),
        .i_setup(i_setup)
    );

    always @(posedge o_match, negedge i_rst_n) begin
        if (!i_rst_n) begin
            o_clk <= #1 1'b0;
        end else begin
            o_clk <= #1 !o_clk;
        end 
    end

endmodule
