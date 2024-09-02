module tlfsmtb;
    wire [2:0] state;
    reg clock;
    reg rst_n;

    tlfsm DUT(state, clock, rst_n);

    initial begin
        $dumpfile("tlfsm.vcd");
        $dumpvars(0, DUT);

        clock = 0;
        rst_n = 0;
        # 10
        rst_n = 1;
        # 1000
        $finish;
    end

    always #5 clock <= ~clock;
endmodule
