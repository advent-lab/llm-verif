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