module counter2tb;
    `define WIDTH       16
    wire [`WIDTH-1:0] counter_value;
    wire match;
    reg clk;
    reg rst_n;
    reg desc;
    reg [`WIDTH-1:0] setup;

    counter2 #(`WIDTH) DUT(counter_value, match, clk, rst_n, desc, setup);

    initial begin
        $dumpfile("counter2.vcd");
        $dumpvars(0, DUT);

        clk = 1'b0;
        rst_n = 1'b0;
        setup = { `WIDTH{1'b0} };
        setup[3:0] = 4'hf;
        desc = 1'b0;
        # 10
        rst_n = 1'b1;
        # 200
        desc = 1'b1;
        rst_n = 1'b0;
        # 10
        rst_n = 1'b1;
        # 200
        // from 0xf to 0
        repeat (5) begin
            @(posedge match)
            // from 0xf to 0
            setup = { `WIDTH{1'b0} };
            setup[3:0] = 4'hf;
            rst_n = 1'b0;
            # 10
            rst_n = 1'b1;
            @(posedge match)
            // from 0x7 to 0
            setup = { `WIDTH{1'b0} };
            setup[3:0] = 4'h7;
            rst_n = 1'b0;
            # 10
            rst_n = 1'b1;
            @(posedge match)
            // from 10 to 0
            setup = { `WIDTH{1'b0} };
            setup[3:0] = 4'd10;
            rst_n = 1'b0;
            # 10
            rst_n = 1'b1;
        
        end
        setup[7:0] = 8'h7f;
        rst_n = 1'b0;
        # 10 
        rst_n = 1'b1;

        #5000
        $finish;

    end

    always #5 clk = ~clk;

endmodule
