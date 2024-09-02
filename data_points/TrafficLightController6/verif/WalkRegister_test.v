`timescale 1ns / 1ps
module WalkRegister_test;

	// Inputs
	reg WR_Sync;
	reg WR_Reset;

	// Outputs
	wire WR;

	// Instantiate the Unit Under Test (UUT)
	WalkRegister uut (
		.WR_Sync(WR_Sync), 
		.WR_Reset(WR_Reset),
		.WR(WR)
	);

	initial begin
		// Initialize Inputs
		WR_Sync = 0;
		WR_Reset = 0;


		// Wait 100 ns for global reset to finish
		#100;
      WR_Sync = 1;
		#10;
		WR_Sync = 0;
		#500;
		WR_Reset = 1;
		
		// Add stimulus here
                $finish;
	end
	

      
endmodule

