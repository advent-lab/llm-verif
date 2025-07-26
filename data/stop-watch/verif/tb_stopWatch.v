`timescale 1s / 1s

module stopWatch_tb;
    reg clk, start, reset;


  wire [5:0] count_s, count_m;
  wire [7:0] anode;
  wire [6:0] display;
  wire clk_1csec;
  
  stopWatch stWt_UUT(clk,start,reset, count_s, count_m, anode, display, clk_1csec);

  initial begin
    clk = 0;
    start = 0;
    reset = 0;
  end

    initial begin
        forever #5 clk = ~clk;
    end
  
	initial begin
        //$dumpvars;
        #2;
        start = 1;
        #20;
        start = 1;
        #300;
        start = 0;
        #20;
        reset = 0;
        #5; start = 1;
        #50 $finish;
	  
	end // initial begin
   
endmodule
