module cntclk2tb;
    `define WIDTH       16

    wire output_clock;
    wire zero;
    wire [`WIDTH-1:0] counter_value;
    reg clk;
    reg rst_n;
    reg desc;
    reg [`WIDTH-1:0] setup;

    cntclk2 #(`WIDTH) DUT(output_clock, zero, counter_value, clk, rst_n, desc, setup);

    initial begin
        $dumpfile("cntclk2.vcd");
        $dumpvars(0, DUT);

        clk = 1'b0;
        rst_n = 1'b0;
        desc = 1'b1;
        setup = {`WIDTH{1'b0}};
        setup[3:0] = 4'hf;
        # 10
        rst_n = 1'b1;
        # 500
        setup[3:0] = 4'h3;
        desc = 1'b0;
        rst_n = 1'b0;
        # 10
        rst_n = 1'b1;

        #5000
        $finish;

    end

    always #5 clk = ~clk;

endmodule
