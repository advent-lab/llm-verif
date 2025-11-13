`timescale 1ns/1ps

module rgb_color_space_hsv_tb;

    logic        clk;
    logic        rst;
    logic        we;
    logic [7:0]  waddr;
    logic [24:0] wdata;
    logic        valid_in;
    logic [7:0]  r_component;
    logic [7:0]  g_component;
    logic [7:0]  b_component;
    wire  [11:0] h_component;
    wire  [12:0] s_component;
    wire  [11:0] v_component;
    wire         valid_out;

    // DUT instantiation
    rgb_color_space_hsv dut (
        .clk(clk),
        .rst(rst),
        .we(we),
        .waddr(waddr),
        .wdata(wdata),
        .valid_in(valid_in),
        .r_component(r_component),
        .g_component(g_component),
        .b_component(b_component),
        .h_component(h_component),
        .s_component(s_component),
        .v_component(v_component),
        .valid_out(valid_out)
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
        we = 0;
        waddr = 0;
        wdata = 0;
        valid_in = 0;
        r_component = 0;
        g_component = 0;
        b_component = 0;

        #20;
        rst = 0;
        #20;

        // Initialize memory if needed (1/delta values)
        // For basic testing, we'll skip detailed memory initialization
        @(posedge clk);
        we = 1;
        waddr = 0;
        wdata = 25'h1000000;  // Some value
        @(posedge clk);
        we = 0;

        #20;

        // Test pure red
        @(posedge clk);
        valid_in = 1;
        r_component = 8'd255;
        g_component = 8'd0;
        b_component = 8'd0;

        @(posedge clk);
        valid_in = 0;

        #100;

        // Test pure green
        @(posedge clk);
        valid_in = 1;
        r_component = 8'd0;
        g_component = 8'd255;
        b_component = 8'd0;

        @(posedge clk);
        valid_in = 0;

        #100;

        // Test pure blue
        @(posedge clk);
        valid_in = 1;
        r_component = 8'd0;
        g_component = 8'd0;
        b_component = 8'd255;

        @(posedge clk);
        valid_in = 0;

        #100;

        // Test white
        @(posedge clk);
        valid_in = 1;
        r_component = 8'd255;
        g_component = 8'd255;
        b_component = 8'd255;

        @(posedge clk);
        valid_in = 0;

        #100;

        // Test black
        @(posedge clk);
        valid_in = 1;
        r_component = 8'd0;
        g_component = 8'd0;
        b_component = 8'd0;

        @(posedge clk);
        valid_in = 0;

        #100;

        // Random colors
        repeat(10) begin
            @(posedge clk);
            valid_in = 1;
            r_component = $random;
            g_component = $random;
            b_component = $random;

            @(posedge clk);
            valid_in = 0;

            #50;
        end

        #200;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t rst=%b valid_in=%b RGB=(%d,%d,%d) valid_out=%b H=%h S=%h V=%h",
                 $time, rst, valid_in, r_component, g_component, b_component,
                 valid_out, h_component, s_component, v_component);
    end

endmodule
