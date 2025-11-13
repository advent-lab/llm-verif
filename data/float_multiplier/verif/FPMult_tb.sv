`timescale 1ns/1ps

module FPMult_tb;

    // Testbench signals
    reg clk;
    reg rst;
    reg [31:0] a;
    reg [31:0] b;

    wire [31:0] result;
    wire [4:0] flags;  // Exception flags

    // Instantiate DUT
    FPMult dut (
        .clk(clk),
        .rst(rst),
        .a(a),
        .b(b),
        .result(result),
        .flags(flags)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk; // 100MHz clock
    end

    // Helper function to display result
    task display_result;
        input [31:0] val_a;
        input [31:0] val_b;
        input [31:0] res;
        input [4:0] flg;
        begin
            $display("Time=%0t: A=%h * B=%h = Result=%h Flags=%b",
                     $time, val_a, val_b, res, flg);
        end
    endtask

    // Test sequence
    initial begin
        $display("Starting FPMult testbench...");

        // Initialize
        rst = 1;
        a = 0;
        b = 0;

        // Reset sequence
        #20;
        rst = 0;
        #10;

        // Test 1: Multiply simple integers
        // 2.0 * 3.0 = 6.0
        $display("\nTest 1: Simple multiplication");
        a = 32'h40000000; // 2.0
        b = 32'h40400000; // 3.0
        #100;
        display_result(a, b, result, flags);

        // Test 2: Multiply by 1
        $display("\nTest 2: Multiply by 1.0");
        a = 32'h40A00000; // 5.0
        b = 32'h3F800000; // 1.0
        #100;
        display_result(a, b, result, flags);

        // Test 3: Multiply by 0
        $display("\nTest 3: Multiply by 0");
        a = 32'h40000000; // 2.0
        b = 32'h00000000; // 0.0
        #100;
        display_result(a, b, result, flags);

        // Test 4: Multiply negative numbers
        $display("\nTest 4: Negative multiplication");
        a = 32'hBF800000; // -1.0
        b = 32'h40000000; // 2.0
        #100;
        display_result(a, b, result, flags);

        // Test 5: Multiply two negative numbers
        $display("\nTest 5: Two negatives");
        a = 32'hC0000000; // -2.0
        b = 32'hC0400000; // -3.0
        #100;
        display_result(a, b, result, flags);

        // Test 6: Small numbers
        $display("\nTest 6: Small numbers");
        a = 32'h3DCCCCCD; // 0.1
        b = 32'h3E4CCCCD; // 0.2
        #100;
        display_result(a, b, result, flags);

        // Test 7: Large numbers
        $display("\nTest 7: Large numbers");
        a = 32'h42C80000; // 100.0
        b = 32'h43480000; // 200.0
        #100;
        display_result(a, b, result, flags);

        // Test 8: Fractional multiplication
        $display("\nTest 8: Fractional multiplication");
        a = 32'h3F000000; // 0.5
        b = 32'h3F000000; // 0.5
        #100;
        display_result(a, b, result, flags);

        // Test 9: Pi multiplication
        $display("\nTest 9: Pi squared");
        a = 32'h40490FDB; // Pi (3.14159...)
        b = 32'h40490FDB; // Pi
        #100;
        display_result(a, b, result, flags);

        // Test 10: Very small * very large
        $display("\nTest 10: Small * Large");
        a = 32'h3C23D70A; // 0.01
        b = 32'h447A0000; // 1000.0
        #100;
        display_result(a, b, result, flags);

        // Test 11: Square of 2
        $display("\nTest 11: 2 squared");
        a = 32'h40000000; // 2.0
        b = 32'h40000000; // 2.0
        #100;
        display_result(a, b, result, flags);

        // Test 12: Random patterns
        $display("\nTest 12: Random patterns");
        a = 32'h3ECCCCCD; // 0.4
        b = 32'h41200000; // 10.0
        #100;
        display_result(a, b, result, flags);

        $display("\nTestbench completed.");
        #50;
        $finish;
    end

endmodule
