/*
 * Compare Counter
 * decrease mode
 * count from load value to 0
 * default: count from { WIDTH{1'b1} } to 0
 * auto restarted on count finish
 * on each auto restart, o_clk is toggled
 */
module cntclk
#(
    parameter WIDTH = 16
) (
    output reg o_clk,                   // toggled on each auto restart
    output wire o_zero,                 // counter reaches zero, about to restart counting
    inout wire [WIDTH-1:0] io_value,    // current value, on load, fed load value
    input wire i_clk,                   // input clock
    input wire i_rst_n,                 // reset counter to default mode
    input wire i_load                   // load compare value, and restart counting
);

    wire [WIDTH-1:0] counter_value;
    wire counter_rstn;
    wire counter_restart;
    wire [1:0] counter_setup;
    wire inner_rst_n;

    counter #(.WIDTH(WIDTH)) inner_counter (
        .io_value(counter_value),
        .o_match(o_zero),
        .i_clk(i_clk),
        .i_rst_n(counter_rstn),
        .i_restart(counter_restart),
        .i_setup(counter_setup)
    );

    assign counter_rstn = 1'b1;

    assign counter_restart = 1'b0;

    assign io_value = (!inner_rst_n) ? { WIDTH{1'bz} } : counter_value;

    assign counter_value = (!i_rst_n) ? { WIDTH{1'b1} } : i_load ? io_value : { WIDTH{1'bz} };

    assign inner_rst_n = (~i_rst_n | i_load) ? 1'b0 : 1'b1;

    assign counter_setup = (!inner_rst_n) ? 2'b11 : 2'b00;

    always @(posedge o_zero, negedge inner_rst_n) begin
        if (!inner_rst_n) begin
            o_clk <= #1 1'b0;
        end else begin
            o_clk <= #1 !o_clk;
        end 
    end

endmodule
