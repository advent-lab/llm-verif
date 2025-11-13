
		`timescale 1ns / 1ps
		module tb_llm;

			// Parameters
			parameter DWIDTH = 8;
			parameter MASK_WIDTH = 8;

			// DUT Inputs
			reg activation_type;
			reg enable_activation;
			reg enable_pool;
			reg in_data_available;
			reg [DWIDTH-1:0] inp_data0;
			reg [DWIDTH-1:0] inp_data1;
			reg [DWIDTH-1:0] inp_data2;
			reg [DWIDTH-1:0] inp_data3;
			reg [DWIDTH-1:0] inp_data4;
			reg [DWIDTH-1:0] inp_data5;
			reg [DWIDTH-1:0] inp_data6;
			reg [DWIDTH-1:0] inp_data7;
			reg [MASK_WIDTH-1:0] validity_mask;
			reg clk;
			reg reset;

			// DUT Outputs
			wire [DWIDTH-1:0] out_data0;
			wire [DWIDTH-1:0] out_data1;
			wire [DWIDTH-1:0] out_data2;
			wire [DWIDTH-1:0] out_data3;
			wire [DWIDTH-1:0] out_data4;
			wire [DWIDTH-1:0] out_data5;
			wire [DWIDTH-1:0] out_data6;
			wire [DWIDTH-1:0] out_data7;
			wire out_data_available;
			wire done_activation;

			// Instantiate the DUT
			activation dut (
				.activation_type(activation_type),
				.enable_activation(enable_activation),
				.enable_pool(enable_pool),
				.in_data_available(in_data_available),
				.inp_data0(inp_data0),
				.inp_data1(inp_data1),
				.inp_data2(inp_data2),
				.inp_data3(inp_data3),
				.inp_data4(inp_data4),
				.inp_data5(inp_data5),
				.inp_data6(inp_data6),
				.inp_data7(inp_data7),
				.out_data0(out_data0),
				.out_data1(out_data1),
				.out_data2(out_data2),
				.out_data3(out_data3),
				.out_data4(out_data4),
				.out_data5(out_data5),
				.out_data6(out_data6),
				.out_data7(out_data7),
				.out_data_available(out_data_available),
				.done_activation(done_activation),
				.clk(clk),
				.reset(reset)
			);

			// Clock generation
			initial begin
				clk = 0;
				forever #5 clk = ~clk; // 10 ns clock period
			end

			// Test stimulus
			initial begin
				// Initialize inputs
				reset = 0;
				enable_pool = 0;
				in_data_available = 0;
				activation_type = 0;
				enable_activation = 0;
				validity_mask = 8'b11111111; // All valid

				// Wait for reset
				#10;
				reset = 1;
				#10;
				reset = 0;

				// Test Case 1: Test relu activation
				activation_type = 0;
				enable_activation = 1;
				in_data_available = 1;
				inp_data0 = $urandom_range(0, 255);
				inp_data1 = $urandom_range(0, 255);
				inp_data2 = $urandom_range(0, 255);
				inp_data3 = $urandom_range(0, 255);
				inp_data4 = $urandom_range(0, 255);
				inp_data5 = $urandom_range(0, 255);
				inp_data6 = $urandom_range(0, 255);
				inp_data7 = $urandom_range(0, 255);
				#10; // Wait for processing

				// Test Case 2: Test tanh activation
				activation_type = 1;
				inp_data0 = $urandom_range(0, 255);
				inp_data1 = $urandom_range(0, 255);
				inp_data2 = $urandom_range(0, 255);
				inp_data3 = $urandom_range(0, 255);
				inp_data4 = $urandom_range(0, 255);
				inp_data5 = $urandom_range(0, 255);
				inp_data6 = $urandom_range(0, 255);
				inp_data7 = $urandom_range(0, 255);
				#10; // Wait for processing

				// Test Case 3: Disable activation
				enable_activation = 0;
				inp_data0 = $urandom_range(0, 255);
				inp_data1 = $urandom_range(0, 255);
				inp_data2 = $urandom_range(0, 255);
				inp_data3 = $urandom_range(0, 255);
				inp_data4 = $urandom_range(0, 255);
				inp_data5 = $urandom_range(0, 255);
				inp_data6 = $urandom_range(0, 255);
				inp_data7 = $urandom_range(0, 255);
				#10; // Wait for processing

				// Test Case 4: Reset behavior
				reset = 1;
				#10;
				reset = 0;

				// Finish simulation
				$finish;
			end
		endmodule
	