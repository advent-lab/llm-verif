
		module tb_top_module;

			// Clock logic
			reg clk100Mhz;
			initial
			begin
				clk100Mhz = 0;
				forever #5 clk100Mhz = ~clk100Mhz;
			end

			// Input signals
			reg reset;
			reg start_button;
			reg stop_button;
			reg [1:0] MODE;

			// DUT instance
			module wrapper_module(clk100Mhz, reset, start_button, stop_button, MODE);
				input clk100Mhz;
				input reset;
				input start_button;
				input stop_button;
				input [1:0] MODE;

				top_module dut (
					.clk100Mhz(clk100Mhz),
					.reset(reset),
					.start_button(start_button),
					.stop_button(stop_button),
					.MODE(MODE)
				);
			endmodule

			// Test cases
			initial
			begin
				// Reset test
				reset = 1;
				#10 reset = 0;

				// Pulse generator test
				start_button = 1;
				MODE = 2'b00; // Walk mode
				#3125 start_button = 0;
				MODE = 2'b01; // Jog mode
				#1562 start_button = 0;
				MODE = 2'b10; // Run mode
				#718 start_button = 0;
				MODE = 2'b11; // Off mode
				#100 start_button = 0;

				// Fitbit tracker test
				start_button = 1;
				#2048 start_button = 0;
				#2048 start_button = 1;
				#2048 start_button = 0;

				// Overflow test
				start_button = 1;
				repeat (10000) #1 start_button = 0;

				$finish;
			end
		endmodule
	