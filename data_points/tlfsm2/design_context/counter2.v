module counter2
#(
    parameter WIDTH = 16
) (
    output wire [WIDTH-1:0] o_value,
    output reg o_match,
    input wire i_clk,
    input wire i_rst_n,
    input wire i_desc,
    input wire [WIDTH-1:0] i_setup
);

    reg [WIDTH-1:0] counter_value;
    wire [WIDTH-1:0] finish_value;
    wire [WIDTH-1:0] compare_value;

    assign o_value = counter_value;
    assign finish_value = i_desc ? { WIDTH{1'b0} } : i_setup;
    assign compare_value = i_desc ? finish_value + 1'b1 : finish_value - 1'b1;

    always @(posedge i_clk) begin
        if (!i_rst_n) begin
            o_match <= #1 0;
            restart();
        end else begin
            o_match <= #1 0;

            if (counter_value == finish_value) begin
                restart();
            end else if (counter_value == compare_value) begin
                // match pulls high on next clock cycle
                // which will be the finish cycle
                o_match <= #1 1'b1;
                step();
            end else begin
                step();
            end
        end
    end

    task step;
        if (i_desc) counter_value <= #1 counter_value - 1'b1;
        else counter_value <= #1 counter_value + 1'b1;
    endtask

    task restart;
        if (i_desc) counter_value <= #1 i_setup;
        else counter_value <= #1 { WIDTH{1'b0} };
    endtask

endmodule
