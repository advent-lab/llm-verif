module onehzclktb;
    `define WIDTH       2
    `define COMPARE     4-1

    wire output_clock;
    reg clk;
    reg rst_n;

    onehzclk #(`COMPARE, `WIDTH) DUT(output_clock, clk, rst_n);

    initial begin
        $dumpfile("onehzclk.vcd");
        $dumpvars(0, DUT);

        clk = 1'b0;
        rst_n = 1'b0;
        # 10
        rst_n = 1'b1;
    
        #5000
        $finish;

    end

    always #5 clk = ~clk;

endmodule
