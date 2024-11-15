module pulse_generator(clk, reset, MODE, START, STOP, pulse_out);
    input wire clk, reset, START, STOP;
    input wire [1:0] MODE;
    output reg pulse_out;

    // Internal registers
    reg [31:0] counter;         // Counter for generating pulse intervals
    reg [31:0] pulse_interval;  // Interval for pulse generation based on MODE
    reg generating_pulses;      // Flag to indicate if pulse generation is active

    // Constants
    parameter WALK_STEP = 3125;  // 32 pulses per second 'minus 00'
    parameter JOG_STEP  = 1562;  // 64 pulses per second 'minus 00'   
    parameter RUN_STEP  = 718;   // 128 pulses per second 'minus 50' 
    parameter OFF_MODE  = 0;

    // Update pulse interval based on MODE (Combinational)
    always @(*) begin
        case (MODE)
            2'b00: pulse_interval = WALK_STEP;
            2'b01: pulse_interval = JOG_STEP;
            2'b10: pulse_interval = RUN_STEP;
            2'b11: pulse_interval = OFF_MODE;
            default: pulse_interval = OFF_MODE;
        endcase
    end

    // Pulse generation logic (Sequential)
    always @(posedge clk) begin
        if (reset) begin
            generating_pulses <= 0; counter <= 0;
            pulse_out <= 0;
        end 
        else begin
            // Handle START and STOP inputs
            if (START) begin            // Start generating pulses
                generating_pulses <= 1; counter <= 0;
            end else if (STOP) begin    // Stop pulse generation
                generating_pulses <= 0; counter <= 0;
                pulse_out <= 0;
            end
            
            // Generate pulses if enabled
            if (generating_pulses && (pulse_interval != 32'd0)) begin
                if (counter >= pulse_interval - 1) begin
                    pulse_out <= 1; counter <= 0;   // Reset counter after each pulse
                end else begin
                    pulse_out <= 0; counter <= counter + 1;
                end
            end else begin      // Ensure pulse_out is low when not generating pulses or in OFF mode
                pulse_out <= 0;
            end
        end
    end

endmodule
