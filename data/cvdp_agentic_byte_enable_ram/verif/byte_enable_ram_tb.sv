`timescale 1ns/1ps

module byte_enable_ram_tb;

    parameter XLEN  = 32;
    parameter LINES = 128;  // Smaller for testing

    logic                     clk;
    logic[$clog2(LINES)-1:0]  addr_a;
    logic                     en_a;
    logic[XLEN/8-1:0]         be_a;
    logic[XLEN-1:0]           data_in_a;
    wire [XLEN-1:0]           data_out_a;
    logic[$clog2(LINES)-1:0]  addr_b;
    logic                     en_b;
    logic[XLEN/8-1:0]         be_b;
    logic[XLEN-1:0]           data_in_b;
    wire [XLEN-1:0]           data_out_b;

    // DUT instantiation
    custom_byte_enable_ram #(
        .XLEN(XLEN),
        .LINES(LINES)
    ) dut (
        .clk(clk),
        .addr_a(addr_a),
        .en_a(en_a),
        .be_a(be_a),
        .data_in_a(data_in_a),
        .data_out_a(data_out_a),
        .addr_b(addr_b),
        .en_b(en_b),
        .be_b(be_b),
        .data_in_b(data_in_b),
        .data_out_b(data_out_b)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        // Initialize
        addr_a = 0;
        en_a = 0;
        be_a = 0;
        data_in_a = 0;
        addr_b = 0;
        en_b = 0;
        be_b = 0;
        data_in_b = 0;

        #20;

        // Write to port A with full byte enable
        @(posedge clk);
        addr_a = 5;
        en_a = 1;
        be_a = 4'b1111;  // All bytes enabled
        data_in_a = 32'hDEADBEEF;

        // Write to port B with partial byte enable
        @(posedge clk);
        addr_b = 10;
        en_b = 1;
        be_b = 4'b0011;  // Only lower 2 bytes
        data_in_b = 32'h12345678;

        // Read from port A
        @(posedge clk);
        en_a = 0;
        addr_a = 5;

        // Read from port B
        @(posedge clk);
        en_b = 0;
        addr_b = 10;

        // Additional writes with different byte enables
        repeat(10) begin
            @(posedge clk);
            addr_a = $random % LINES;
            en_a = $random % 2;
            be_a = $random % 16;
            data_in_a = $random;

            addr_b = $random % LINES;
            en_b = $random % 2;
            be_b = $random % 16;
            data_in_b = $random;
        end

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t addr_a=%h en_a=%b be_a=%b din_a=%h dout_a=%h addr_b=%h en_b=%b be_b=%b din_b=%h dout_b=%h",
                 $time, addr_a, en_a, be_a, data_in_a, data_out_a, addr_b, en_b, be_b, data_in_b, data_out_b);
    end

endmodule
