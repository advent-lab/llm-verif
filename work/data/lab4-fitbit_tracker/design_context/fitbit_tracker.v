module fitbit_tracker(clk, reset, pulse_in, total_step, distance_covered, OFLOW);
    input wire clk, reset, pulse_in;
    output reg [13:0] total_step;           // 14 bits to represent up to 9999
    output reg [4:0] distance_covered;      // 5 bits to represent up to 19 (9.5 miles / 0.5 miles)
    output reg OFLOW;
    
    reg prev_pulse;
    reg [10:0] step_counter; // Counts up to 2047

    always @(posedge clk) begin
        if (reset) begin
            total_step       <= 14'd0; distance_covered <= 5'd0;
            OFLOW            <= 1'b0;
            prev_pulse       <= 1'b0; step_counter     <= 11'd0;
        end else begin
            if (!pulse_in && prev_pulse) begin  // Falling edge detected
                if (total_step < 14'd9999) begin
                    total_step <= total_step + 14'd1;
                    if (step_counter == 12'd2047) begin
                        step_counter <= 0;
                        if (distance_covered < 5'd19) distance_covered <= distance_covered + 5'b1;
                    end
                    else begin
                        step_counter <= step_counter + 1'd1;
                    end
                end
                else begin
                    OFLOW <= 1'b1; step_counter <= step_counter + 1;
                    if(step_counter == 12'd2047) begin
                        step_counter <= 0;
                        if (distance_covered < 5'd19) distance_covered <= distance_covered + 5'b1;
                    end
                end
            end
            prev_pulse <= pulse_in;
        end
    end

endmodule