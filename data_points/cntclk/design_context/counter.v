/*
 * Programmable Counter
 * 2-modes: decrease/increase
 * decrease: from setup value to 0
 * increase: from 0 to setup value
 * auto reset when count finished
 * on auto reset, notifies a counter finish
 * default: increase, from 1 to { WIDTH{1'b1} }
 * counting restarted on (re)setup
 */
module counter
#(
    parameter WIDTH = 16
) (
    inout wire [WIDTH-1:0] io_value,    // current value of the counter, or on setup, fed setup value
    output reg o_match,                 // on a count cycle finishes, match is pull high for 1 clock cycle
    input wire i_clk,                   // input clock
    input wire i_rst_n,                 // reset counter, low active, reset counter to default state
    input wire i_restart,               // restart counting, counting mode is not changed
    input wire [1:0] i_setup            // 00 - couting, 11 - decrease & load, 10 - increase & load, 01 - undefined
);

    reg [WIDTH-1:0] counter_value;
    reg [WIDTH-1:0] setup_value;
    reg [WIDTH-1:0] compare_value;
    reg [WIDTH-1:0] finish_value;
    reg desc;

    assign io_value = (i_setup == 2'b00) ? counter_value : { WIDTH{1'bz} };

    always @(posedge i_clk, negedge i_rst_n) begin
        if (!i_rst_n) begin
            counter_value <= #1 { WIDTH{1'b0} };
            setup_value <= #1 { WIDTH{1'b1} };
            compare_value <= #1 { WIDTH{1'b1} } - 1'b1;
            finish_value <= #1 { WIDTH{1'b1} };
            desc <= #1 1'b0;
            o_match <= #1 0;
        end else begin
            o_match <= #1 0;
            case (i_setup)
                3'b11: begin
                    desc <= #1 1'b1;
                    setup_value <= #1 io_value;
                    counter_value <= #1 io_value;
                    compare_value <= #1 { WIDTH{1'b0} } + 1'b1;
                    finish_value <= #1 { WIDTH{1'b0} };
                end
                3'b10: begin
                    desc <= #1 1'b0;
                    setup_value <= #1 io_value;
                    counter_value <= #1 { WIDTH{1'b0} };
                    compare_value <= #1 io_value - 1'b1;
                    finish_value <= #1 io_value;
                end
                3'b00: begin
                    if (i_restart) begin
                        restart();
                    end else begin
                        if (counter_value == finish_value) begin
                            restart();
                        end else if (counter_value == compare_value) begin
                            // match pulls high on next clock cycle
                            o_match <= #1 1'b1;
                            step();
                        end else begin
                            step();
                        end
                    end
                end
            endcase
        end
    end

    task step;
        if (desc) counter_value <= #1 counter_value - 1'b1;
        else counter_value <= #1 counter_value + 1'b1;
    endtask

    task restart;
        if (desc) counter_value <= #1 setup_value;
        else counter_value <= #1 { WIDTH{1'b0} };
    endtask

endmodule
