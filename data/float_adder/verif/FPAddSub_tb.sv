`timescale 1ns/1ps

module FPAddSub_tb;

    // Testbench signals
    reg clk;
    reg rst;
    reg [31:0] a;
    reg [31:0] b;
    reg operation;  // 0 = add, 1 = subtract

    wire [31:0] result;
    wire [4:0] flags;  // [4]=overflow, [3]=underflow, [2]=div_by_zero, [1]=invalid, [0]=inexact

    // Instantiate DUT
    FPAddSub dut (
        .clk(clk),
        .rst(rst),
        .a(a),
        .b(b),
        .operation(operation),
        .result(result),
        .flags(flags)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk; // 100MHz clock
    end

    // Helper function to display floating point values
    task display_result;
        input [31:0] val_a;
        input [31:0] val_b;
        input op;
        input [31:0] res;
        input [4:0] flg;
        begin
            $display("Time=%0t: A=%h B=%h OP=%s => Result=%h Flags=%b",
                     $time, val_a, val_b, op ? "SUB" : "ADD", res, flg);
        end
    endtask

    // Test sequence
    initial begin
        $display("Starting FPAddSub testbench...");

        // Initialize
        rst = 1;
        a = 0;
        b = 0;
        operation = 0;

        // Reset sequence
        #20;
        rst = 0;
        #10;

        // Test 1: Addition of positive numbers
        // 1.0 + 2.0 = 3.0
        $display("\nTest 1: Simple addition");
        operation = 0;
        a = 32'h3F800000; // 1.0
        b = 32'h40000000; // 2.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 2: Subtraction
        // 5.0 - 3.0 = 2.0
        $display("\nTest 2: Simple subtraction");
        operation = 1;
        a = 32'h40A00000; // 5.0
        b = 32'h40400000; // 3.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 3: Addition with zero
        $display("\nTest 3: Addition with zero");
        operation = 0;
        a = 32'h3F800000; // 1.0
        b = 32'h00000000; // 0.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 4: Addition of negative and positive
        $display("\nTest 4: Adding negative and positive");
        operation = 0;
        a = 32'hBF800000; // -1.0
        b = 32'h40000000; // 2.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 5: Large number addition
        $display("\nTest 5: Large numbers");
        operation = 0;
        a = 32'h42C80000; // 100.0
        b = 32'h43480000; // 200.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 6: Small number addition
        $display("\nTest 6: Small numbers");
        operation = 0;
        a = 32'h3DCCCCCD; // 0.1
        b = 32'h3E4CCCCD; // 0.2
        #100;
        display_result(a, b, operation, result, flags);

        // Test 7: Subtraction resulting in negative
        $display("\nTest 7: Subtraction resulting in negative");
        operation = 1;
        a = 32'h40000000; // 2.0
        b = 32'h40A00000; // 5.0
        #100;
        display_result(a, b, operation, result, flags);

        // Test 8: Addition of same numbers
        $display("\nTest 8: Adding equal numbers");
        operation = 0;
        a = 32'h40490FDB; // Pi (3.14159...)
        b = 32'h40490FDB; // Pi
        #100;
        display_result(a, b, operation, result, flags);

        // Test 9: Subtraction of equal numbers
        $display("\nTest 9: Subtracting equal numbers");
        operation = 1;
        a = 32'h40490FDB; // Pi
        b = 32'h40490FDB; // Pi
        #100;
        display_result(a, b, operation, result, flags);

        // Test 10: Various corner cases
        $display("\nTest 10: Corner cases");
        operation = 0;
        a = 32'h7F7FFFFF; // Max normal float
        b = 32'h3F800000; // 1.0
        #100;
        display_result(a, b, operation, result, flags);

        $display("\nTestbench completed.");
        #50;
        $finish;
    end

endmodule
