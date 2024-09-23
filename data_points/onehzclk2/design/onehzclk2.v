module onehzclk2
#(
    parameter COMPARE = 25'd25000000 - 1'b1,
    parameter WIDTH = 25
) (
    output o_clk,
    input i_clk,
    input i_rst_n
);

    wire counter_desc;
    wire [WIDTH-1:0] counter_setup;
    
    assign counter_desc = 1'b1;
    assign counter_setup = COMPARE;

    cntclk2 #(.WIDTH(WIDTH)) inner_counter(
        .o_clk(o_clk),
        .o_match(),
        .o_value(),
        .i_clk(i_clk),
        .i_rst_n(i_rst_n),
        .i_desc(counter_desc),
        .i_setup(counter_setup)
    );

endmodule
