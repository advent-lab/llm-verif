`timescale 1ns/1ps

module cic_decimator_tb;

    parameter WIDTH = 16;
    parameter RMAX = 4;
    parameter M = 1;
    parameter N = 2;
    parameter REG_WIDTH = WIDTH + $clog2((RMAX * M)**N);

    logic                      clk;
    logic                      rst;
    logic [WIDTH-1:0]          input_tdata;
    logic                      input_tvalid;
    logic                      output_tready;
    logic [$clog2(RMAX+1)-1:0] rate;
    wire                       input_tready;
    wire  [REG_WIDTH-1:0]      output_tdata;
    wire                       output_tvalid;

    // DUT instantiation
    cic_decimator #(
        .WIDTH(WIDTH),
        .RMAX(RMAX),
        .M(M),
        .N(N)
    ) dut (
        .clk(clk),
        .rst(rst),
        .input_tdata(input_tdata),
        .input_tvalid(input_tvalid),
        .output_tready(output_tready),
        .rate(rate),
        .input_tready(input_tready),
        .output_tdata(output_tdata),
        .output_tvalid(output_tvalid)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        // Initialize
        rst = 1;
        input_tdata = 0;
        input_tvalid = 0;
        output_tready = 1;
        rate = 2;  // Decimation rate

        #20;
        rst = 0;
        #20;

        // Send some data
        repeat(20) begin
            @(posedge clk);
            if (input_tready) begin
                input_tvalid = 1;
                input_tdata = $random & 16'hFFFF;
            end else begin
                input_tvalid = 0;
            end
        end

        @(posedge clk);
        input_tvalid = 0;

        // Toggle output ready
        #50;
        @(posedge clk);
        output_tready = 0;
        #30;
        @(posedge clk);
        output_tready = 1;

        // More data with different rate
        @(posedge clk);
        rate = 4;

        repeat(15) begin
            @(posedge clk);
            if (input_tready) begin
                input_tvalid = 1;
                input_tdata = $random & 16'hFFFF;
            end
        end

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t rst=%b rate=%0d in_valid=%b in_data=%h in_ready=%b out_valid=%b out_data=%h out_ready=%b",
                 $time, rst, rate, input_tvalid, input_tdata, input_tready, output_tvalid, output_tdata, output_tready);
    end

endmodule
