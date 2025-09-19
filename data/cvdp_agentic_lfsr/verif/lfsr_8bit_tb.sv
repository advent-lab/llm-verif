module lfsr_8bit_tb;
    reg clk;
    reg rst;
    reg [7:0] seed;
    wire [7:0] lfsr_out;
    reg [7:0] expected_lfsr;
    reg [7:0] shift_reg;
    integer i;

    always #5 clk = ~clk; // Clock generation

    initial begin
        clk = 0; rst = 1; seed = 8'b10101010; expected_lfsr = seed;
        #10; rst = 0;

        for (i = 0; i < 20; i = i + 1) begin
            #10;
            shift_reg = {expected_lfsr[6:0], expected_lfsr[7] ^ expected_lfsr[5] ^ expected_lfsr[4] ^ expected_lfsr[3]}; // polynomial
            if (lfsr_out !== shift_reg) begin
                $error("ERROR at cycle %d: Expected %b, Got %b", i, shift_reg, lfsr_out);
            end
            expected_lfsr = shift_reg;
        end

        $finish;
    end

    // Instantiate the DUT
    lfsr_8bit dut (
        .clk(clk),
        .rst(rst),
        .seed(seed),
        .lfsr_out(lfsr_out)
    );

    // Waveform generation
    initial begin
        $dumpfile("lfsr_8bit.vcd");
        $dumpvars(0, lfsr_8bit_tb);
    end

endmodule