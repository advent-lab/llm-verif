`timescale 1ns / 1ps
module Timer_test;

	// Inputs
	reg [3:0] Value;
	reg oneHz_enable;
	reg start_timer;
	reg clk;
	reg Reset_Sync;

	// Outputs
	wire expired;

	// Instantiate the Unit Under Test (UUT)
	Timer uut (
		.Value(Value), 
		.oneHz_enable(oneHz_enable), 
		.start_timer(start_timer),
		.clk(clk),
		.expired(expired),
		.Reset_Sync(Reset_Sync)
	);

	initial begin
		// Initialize Inputs
		Value = 0;
		oneHz_enable = 0;
		start_timer = 0;
		Reset_Sync = 0;
		// Wait 100 ns for global reset to finish
		#5;
      Value=4'b1100;
		start_timer=1;
		Reset_Sync = 1;
		#5;
		start_timer=0;
		Reset_Sync = 0;
		#30;
		//Value=4'b1000;
	        $finish;
	   
	end
	
		initial begin 
			oneHz_enable=0;
			forever begin
				#5 oneHz_enable = ~oneHz_enable;
					  end 
					end
      initial begin 
			clk=0;
			forever begin
				#5 clk = ~clk;
					  end 
					end
endmodule

