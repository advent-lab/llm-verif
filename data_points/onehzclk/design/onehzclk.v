/*
 * compare & count clock
 * cycle time is double COMPARE+1
 */
module onehzclk
#(
    parameter COMPARE = 25000000 - 1,   // half_cycle_time - 1
    parameter WIDTH = 25                // bit width
) (
    output o_clk,   // output clock
    input i_clk,    // input clock
    input i_rst_n   // restart
);

    wire [WIDTH-1:0] counter_loader;
    wire counter_set;
    wire counter_rst_n;
    
    assign counter_rst_n = 1'b1;
    
    assign counter_loader = counter_set ? COMPARE : { WIDTH{1'bz} };
    
    assign counter_set = !i_rst_n;
    
    cntclk #(.WIDTH(WIDTH)) inner_counter(
        .o_clk(o_clk),
        .o_zero(),
        .io_value(counter_loader),
        .i_clk(i_clk),
        .i_rst_n(counter_rst_n),
        .i_load(counter_set)
    );

endmodule
