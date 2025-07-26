`timescale 1ns / 1ps

module dual_port_memory_tb;
    
    // Parameters
    parameter DATA_WIDTH = 4;
    parameter ADDR_WIDTH = 5;
    
    // Signals
    reg clk;
    reg we_a, we_b;
    reg [ADDR_WIDTH-1:0] addr_a, addr_b;
    reg [DATA_WIDTH-1:0] data_in_a, data_in_b;
    wire [DATA_WIDTH-1:0] data_out_a, data_out_b;
    
    // Instantiate the dual-port memory module
    dual_port_memory #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) uut (
        .clk(clk),
        .we_a(we_a),
        .we_b(we_b),
        .addr_a(addr_a),
        .addr_b(addr_b),
        .data_in_a(data_in_a),
        .data_in_b(data_in_b),
        .data_out_a(data_out_a),
        .data_out_b(data_out_b)
    );
    
    // Clock generation
    always #5 clk = ~clk; // 10ns period

    // Monitor for real-time tracking
    initial begin
        $monitor("Time = %0t | we_a=%b addr_a=%d data_in_a=%b data_out_a=%b | we_b=%b addr_b=%d data_in_b=%b data_out_b=%b", 
                 $time, we_a, addr_a, data_in_a, data_out_a, we_b, addr_b, data_in_b, data_out_b);
    end

    initial begin
        // Initialize signals
        clk = 0;
        we_a = 0;
        we_b = 0;
        addr_a = 0;
        addr_b = 0;
        data_in_a = 0;
        data_in_b = 0;
        
        // Apply test cases
        #10;
        
        // Write to port A and port B at different addresses
        we_a = 1; addr_a = 5; data_in_a = 4'b1010;
        we_b = 1; addr_b = 10; data_in_b = 4'b1100;
        $display("Time = %0t | Writing 1010 to addr 5 on Port A, Writing 1100 to addr 10 on Port B", $time);
        #10;
        
        // Disable write enables and read back
        we_a = 0; addr_a = 5;
        we_b = 0; addr_b = 10;
        #10;
        $display("Time = %0t | Reading from addr 5 on Port A: %b, addr 10 on Port B: %b", $time, data_out_a, data_out_b);
        
        // Check output values
        if (data_out_a !== 4'b1010) $display("Test Failed: Port A Read Mismatch");
        if (data_out_b !== 4'b1100) $display("Test Failed: Port B Read Mismatch");
        
        // Write to the same address with both ports
        we_a = 1; addr_a = 7; data_in_a = 4'b0110;
        we_b = 1; addr_b = 7; data_in_b = 4'b1001;
        $display("Time = %0t | Writing 0110 to addr 7 on Port A, Writing 1001 to addr 7 on Port B", $time);
        #10;
        
        // Disable write enables
        we_a = 0; we_b = 0;
        addr_a = 7; addr_b = 7;
        #10;
        $display("Time = %0t | Reading from addr 7 on both ports: Port A: %b, Port B: %b", $time, data_out_a, data_out_b);
        
        // Check last write dominance (port B writes last)
        if (data_out_a !== 4'b1001 || data_out_b !== 4'b1001) $display("Test Failed: Last Write Dominance Issue");
        
        // End simulation
        $display("Time = %0t | Test Completed", $time);
        $finish;
    end
    
endmodule