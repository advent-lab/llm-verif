`timescale 1ns / 1ps

module ttc_counter_lite_tb;
    
    reg clk;                    // Clock signal
    reg reset;                  // Reset signal
    reg [3:0] axi_addr;         // AXI address
    reg [31:0] axi_wdata;       // AXI write data
    reg axi_write_en;           // AXI write enable
    reg axi_read_en;            // AXI read enable
    wire [31:0] axi_rdata;      // AXI read data
    wire interrupt;             // Interrupt signal

    // Instantiate the DUT (Device Under Test)
    ttc_counter_lite uut (
        .clk(clk),
        .reset(reset),
        .axi_addr(axi_addr),
        .axi_wdata(axi_wdata),
        .axi_write_en(axi_write_en),
        .axi_read_en(axi_read_en),
        .axi_rdata(axi_rdata),
        .interrupt(interrupt)
    );

    // Clock generation: Generates a 100 MHz clock (10 ns period)
    always begin
        #5 clk = ~clk;
    end

    initial begin
        clk = 0;
        reset = 1;
        axi_addr = 4'b0;
        axi_wdata = 32'b0;
        axi_write_en = 0;
        axi_read_en = 0;
        #20;
        reset = 0;

        axi_addr = 4'b0001; 
        axi_wdata = 32'h0000008; 
        axi_write_en = 1;
        #10 axi_write_en = 0;
        
        axi_addr = 4'b0010; 
        axi_wdata = 32'h00000006; 
        axi_write_en = 1;
        #10 axi_write_en = 0;

        axi_addr = 4'b0011; 
        axi_wdata = 32'h00000007; 
        axi_write_en = 1;
        #10 axi_write_en = 0;

        axi_addr = 4'b0101; 
        axi_wdata = 32'h00000003; 
        axi_write_en = 1;
        #10 axi_write_en = 0;

        #200; 
        axi_addr = 4'b0000; 
        axi_read_en = 1;
        #90 axi_read_en = 0;
	if(axi_rdata[15:0]==32'h0000008)begin
	    	$display("[INFO] PASS Counter value read: %d", axi_rdata[15:0]);
	end
	else
		begin 
		$display("[ERROR] FAIL counter did not match ");
	end
        #50;
        axi_addr = 4'b0100; 
        axi_read_en = 1;
        #50 axi_read_en = 0;
	#10;
	if(axi_rdata[0])
	begin 
        $display("[INFO] PASS Interrupt status read: %b", axi_rdata[0]);
	end
	else
	begin
	$display("[ERROR] FAIL");
	end 
        axi_addr = 4'b0100; 
        axi_wdata = 32'b0;
        axi_write_en = 1;
        #60 axi_write_en = 0;
	if(~interrupt)
		$display("[INFO] PASS interupt is cleared  PASS");
	else  begin
		$display("[INFO] FAIL Interupt is not cleared  FAIL");
	end
        #100;
        $display("[INFO] Ending simulation");
        $finish;
    end

    initial begin
        $dumpfile("test.vcd");          
        $dumpvars(0, ttc_counter_lite_tb);     
    end    

endmodule