`timescale 1ns/1ps

module continuous_adder #(
    parameter integer DATA_WIDTH       = 32,
    parameter integer ENABLE_THRESHOLD = 0,
    parameter integer THRESHOLD        = 16,
    parameter integer REGISTER_OUTPUT  = 0
)(
    input  wire clk,
    input  wire rst_n,
    input  wire valid_in,
    input  wire [DATA_WIDTH-1:0] data_in,
    input  wire accumulate_enable,
    input  wire flush,
    output reg  [DATA_WIDTH-1:0] sum_out,
    output reg  sum_valid
);

reg [DATA_WIDTH-1:0] sum_reg;
wire threshold_reached = (ENABLE_THRESHOLD != 0) && (sum_reg >= THRESHOLD);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        sum_reg <= '0;
    else begin
        if (flush)
            sum_reg <= '0;
        else if (valid_in && accumulate_enable)
            sum_reg <= sum_reg + data_in;
    end
end

generate
    if (REGISTER_OUTPUT != 0) begin
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                sum_out   <= '0;
                sum_valid <= 1'b0;
            end else begin
                if (flush || threshold_reached) begin
                    sum_out   <= sum_reg;
                    sum_valid <= 1'b1;
                end else begin
                    sum_valid <= 1'b0;
                end
            end
        end
    end else begin
        always @* begin
            sum_out   = (flush || threshold_reached) ? sum_reg : sum_out;
            sum_valid = (flush || threshold_reached) ? 1'b1     : 1'b0;
        end
    end
endgenerate

endmodule