
		module tb_llm;

			// Clock logic
			reg clk;
			initial
			begin
				clk = 0;
			end
			always
			begin
				#5 clk = ~clk;
			end

			// Reset logic
			reg rst_n;
			initial
			begin
				rst_n = 0;
				#10 rst_n = 1;
			end

			// DUT instantiation
			wire [3:0] o_data;
			wire o_full;
			wire o_empty;
			reg [3:0] i_data;
			reg wr_en;
			reg rd_en;
			syncFIFO_v2 #(4,4) dut(clk, rst_n, i_data, wr_en, rd_en, o_data, o_full, o_empty);

			// Test cases
			initial
			begin
				// Test case 1: Reset startup check
				#10;
				assert(o_empty);
				assert(o_full == 0);

				// Test case 2: Write to FIFO when not full
				i_data = 4'b0001;
				wr_en = 1;
				#10;
				assert(o_data == 4'b0001);
				assert(o_empty == 0);

				// Test case 3: Read from FIFO when not empty
				rd_en = 1;
				#10;
				assert(o_data == 4'b0001);
				assert(o_empty);

				// Test case 4: Write to FIFO when full
				i_data = 4'b0010;
				wr_en = 1;
				#10;
				assert(o_full);
				assert(o_data != 4'b0010);

				// Test case 5: Read from FIFO when empty
				rd_en = 1;
				#10;
				assert(o_empty);
				assert(o_data == 4'b0000);

				// Test case 6: Write to FIFO when not full and read from FIFO when not empty
				i_data = 4'b0011;
				wr_en = 1;
				#10;
				rd_en = 1;
				#10;
				assert(o_data == 4'b0011);
				assert(o_empty == 0);

				$finish;
			end
		endmodule
	