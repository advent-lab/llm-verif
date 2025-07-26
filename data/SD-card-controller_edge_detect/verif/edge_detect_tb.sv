module edge_detect_tb();

parameter TCLK = 20; // 50 MHz -> timescale 1ns

reg rst;
reg clk;
reg sig;
wire rise;
wire fall;

sd_edge_detect edge_detect_dut(
    .rst(rst),
    .clk(clk),
    .sig(sig), 
    .rise(rise),
    .fall(fall)
);

// Generating clk clock
always
begin
    clk=0;
    forever #(TCLK/2) clk = ~clk;
end

initial
begin
    rst = 1;
    sig = 0;
    
    #(3.2*TCLK);
    rst = 0;
    
    $display("edge_detect_tb start ...");

    //one cycle sig
    sig = 1;
    #TCLK;
    assert(rise == 1);
    assert(fall == 0);
    
    sig = 0;
    #TCLK;
    assert(rise == 0);
    assert(fall == 1);

    #TCLK;
    assert(rise == 0);
    assert(fall == 0);
    #TCLK;
    assert(rise == 0);
    assert(fall == 0);

    //multiple cycles sig
    sig = 1;
    #TCLK;
    assert(rise == 1);
    assert(fall == 0);
    #TCLK;
    assert(rise == 0);
    assert(fall == 0);
    #TCLK;
    assert(rise == 0);
    assert(fall == 0);
    
    sig = 0;
    #TCLK;
    assert(rise == 0);
    assert(fall == 1);
    #TCLK;
    assert(rise == 0);
    assert(fall == 0);
    #TCLK;
    assert(rise == 0);
    assert(fall == 0);

    #(10*TCLK) $display("edge_detect_tb finish ...");
    $finish;
    
end

endmodule 
