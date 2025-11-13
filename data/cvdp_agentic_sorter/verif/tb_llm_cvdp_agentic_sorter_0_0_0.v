
		module tb_llm;

			// Parameters
			parameter WIDTH = 8;

			// DUT signals
			reg clk;
			reg rst;
			reg start;
			reg [8*WIDTH-1:0] in_data;
			wire done;
			wire [8*WIDTH-1:0] out_data;

			// Clock generation
			initial begin
				clk = 0;
				forever #5 clk = ~clk; // 10 time units clock period
			end

			// DUT instantiation
			sorting_engine #(WIDTH) dut (
				.clk(clk),
				.rst(rst),
				.start(start),
				.in_data(in_data),
				.done(done),
				.out_data(out_data)
			);

			// Testcase
			initial begin
				// Reset the DUT
				rst = 1;
				start = 0;
				in_data = 0;
				#15;
				rst = 0;

				// Apply random input and start sorting
				repeat (10) begin
					@(posedge clk);
					in_data = $urandom();
					start = 1;
					@(posedge clk);
					start = 0;

					// Wait for sorting to complete
					wait(done);

					// Check output
					$display("Sorted output: %h", out_data);
				end

				$finish;
			end
		endmodule
	