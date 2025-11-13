`timescale 1ns/1ns

module activation_tb;

    // Parameters from design
    parameter DWIDTH = 8;
    parameter MASK_WIDTH = 8;

    // Testbench signals
    reg clk;
    reg reset;
    reg activation_type;
    reg enable_activation;
    reg enable_pool;
    reg in_data_available;
    reg [DWIDTH-1:0] inp_data0, inp_data1, inp_data2, inp_data3;
    reg [DWIDTH-1:0] inp_data4, inp_data5, inp_data6, inp_data7;
    reg [MASK_WIDTH-1:0] validity_mask;

    wire [DWIDTH-1:0] out_data0, out_data1, out_data2, out_data3;
    wire [DWIDTH-1:0] out_data4, out_data5, out_data6, out_data7;
    wire out_data_available;
    wire done_activation;

    // Instantiate DUT
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
        .validity_mask(validity_mask),
        .done_activation(done_activation),
        .clk(clk),
        .reset(reset)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk; // 100MHz clock
    end

    // Test sequence
    initial begin
        $display("Starting activation testbench...");

        // Initialize signals
        reset = 1;
        activation_type = 0;
        enable_activation = 0;
        enable_pool = 0;
        in_data_available = 0;
        validity_mask = 8'hFF;
        inp_data0 = 0; inp_data1 = 0; inp_data2 = 0; inp_data3 = 0;
        inp_data4 = 0; inp_data5 = 0; inp_data6 = 0; inp_data7 = 0;

        // Reset sequence
        #20;
        reset = 0;
        #10;

        // Test 1: ReLU activation (activation_type = 0)
        $display("Test 1: ReLU activation");
        enable_activation = 1;
        activation_type = 0; // ReLU
        in_data_available = 1;
        inp_data0 = 8'd50;
        inp_data1 = 8'd100;
        inp_data2 = 8'd25;
        inp_data3 = 8'd75;
        inp_data4 = 8'd10;
        inp_data5 = 8'd200;
        inp_data6 = 8'd150;
        inp_data7 = 8'd30;
        #10;
        in_data_available = 0;
        #50;

        // Test 2: TanH activation (activation_type = 1)
        $display("Test 2: TanH activation");
        activation_type = 1; // TanH
        in_data_available = 1;
        inp_data0 = 8'd90;
        inp_data1 = 8'd45;
        inp_data2 = 8'd30;
        inp_data3 = 8'd20;
        inp_data4 = 8'd10;
        inp_data5 = 8'd0;
        inp_data6 = -8'd20;
        inp_data7 = -8'd50;
        #10;
        in_data_available = 0;
        #100;

        // Test 3: Activation disabled (bypass mode)
        $display("Test 3: Activation disabled (bypass mode)");
        enable_activation = 0;
        in_data_available = 1;
        inp_data0 = 8'd111;
        inp_data1 = 8'd222;
        inp_data2 = 8'd33;
        inp_data3 = 8'd44;
        inp_data4 = 8'd55;
        inp_data5 = 8'd66;
        inp_data6 = 8'd77;
        inp_data7 = 8'd88;
        #10;
        in_data_available = 0;
        #50;

        // Test 4: Mixed data patterns with ReLU
        $display("Test 4: Mixed data patterns with ReLU");
        enable_activation = 1;
        activation_type = 0;
        in_data_available = 1;
        inp_data0 = 8'd255;
        inp_data1 = 8'd128;
        inp_data2 = 8'd64;
        inp_data3 = 8'd32;
        inp_data4 = 8'd16;
        inp_data5 = 8'd8;
        inp_data6 = 8'd4;
        inp_data7 = 8'd2;
        #10;
        in_data_available = 0;
        #50;

        $display("Testbench completed.");
        $finish;
    end

    // Monitor outputs
    initial begin
        $monitor("Time=%0t: out_available=%b done=%b out[0]=%d out[7]=%d",
                 $time, out_data_available, done_activation, out_data0, out_data7);
    end

endmodule
