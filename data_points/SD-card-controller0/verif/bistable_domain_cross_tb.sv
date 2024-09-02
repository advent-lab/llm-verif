module bistable_domain_cross_tb();

parameter TCLK_A = 20; // 50 MHz -> timescale 1ns
parameter TCLK_B = 203; // 4.98 MHz -> timescale 1ns

reg rst;
reg clk_a;
reg [1:0] in;
reg clk_b;
wire [1:0] out;

bistable_domain_cross #(2) bistable_domain_cross_dut(
    .rst(rst),
    .clk_a(clk_a),
    .in(in), 
    .clk_b(clk_b),
    .out(out)
);

// Generating clk_a clock
always
begin
    clk_a=0;
    forever #(TCLK_A/2) clk_a = ~clk_a;
end

// Generating clk_b clock
always
begin
    clk_b=0;
    forever #(TCLK_B/2) clk_b = ~clk_b;
end

initial
begin
    rst = 1;
    in = 0;
    
    #(3.2*TCLK_B);
    rst = 0;
    
    $display("bistable_domain_cross_tb start ...");
    
    #(3*TCLK_B);
    @(posedge clk_a) #(0.1*TCLK_A);
    in = 2'b11;
    #TCLK_A;
    @(posedge clk_b)#(1.5*TCLK_B);
    
    assert(out == 2'b11);
    
    #TCLK_B;
    assert(out == 2'b11);
 
    @(posedge clk_a) #(0.1*TCLK_A);
    in = 2'b00;
    #TCLK_A;
 
    @(posedge clk_b)#(1.5*TCLK_B);
    #TCLK_B;

    assert(out == 2'b00);

    #(10*TCLK_B) $display("bistable_domain_cross_tb finish ...");
    $finish;
    
end

endmodule
