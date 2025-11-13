`timescale 1ns/1ns

module matrix_multiplication_tb;

    // Parameters
    parameter DWIDTH = 16;
    parameter AWIDTH = 5;

    // Testbench signals
    reg clk;
    reg reset;
    reg we1, we2;
    reg enable_writing_to_mem;
    reg [DWIDTH-1:0] data_pi;
    reg [AWIDTH-1:0] addr_pi;
    reg [AWIDTH-1:0] out_sel;

    wire [2*DWIDTH-1:0] data_out;
    wire done_mat_mul;

    // Instantiate DUT
    matrix_multiplication dut (
        .clk(clk),
        .reset(reset),
        .we1(we1),
        .we2(we2),
        .enable_writing_to_mem(enable_writing_to_mem),
        .data_pi(data_pi),
        .addr_pi(addr_pi),
        .out_sel(out_sel),
        .data_out(data_out),
        .done_mat_mul(done_mat_mul)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk; // 100MHz clock
    end

    // Task to write data to memory
    task write_memory;
        input [AWIDTH-1:0] addr;
        input [DWIDTH-1:0] data;
        input mem_select; // 0 for we1, 1 for we2
        begin
            addr_pi = addr;
            data_pi = data;
            enable_writing_to_mem = 1;
            if (mem_select == 0) begin
                we1 = 1;
                we2 = 0;
            end else begin
                we1 = 0;
                we2 = 1;
            end
            #10;
            we1 = 0;
            we2 = 0;
            enable_writing_to_mem = 0;
        end
    endtask

    // Test sequence
    initial begin
        $display("Starting matrix_multiplication testbench...");

        // Initialize
        reset = 1;
        we1 = 0;
        we2 = 0;
        enable_writing_to_mem = 0;
        data_pi = 0;
        addr_pi = 0;
        out_sel = 0;

        // Reset sequence
        #20;
        reset = 0;
        #10;

        // Test 1: Simple matrix multiplication
        $display("\nTest 1: Loading matrix A (2x2)");
        // Matrix A:
        // [1, 2]
        // [3, 4]
        write_memory(0, 16'd1, 0);  // A[0][0]
        write_memory(1, 16'd2, 0);  // A[0][1]
        write_memory(2, 16'd3, 0);  // A[1][0]
        write_memory(3, 16'd4, 0);  // A[1][1]

        $display("Test 1: Loading matrix B (2x2)");
        // Matrix B:
        // [5, 6]
        // [7, 8]
        write_memory(0, 16'd5, 1);  // B[0][0]
        write_memory(1, 16'd6, 1);  // B[0][1]
        write_memory(2, 16'd7, 1);  // B[1][0]
        write_memory(3, 16'd8, 1);  // B[1][1]

        // Start multiplication
        #50;
        $display("Starting matrix multiplication...");

        // Wait for completion
        wait(done_mat_mul == 1);
        #20;
        $display("Matrix multiplication done!");

        // Read results
        $display("Reading results...");
        for (int i = 0; i < 4; i = i + 1) begin
            out_sel = i;
            #10;
            $display("Result[%0d] = %0d", i, data_out);
        end

        // Test 2: Identity matrix multiplication
        $display("\nTest 2: Identity matrix test");
        reset = 1;
        #20;
        reset = 0;
        #10;

        // Matrix A = Identity
        write_memory(0, 16'd1, 0);
        write_memory(1, 16'd0, 0);
        write_memory(2, 16'd0, 0);
        write_memory(3, 16'd1, 0);

        // Matrix B = any matrix
        write_memory(0, 16'd10, 1);
        write_memory(1, 16'd20, 1);
        write_memory(2, 16'd30, 1);
        write_memory(3, 16'd40, 1);

        #50;
        wait(done_mat_mul == 1);
        #20;

        for (int i = 0; i < 4; i = i + 1) begin
            out_sel = i;
            #10;
            $display("Result[%0d] = %0d", i, data_out);
        end

        // Test 3: Zero matrix
        $display("\nTest 3: Zero matrix test");
        reset = 1;
        #20;
        reset = 0;
        #10;

        // Matrix A = zeros
        write_memory(0, 16'd0, 0);
        write_memory(1, 16'd0, 0);
        write_memory(2, 16'd0, 0);
        write_memory(3, 16'd0, 0);

        // Matrix B = any matrix
        write_memory(0, 16'd100, 1);
        write_memory(1, 16'd200, 1);
        write_memory(2, 16'd300, 1);
        write_memory(3, 16'd400, 1);

        #50;
        wait(done_mat_mul == 1);
        #20;

        for (int i = 0; i < 4; i = i + 1) begin
            out_sel = i;
            #10;
            $display("Result[%0d] = %0d", i, data_out);
        end

        // Test 4: Larger values
        $display("\nTest 4: Larger values");
        reset = 1;
        #20;
        reset = 0;
        #10;

        write_memory(0, 16'd100, 0);
        write_memory(1, 16'd200, 0);
        write_memory(2, 16'd300, 0);
        write_memory(3, 16'd400, 0);

        write_memory(0, 16'd10, 1);
        write_memory(1, 16'd20, 1);
        write_memory(2, 16'd30, 1);
        write_memory(3, 16'd40, 1);

        #50;
        wait(done_mat_mul == 1);
        #20;

        for (int i = 0; i < 4; i = i + 1) begin
            out_sel = i;
            #10;
            $display("Result[%0d] = %0d", i, data_out);
        end

        $display("\nTestbench completed.");
        #50;
        $finish;
    end

    // Monitor done signal
    initial begin
        $monitor("Time=%0t: reset=%b we1=%b we2=%b done=%b data_out=%d",
                 $time, reset, we1, we2, done_mat_mul, data_out);
    end

endmodule
