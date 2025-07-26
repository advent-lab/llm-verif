
		module tb_uart_core;

			// Clock logic
			reg clk;
			initial
			begin
				clk = 0;
				forever #10 clk = ~clk;
			end

			// Reset logic
			reg reset_n;
			initial
			begin
				reset_n = 0;
				#10 reset_n = 1;
			end

			// Configuration parameters
			reg [15:0] bit_rate;
			reg [3:0] data_bits;
			reg [1:0] stop_bits;

			// External data interface
			reg rxd;
			wire txd;

			// Internal receive interface
			wire rxd_syn;
			wire [7:0] rxd_data;
			reg rxd_ack;

			// Internal transmit interface
			reg txd_syn;
			reg [7:0] txd_data;
			wire txd_ack;

			// Instantiate the DUT
			uart_core dut (
				.clk(clk),
				.reset_n(reset_n),
				.bit_rate(bit_rate),
				.data_bits(data_bits),
				.stop_bits(stop_bits),
				.rxd(rxd),
				.txd(txd),
				.rxd_syn(rxd_syn),
				.rxd_data(rxd_data),
				.rxd_ack(rxd_ack),
				.txd_syn(txd_syn),
				.txd_data(txd_data),
				.txd_ack(txd_ack)
			);

			// Test cases
			initial
			begin
				// Test case 1: Reset and initialization
				#10;
				$display("Test case 1: Reset and initialization");
				if (dut.rxd_syn!== 0 || dut.rxd_data!== 8'd0 || dut.txd_syn!== 0) begin
					$display("Error: Test case 1 failed");
				end

				// Test case 2: Configuration register testing
				bit_rate = 16'd1000;
				data_bits = 4'd8;
				stop_bits = 2'd1;
				#10;
				$display("Test case 2: Configuration register testing");
				if (dut.bit_rate!== bit_rate || dut.data_bits!== data_bits || dut.stop_bits!== stop_bits) begin
					$display("Error: Test case 2 failed");
				end

				// Test case 3: Receive interface testing
				rxd = 1;
				#10;
				$display("Test case 3: Receive interface testing");
				if (dut.rxd_syn!== 1) begin
					$display("Error: Test case 3 failed");
				end
				rxd_ack = 1;
				#10;
				$display("Test case 3: Receive interface testing");
				if (dut.rxd_syn!== 0) begin
					$display("Error: Test case 3 failed");
				end

				// Test case 4: Transmit interface testing
				txd_data = 8'd12;
				txd_syn = 1;
				#10;
				$display("Test case 4: Transmit interface testing");
				if (dut.txd_syn!== 1) begin
					$display("Error: Test case 4 failed");
				end

				// Test case 5: Loopback mode testing
				bit_rate = 16'd1000;
				data_bits = 4'd8;
				stop_bits = 2'd1;
				rxd = 1;
				txd_data = 8'd12;
				txd_syn = 1;
				#10;
				$display("Test case 5: Loopback mode testing");
				if (dut.rxd_syn!== 1) begin
					$display("Error: Test case 5 failed");
				end
				rxd_ack = 1;
				#10;
				$display("Test case 5: Loopback mode testing");
				if (dut.rxd_syn!== 0) begin
					$display("Error: Test case 5 failed");
				end

				$finish;
			end
		endmodule
	