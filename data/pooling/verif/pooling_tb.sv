`timescale 1ns/1ns

module pooling_tb;

    // Parameters
    parameter DWIDTH = 8;
    parameter AWIDTH = 11;

    // Testbench signals
    reg clk;
    reg resetn;
    reg start_pooling;
    reg pool_select;  // 0 = max pooling, 1 = average pooling
    reg enable_pool;
    reg [DWIDTH-1:0] rdata_accum0_pool, rdata_accum1_pool, rdata_accum2_pool, rdata_accum3_pool;
    reg [DWIDTH-1:0] rdata_accum4_pool, rdata_accum5_pool, rdata_accum6_pool, rdata_accum7_pool;
    reg [AWIDTH-1:0] matrix_size;
    reg [AWIDTH-1:0] filter_size;

    wire pool_norm_valid;
    wire [DWIDTH-1:0] pool0, pool1, pool2, pool3, pool4, pool5, pool6, pool7;
    wire [AWIDTH-1:0] raddr_accum0_pool, raddr_accum1_pool, raddr_accum2_pool, raddr_accum3_pool;
    wire [AWIDTH-1:0] raddr_accum4_pool, raddr_accum5_pool, raddr_accum6_pool, raddr_accum7_pool;

    // Instantiate DUT
    pooling dut (
        .clk(clk),
        .resetn(resetn),
        .start_pooling(start_pooling),
        .pool_select(pool_select),
        .pool_norm_valid(pool_norm_valid),
        .enable_pool(enable_pool),
        .rdata_accum0_pool(rdata_accum0_pool),
        .rdata_accum1_pool(rdata_accum1_pool),
        .rdata_accum2_pool(rdata_accum2_pool),
        .rdata_accum3_pool(rdata_accum3_pool),
        .rdata_accum4_pool(rdata_accum4_pool),
        .rdata_accum5_pool(rdata_accum5_pool),
        .rdata_accum6_pool(rdata_accum6_pool),
        .rdata_accum7_pool(rdata_accum7_pool),
        .raddr_accum0_pool(raddr_accum0_pool),
        .raddr_accum1_pool(raddr_accum1_pool),
        .raddr_accum2_pool(raddr_accum2_pool),
        .raddr_accum3_pool(raddr_accum3_pool),
        .raddr_accum4_pool(raddr_accum4_pool),
        .raddr_accum5_pool(raddr_accum5_pool),
        .raddr_accum6_pool(raddr_accum6_pool),
        .raddr_accum7_pool(raddr_accum7_pool),
        .pool0(pool0),
        .pool1(pool1),
        .pool2(pool2),
        .pool3(pool3),
        .pool4(pool4),
        .pool5(pool5),
        .pool6(pool6),
        .pool7(pool7),
        .matrix_size(matrix_size),
        .filter_size(filter_size)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk; // 100MHz clock
    end

    // Test sequence
    initial begin
        $display("Starting pooling testbench...");

        // Initialize
        resetn = 0;
        start_pooling = 0;
        pool_select = 0;
        enable_pool = 0;
        matrix_size = 8;
        filter_size = 2;
        rdata_accum0_pool = 0;
        rdata_accum1_pool = 0;
        rdata_accum2_pool = 0;
        rdata_accum3_pool = 0;
        rdata_accum4_pool = 0;
        rdata_accum5_pool = 0;
        rdata_accum6_pool = 0;
        rdata_accum7_pool = 0;

        // Reset sequence
        #20;
        resetn = 1;
        #10;

        // Test 1: Max pooling with random data
        $display("\nTest 1: Max pooling");
        enable_pool = 1;
        pool_select = 0; // Max pooling
        start_pooling = 1;
        rdata_accum0_pool = 8'd10;
        rdata_accum1_pool = 8'd20;
        rdata_accum2_pool = 8'd30;
        rdata_accum3_pool = 8'd40;
        rdata_accum4_pool = 8'd50;
        rdata_accum5_pool = 8'd60;
        rdata_accum6_pool = 8'd70;
        rdata_accum7_pool = 8'd80;
        #10;
        start_pooling = 0;
        #100;

        // Test 2: Average pooling
        $display("\nTest 2: Average pooling");
        pool_select = 1; // Average pooling
        start_pooling = 1;
        rdata_accum0_pool = 8'd100;
        rdata_accum1_pool = 8'd200;
        rdata_accum2_pool = 8'd50;
        rdata_accum3_pool = 8'd150;
        rdata_accum4_pool = 8'd75;
        rdata_accum5_pool = 8'd125;
        rdata_accum6_pool = 8'd25;
        rdata_accum7_pool = 8'd175;
        #10;
        start_pooling = 0;
        #100;

        // Test 3: Pooling disabled (bypass mode)
        $display("\nTest 3: Pooling disabled");
        enable_pool = 0;
        start_pooling = 1;
        rdata_accum0_pool = 8'd11;
        rdata_accum1_pool = 8'd22;
        rdata_accum2_pool = 8'd33;
        rdata_accum3_pool = 8'd44;
        rdata_accum4_pool = 8'd55;
        rdata_accum5_pool = 8'd66;
        rdata_accum6_pool = 8'd77;
        rdata_accum7_pool = 8'd88;
        #10;
        start_pooling = 0;
        #100;

        // Test 4: Max pooling with extreme values
        $display("\nTest 4: Max pooling with extreme values");
        enable_pool = 1;
        pool_select = 0;
        start_pooling = 1;
        rdata_accum0_pool = 8'd255;
        rdata_accum1_pool = 8'd0;
        rdata_accum2_pool = 8'd255;
        rdata_accum3_pool = 8'd0;
        rdata_accum4_pool = 8'd128;
        rdata_accum5_pool = 8'd64;
        rdata_accum6_pool = 8'd32;
        rdata_accum7_pool = 8'd16;
        #10;
        start_pooling = 0;
        #100;

        // Test 5: Average pooling with same values
        $display("\nTest 5: Average pooling with same values");
        pool_select = 1;
        start_pooling = 1;
        rdata_accum0_pool = 8'd100;
        rdata_accum1_pool = 8'd100;
        rdata_accum2_pool = 8'd100;
        rdata_accum3_pool = 8'd100;
        rdata_accum4_pool = 8'd100;
        rdata_accum5_pool = 8'd100;
        rdata_accum6_pool = 8'd100;
        rdata_accum7_pool = 8'd100;
        #10;
        start_pooling = 0;
        #100;

        $display("\nTestbench completed.");
        $finish;
    end

    // Monitor outputs
    initial begin
        $monitor("Time=%0t: valid=%b pool[0]=%d pool[7]=%d",
                 $time, pool_norm_valid, pool0, pool7);
    end

endmodule
