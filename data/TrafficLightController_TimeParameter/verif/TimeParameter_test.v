`timescale 1ns / 1ps
module TimeParameter_test;

	// Inputs
	reg [1:0] Selector;
	reg [3:0] Time_value;
	reg Prog_Sync;
	reg [1:0] interval;
	reg clk;

	// Outputs
	wire [3:0] value;

	// Instantiate the Unit Under Test (UUT)
	TimeParameter uut (
		.Selector(Selector), 
		.Time_value(Time_value), 
		.Prog_Sync(Prog_Sync), 
		.interval(interval), 
		.clk(clk), 
		.value(value)
	);

	initial begin
		// Initialize Inputs
		Selector = 2'b00;
		Time_value = 4'b0000;
		Prog_Sync = 0;
		interval = 2'b00;
		
		// Wait 100 ns for global reset to finish
		#10;
       Selector = 2'b00; 
		 interval = 2'b01;
		// Add stimulus here
		#10;
		 Selector = 2'b01;
		 interval =2'b00;
		 
		#5
		Prog_Sync = 1;
		#5
		Selector = 2'b01;
		Time_value = 4'b1111;
	        $finish;

	end
	
	initial begin
	clk = 0;
	forever begin
	 #5 clk = ~clk;
	end 
	end
      
endmodule

