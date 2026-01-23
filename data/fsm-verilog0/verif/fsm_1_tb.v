/* 
 * Finite State Machine 1 Verilog example testbench (iverilog 10.1)
 *
 * Required behavior:
 * 1. One input & one output
 * 2. Sets '1' on the output after input is set to '011' and keeps until input sequence changes to '100'
 * 3. System works in a continuous manner
 */

`timescale 1ns/1ps

`include "../design/fsm_1.v"

 module fsm_tb;

    /* inputs */
    reg Clock;
    reg Reset;
    reg [2:0] In;

    /* outputs */
    wire Out;

    /* variables */
    integer i;

    /* instantiate the uut */
    fsm uut(.clock(Clock), .reset(Reset), .out(Out), .in(In));

    initial
    begin
        $display("FSM 1 testbench...\n");
        $dumpfile("fsm_1_test.vcd");
        $dumpvars;

        Clock = 1'b0;
        i = 0;
        Reset = 0;
        #10;
        Reset = 1;
        #5;
        Clock = 1'b1;
        #5;
        Reset = 0;
        Clock = 1'b0;
        In = 3'b000;
        #20;

        while (i < 10) begin
            Clock = ~Clock; #10;
            Clock = ~Clock; #10;
            i = i + 1;
            In = In + 1;
        end

        i = 0;
        #10;

        while (i < 20) begin
            Clock = ~Clock; #10;
            Clock = ~Clock; #10;
            i = i + 1;
            In = In + 3;
        end

        $display("Done...");
    end

endmodule
    
