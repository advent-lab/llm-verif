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
