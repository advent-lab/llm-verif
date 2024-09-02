module countertb;
    `define WIDTH       16
    wire [`WIDTH-1:0] counter_value;
    reg [`WIDTH-1:0] counter_loader;
    wire match;
    reg clk;
    reg rst_n;
    reg restart;
    reg [1:0] setup;

    counter #(`WIDTH) DUT(counter_value, match, clk, rst_n, restart, setup);

    assign counter_value = (setup == 2'b00) ? { `WIDTH{1'bz} } : counter_loader;

    initial begin
        $dumpfile("counter.vcd");
        $dumpvars(0, DUT);

        clk = 1'b0;
        rst_n = 1'b0;
        counter_loader = { `WIDTH{1'b0} };
        setup = 2'b00;
        restart = 1'b0;
        # 10
        rst_n = 1'b1;
        # 200
        restart = 1'b1;
        # 10
        restart = 1'b0;
        # 200
        // from 0xf to 0
        counter_loader = { `WIDTH{1'b0} };
        counter_loader[3:0] = 4'h9;
        setup = 2'b11;
        # 10
        setup = 2'b00;
        repeat (5) begin
            @(posedge match)
            // from 0xf to 0
            counter_loader = { `WIDTH{1'b0} };
            counter_loader[3:0] = 4'hf;
            setup = 2'b11;
            # 10
            setup = 2'b00;
            @(posedge match)
            // from 0x7 to 0
            counter_loader = { `WIDTH{1'b0} };
            counter_loader[3:0] = 4'h7;
            setup = 2'b11;
            # 10
            setup = 2'b00;
            @(posedge match)
            // from 10 to 0
            counter_loader = { `WIDTH{1'b0} };
            counter_loader[3:0] = 4'd10;
            setup = 2'b11;
            # 10
            setup = 2'b00;
        
        end
        counter_loader[7:0] = 8'h7f;
        setup = 2'b10;
        # 10 
        setup = 2'b00;
        # 200
        restart = 1'b1;
        # 10
        restart = 1'b0;

        #5000
        $finish;

    end

    always #5 clk = ~clk;

endmodule
