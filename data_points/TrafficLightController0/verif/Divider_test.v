`timescale 1ns / 1ps
module Divider_test;

	// Inputs
	reg clk;
	reg rst;
	
	// Outputs
	wire oneHz_enable;

	// Instantiate the Unit Under Test (UUT)
	Divider uut (
		.rst(rst),
		.clk(clk), 
		.oneHz_enable(oneHz_enable)
	);


	initial begin 
	clk=0;
	rst=0;
	#10;
	rst=1;
	#10;
	rst=0;
	$finish;   
	end
	
	initial begin
	forever begin
	 #5 clk = ~clk;
	end 
	end
endmodule

