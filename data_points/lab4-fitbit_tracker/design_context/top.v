module top_module(clk100Mhz, reset, start_button, stop_button, MODE, cathode, DP, anode, overflow); 
    input wire clk100Mhz, reset, start_button, stop_button;
    input wire [1:0] MODE;

    output wire [6:0] cathode;         // 7-segment display cathodes (segments a-g)
    output wire DP;                    // Decimal point on 7-segment display
    output wire [7:0] anode;           // 7-segment display anodes (for each digit)
    output wire overflow;

    // Internal signals
    wire start_debounced, stop_debounced, pulse_out, OFLOW;
    wire [13:0] total_step;
    wire [4:0] distance_covered;

    // BCD conversion outputs
    wire [15:0] BCD_step_count, BCD_distance, BCD_mode;

    // Rotator output
    wire [15:0] BCD_value;
    wire [3:0] decimal_point;

    assign overflow = OFLOW;
    
    // Debouncer for the start button
    debouncer db_start (.clk100Mhz(clk100Mhz), .rst(reset), .i_sig(start_button), .o_sig_debounced(start_debounced));

    // Debouncer for the stop button
    debouncer db_stop (.clk100Mhz(clk100Mhz), .rst(reset), .i_sig(stop_button), .o_sig_debounced(stop_debounced));

    // Pulse generator
    pulse_generator pulse_gen (.clk(clk100Mhz), .reset(reset), .MODE(MODE),
        .START(start_debounced), .STOP(stop_debounced), .pulse_out(pulse_out));

    // Fitbit tracker module to count steps and calculate distance
    fitbit_tracker tracker (.clk(clk100Mhz), .reset(reset), .pulse_in(pulse_out),
        .total_step(total_step), .distance_covered(distance_covered), .OFLOW(overflow));

    // Binary to BCD conversion for total steps
    bin2bcd_fsm step_bcd_conv (.clk100Mhz(clk100Mhz),
        .rst(reset), .start(1'b1),  // Always start conversion
        .bin(total_step),
        .bcd(BCD_step_count));

    // Binary to BCD conversion for distance
    bin2bcd_fsm distance_bcd_conv (.clk100Mhz(clk100Mhz),
        .rst(reset), .start(1'b1),        // Always start conversion
        .bin({8'b0, distance_covered*5}), // Extend distance_covered to 14 bits for conversion
        .bcd(BCD_distance));
    
    // Binary to BCD conversion for MODE
    bin2bcd_fsm mode_bcd_conv (.clk100Mhz(clk100Mhz),
        .rst(reset), .start(1'b1),       // Always start conversion
        .bin({12'b0, MODE}),             // Extend MODE to 14 bits for conversion
        .bcd(BCD_mode));
    
    // Rotator to switch between step count, distance, and mode display
    Rotator rotator (.clk(clk100Mhz), .reset(reset),
        .BCD_step_count(BCD_step_count), .BCD_distance(BCD_distance),
        .BCD_mode(BCD_mode), .BCD_value(BCD_value),
        .decimal(decimal_point));

    // Four-digit 7-segment display driver
    four_digit_display display (.clk(clk100Mhz), .reset(reset),
        .BCD_value(BCD_value), .decimal_point(decimal_point),
        .cathodes(cathode), .anodes(anode), .DP(DP));

endmodule

////////////////////////////////////////////////////////////////////////////////

