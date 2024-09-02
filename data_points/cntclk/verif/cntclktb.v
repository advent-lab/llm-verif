module cntclktb;
    `define WIDTH       16

    wire output_clock;
    wire zero;
    wire [`WIDTH-1:0] counter_value;
    reg [`WIDTH-1:0] counter_loader;
    reg clk;
    reg rst_n;
    reg load;
    reg desc;

    cntclk #(`WIDTH) DUT(output_clock, zero, counter_value, clk, rst_n, load);

    assign counter_value = load ? counter_loader : { `WIDTH{1'bz} };

    initial begin
        $dumpfile("cntclk.vcd");
        $dumpvars(0, DUT);

        clk = 1'b0;
        rst_n = 1'b0;
        counter_loader = { `WIDTH{1'b0} };
        load = 1'b0;
        desc = 1'b0;
        # 10
        rst_n = 1'b1;
        # 500
        counter_loader[3:0] = 4'h3;
        load = 1'b1;
        # 10
        load = 1'b0;

        #5000
        $finish;

    end

    always #5 clk = ~clk;

endmodule
