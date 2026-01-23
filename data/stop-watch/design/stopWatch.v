`timescale 1ns / 1ns     //It was just for quick simulations, make it your own

//making a stop watch which can display centi-seconds, seconds, minutes and hours on the
//7 segment displays of Nexys A7 FPGA

module stopWatch(clk, start, reset, count_s, count_m, anode, display, clk_1csec);
    input clk;
    input start, reset;
    output reg clk_1csec;       //1 centi-second clock
    output reg [5:0] count_s, count_m;
	reg [6:0] count_cs;	//count centi-second
	//output reg [6:0] count_cs;	//count centi-second
	
    reg [4:0] count_h;
    output reg [7:0] anode;
    output reg [6:0] display;
	
    initial clk_1csec=0;
    
    //local variables
    reg [25:0] timer1 = 0;    //timer1 is for clock division
    reg [17:0] timer2 = 0;    //timer2 is for segment selection
    reg [31:0] count_time = 0;
    reg clk_seg;
    reg [2:0] seg_count;
    reg [3:0] data;
	
    always @ (posedge clk)
    begin
        timer1 <= timer1 + 1;
        timer2 <= timer2 + 1;
        clk_seg <= timer2[17];  //17, this is just for cheating to human eye (We are using multiplexing to display on seven segments)
        if (timer1>500000)  //manipulate this to change the frequency of your clock, I have explained it in Readme.md file
        begin
            timer1<=0;
            clk_1csec<= ~clk_1csec;
        end 
        if (timer2>131072)   //multiplexing, do not change it
            timer2 <= 0;
     end
     
     always @ (posedge clk_1csec)     //this is triggered after each centi second
     begin
          if (reset)
          begin
            count_time <= 0;
            count_cs <= 0;
            count_s <=0;
            count_m <=0;
            count_h <=0;
          end
          else
          begin
              if(start)
              begin
                  count_time <= count_time+1;       //only one counter is used for this stop watch
				  count_cs <= count_time % 100;     //centi = 100 (% means we cannot got beyond 99 in centi-seconds)
				  
                  count_s <= (count_time/100) % 60;   //count_time/100 means 
                  count_m <= (count_time/6000)%60;  
                  count_h <= (count_time/360000)%24;
              end  
          end  
     end
     
     always @ (posedge clk_seg)
     begin
        seg_count <= seg_count+1;
        if (seg_count>7)
            seg_count <=0;
        case(seg_count)
            0: begin anode <=8'b11111110; data<=count_cs%10; end
            1: begin anode <=8'b11111101; data<=count_cs/10; end
            2: begin anode <=8'b11111011; data<=count_s%10; end
            3: begin anode <=8'b11110111; data<=count_s/10; end
            4: begin anode <=8'b11101111; data<=count_m%10; end
            5: begin anode <=8'b11011111; data<=count_m/10; end
            6: begin anode <=8'b10111111; data<=count_h%10; end 
            7: begin anode <=8'b01111111; data<=count_h/10; end
        endcase
    end

// Cathode patterns of the 7-segment 1 LED display 
    always @(*)
    begin
        case(data)
        4'b0000: display <= 7'b0000001; // "0"     
        4'b0001: display <= 7'b1001111; // "1" 
        4'b0010: display <= 7'b0010010; // "2" 
        4'b0011: display <= 7'b0000110; // "3" 
        4'b0100: display <= 7'b1001100; // "4" 
        4'b0101: display <= 7'b0100100; // "5" 
        4'b0110: display <= 7'b0100000; // "6" 
        4'b0111: display <= 7'b0001111; // "7" 
        4'b1000: display <= 7'b0000000; // "8"     
        4'b1001: display <= 7'b0000100; // "9"
		4'b1010: display <= 7'b0001000; // "A"     
        4'b1011: display <= 7'b1100000; // "b"     
        4'b1100: display <= 7'b0110001; // "C"     
        4'b1101: display <= 7'b1000010; // "d"     
        4'b1110: display <= 7'b0110000; // "E"     
        4'b1111: display <= 7'b0111000; // "F"     
        
        default: display <= 7'b1111110; // "-"
        endcase
    
end	
endmodule
 
