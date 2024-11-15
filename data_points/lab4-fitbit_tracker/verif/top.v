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

module debouncer(clk100Mhz, rst, i_sig, o_sig_debounced);
   input clk100Mhz, rst;      
   input  i_sig;
   output o_sig_debounced;

   reg isig_rg, isig_sync_rg;                      // Registers in 2FF Synchronizer
   reg sig_rg, sig_d_rg, sig_debounced_rg ;        // Registers for switch's state
   reg [3:0] counter_rg;                           // Counter
   
   always @(posedge clk100Mhz)
   begin
       // Reset  
       if (rst) begin
          // Internal Registers
          sig_rg <= 0;
          sig_d_rg <= 0;
          sig_debounced_rg <= 0;
          counter_rg <= 1;
       end
       // Out of reset
       else begin
          // Register state of switch      
          sig_rg <= isig_sync_rg;
          sig_d_rg <= sig_rg;
   
          // Increment counter if two consecutive states are same, otherwise reset
          counter_rg <= (sig_d_rg == sig_rg) ? counter_rg + 1 : 1;
     
          // Counter overflow, valid state registered
          if (counter_rg [3]) begin
             sig_debounced_rg <= sig_d_rg ;
          end
       end
   end
   
   always @(posedge clk100Mhz) begin
       // Reset  
       if (rst) begin
          // Internal Registers
          isig_rg <= 0;
          isig_sync_rg <= 0;
         
       end
       // Out of reset
       else begin
          isig_rg <= i_sig;               // Metastable flop
          isig_sync_rg <= isig_rg;        // Synchronizing flop
       end
   end
   assign o_sig_debounced = sig_debounced_rg;

endmodule

////////////////////////////////////////////////////////////////////////////////


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

////////////////////////////////////////////////////////////////////////////////

//double dabble algorithm
module bin2bcd_fsm(clk100Mhz, rst, start, bin, bcd);
    input clk100Mhz, rst, start;
    input [13:0] bin;
    output reg [15:0] bcd;
   
    reg [13:0] r_bin; //This exists in case bin changes in the middle of the conversion
    reg [15:0] w_bcd; //This exists to "hide" the conversion process from top module
    reg [3:0] counter;
    reg [1:0] state;
   
    localparam START_case = 0, SHIFT = 1, CHECK_ADD = 2, FINISH = 3;
   
    always @(posedge clk100Mhz) begin
        if (rst) begin
            counter <= 0; state <= START_case;
            bcd <= 0; w_bcd <= 0; r_bin<=0;
        end
        
        else begin
            case(state)
            
                START_case: begin
                    counter <= 0;
                    
                    if(start) begin
                        state <= SHIFT;
                        w_bcd <= 0; r_bin <= bin;
                    end
                    
                    else
                        state <= START_case;
                end
               
                //Shift left
                SHIFT: begin
                    w_bcd <= w_bcd << 1; w_bcd[0] <= r_bin[13];
                    r_bin <= r_bin << 1;
                    counter <= counter + 1; state <= CHECK_ADD;
                end
               
                //Add 3 if 5 or more for any 4-bit bcd nibble
                CHECK_ADD: begin
                    if(w_bcd[3:0] >= 5) w_bcd[3:0] <= w_bcd[3:0] + 3;
                   
                    if(w_bcd[7:4] >= 5) w_bcd[7:4] <= w_bcd[7:4] + 3;
                       
                    if(w_bcd[11:8] >= 5) w_bcd[11:8] <= w_bcd[11:8] + 3;
                       
                    if(w_bcd[15:12] >= 5) w_bcd[15:12] <= w_bcd[15:12] + 3;
                    
                    //14 bits wide since it only has to display up to 9999   
                    if(counter < (13)) state <= SHIFT;
                    else state <= FINISH;
                end
               
                //Final shift and assign before exit
                FINISH: begin
                    bcd <= {w_bcd[14:0], r_bin[13]};
                    state <= START_case;
                end

            endcase
        end
    end
    
endmodule

////////////////////////////////////////////////////////////////////////////////

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

////////////////////////////////////////////////////////////////////////////////

module four_digit_display(clk, reset, BCD_value, decimal_point, cathodes, anodes, DP);
    input wire clk, reset;
    input wire [15:0] BCD_value;      // 4-digit BCD input
    input wire [3:0] decimal_point;   // Decimal point control for each digit
    output reg [6:0] cathodes;        // Cathode signals for segments a-g
    output reg [7:0] anodes;          // Anode signals for digits 0-7 (only 0-3 used)
    output reg DP;                     // Decimal point signal

    reg [1:0] digit_select;           // 2-bit counter to select the current digit
    reg [3:0] current_digit;          // Current BCD digit to display
    reg current_dot;                  // Current decimal point state
    wire [7:0] segs_with_dp;          // Output from seven_segment module

    // Instantiate the seven_segment module
    seven_segment sseg (.bcd(current_digit), .dot(current_dot), .segs_with_dp(segs_with_dp));

    // Extract segment and decimal point outputs
    wire [6:0] segments = segs_with_dp[6:0];
    wire dp = segs_with_dp[7];

    // Clock divider for multiplexing (adjust the divisor for desired refresh rate)
    reg [17:0] refresh_counter;
    wire refresh_tick = (refresh_counter == 16'd0);

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            refresh_counter <= 18'd99999;  // Adjust for approximately 200 Hz refresh rate
        end else begin
            if (refresh_counter == 16'd0) refresh_counter <= 18'd99999;
            else refresh_counter <= refresh_counter - 1;
        end
    end

    // Digit selection logic
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            digit_select <= 2'b00;
        end else if (refresh_tick) begin
            digit_select <= digit_select + 1'b1;
        end
    end

    // Select current digit and decimal point based on digit_select
    always @(*) begin
        case (digit_select)
            2'b00: begin
                current_digit = BCD_value[3:0];     // Least significant digit
                current_dot = decimal_point[0];
                anodes = 8'b11111110;               // Enable digit 0 (active low)
            end
            2'b01: begin
                current_digit = BCD_value[7:4];
                current_dot = decimal_point[1];
                anodes = 8'b11111101;               // Enable digit 1
            end
            2'b10: begin
                current_digit = BCD_value[11:8];
                current_dot = decimal_point[2];
                anodes = 8'b11111011;               // Enable digit 2
            end
            2'b11: begin
                current_digit = BCD_value[15:12];   // Most significant digit
                current_dot = decimal_point[3];
                anodes = 8'b11110111;               // Enable digit 3
            end
            default: begin
                current_digit = 4'd0;
                current_dot = 1'b0;
                anodes = 8'b11111111;               // All digits off
            end
        endcase
    end

    // Assign cathode and decimal point outputs
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            cathodes <= 7'b1111111;
            DP <= 1'b1;
        end else begin
            cathodes <= segments;
            DP <= dp;
        end
    end

endmodule


module seven_segment(bcd, dot, segs_with_dp);
   input  [3:0] bcd; 
   input        dot;
   output [7:0] segs_with_dp;
    
   reg [6:0] seven;

   always @(bcd)
   begin
      case (bcd)
         4'b0000 : seven = 7'b1000000 ; 
         4'b0001 : seven = 7'b1111001 ; 
         4'b0010 : seven = 7'b0100100 ; 
         4'b0011 : seven = 7'b0110000 ;
         4'b0100 : seven = 7'b0011001 ;
         4'b0101 : seven = 7'b0010010 ;
         4'b0110 : seven = 7'b0000010 ;
         4'b0111 : seven = 7'b1111000 ;
         4'b1000 : seven = 7'b0000000 ;
         4'b1001 : seven = 7'b0010000 ; 
         default : seven = 7'b1111111 ; 
      endcase 
   end 
   assign segs_with_dp = {dot, seven};
   
endmodule
