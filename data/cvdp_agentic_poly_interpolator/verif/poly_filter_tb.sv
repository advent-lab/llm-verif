`timescale 1ns/1ps

module poly_filter_tb;

    parameter N           = 4;
    parameter TAPS        = 8;
    parameter COEFF_WIDTH = 16;
    parameter DATA_WIDTH  = 16;
    localparam ACC_WIDTH  = DATA_WIDTH + COEFF_WIDTH + $clog2(TAPS);

    logic                         clk;
    logic                         arst_n;
    logic [DATA_WIDTH-1:0]        sample_buffer [0:TAPS-1];
    logic                         valid_in;
    logic [$clog2(N)-1:0]         phase;
    wire  [ACC_WIDTH-1:0]         filter_out;
    wire                          valid;

    // DUT instantiation
    poly_filter #(
        .N(N),
        .TAPS(TAPS),
        .COEFF_WIDTH(COEFF_WIDTH),
        .DATA_WIDTH(DATA_WIDTH)
    ) dut (
        .clk(clk),
        .arst_n(arst_n),
        .sample_buffer(sample_buffer),
        .valid_in(valid_in),
        .phase(phase),
        .filter_out(filter_out),
        .valid(valid)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        integer i;

        // Initialize
        arst_n = 0;
        valid_in = 0;
        phase = 0;
        for (i = 0; i < TAPS; i = i + 1) begin
            sample_buffer[i] = 0;
        end

        #20;
        arst_n = 1;
        #20;

        // Send data with phase 0
        @(posedge clk);
        valid_in = 1;
        phase = 0;
        for (i = 0; i < TAPS; i = i + 1) begin
            sample_buffer[i] = $random & 16'hFFFF;
        end

        @(posedge clk);
        valid_in = 0;

        #50;

        // Send data with phase 1
        @(posedge clk);
        valid_in = 1;
        phase = 1;
        for (i = 0; i < TAPS; i = i + 1) begin
            sample_buffer[i] = $random & 16'hFFFF;
        end

        @(posedge clk);
        valid_in = 0;

        #50;

        // Send data with phase 2
        @(posedge clk);
        valid_in = 1;
        phase = 2;
        for (i = 0; i < TAPS; i = i + 1) begin
            sample_buffer[i] = $random & 16'hFFFF;
        end

        @(posedge clk);
        valid_in = 0;

        #50;

        // Multiple samples with different phases
        repeat(10) begin
            @(posedge clk);
            valid_in = 1;
            phase = $random % N;
            for (i = 0; i < TAPS; i = i + 1) begin
                sample_buffer[i] = $random & 16'hFFFF;
            end

            @(posedge clk);
            valid_in = 0;

            #20;
        end

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t arst_n=%b valid_in=%b phase=%0d valid_out=%b filter_out=%h",
                 $time, arst_n, valid_in, phase, valid, filter_out);
    end

endmodule
