module Rotator(clk, reset, BCD_step_count, BCD_distance, BCD_mode, BCD_value, decimal);
    input wire clk, reset;
    input wire [15:0] BCD_step_count, BCD_distance, BCD_mode;
    output reg [15:0] BCD_value;
    output reg [3:0] decimal;

    reg [1:0] state;
    reg [31:0] cycle_counter;
    parameter CYCLE_LIMIT = 200_000_000;  // Adjust for 1-second cycles at 100 MHz

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            state         <= 2'd0;
            cycle_counter <= 32'd0;
        end else begin
            if (cycle_counter >= CYCLE_LIMIT - 1) begin
                cycle_counter <= 32'd0;
                if (state == 2'd2)
                    state <= 2'd0;
                else
                    state <= state + 1'd1;
            end else begin
                cycle_counter <= cycle_counter + 1'd1;
            end
        end
    end

    // Output logic based on the current state
    always @(*) begin
        case (state)
            2'd0: begin
                // Display Total Step Count
                BCD_value     = BCD_step_count;
                decimal = 4'b1111;    // No decimal point
            end
            2'd1: begin
                // Display Total Distance
                BCD_value     = BCD_distance;
                decimal = 4'b1101;    // Decimal on the second digit from the right
            end
            2'd2: begin
                // Display Mode
                BCD_value     = BCD_mode;
                decimal = 4'b1111;    // No decimal point
            end
            default: begin
                BCD_value     = 16'd0;
                decimal = 4'b1111;
            end
        endcase
    end

endmodule