/* 
 * Finite State Machine 2 Verilog example testbench (iverilog 10.1)
 *
 * Required behavior:
 * 1. Serial 3 bit slicing input
 * 2. After detecting an odd number sets output to 1 for 3 clock cycles
 * 3. MSB goes first
 */

`timescale 1ns/1ps

`include "../design/fsm_2.v"

 module fsm_tb;

    /* inputs */
    reg Clock;
    reg Reset;
    reg In;

    /* outputs */
    wire Out;

    /* constants */
    parameter TABLE_SIZE = 30;

    /* variables */
    integer i;
    reg [TABLE_SIZE - 1 : 0] values =  {1'b0, 1'b0, 1'b0,
                                        1'b0, 1'b0, 1'b0,
                                        1'b0, 1'b0, 1'b1,
                                        1'b0, 1'b1, 1'b0,
                                        1'b0, 1'b1, 1'b1,
                                        1'b1, 1'b0, 1'b0,
                                        1'b1, 1'b0, 1'b1,
                                        1'b1, 1'b1, 1'b0,
                                        1'b1, 1'b1, 1'b1,
                                        1'b1, 1'b1, 1'b1};

    /* instantiate the uut */
    fsm uut(.clock(Clock), .reset(Reset), .out(Out), .in(In));

    initial
    begin
        $display("FSM 2 testbench...\n");
        $dumpfile("fsm_2_test.vcd");
        $dumpvars;

        /* Reset routine */
        Clock = 0;
        i = 0;
        Reset = 0;
        #10;
        Reset = 1;
        #5;
        Clock = 1;
        #5;
        Reset = 0;
        Clock = 0;
        In = 0;
        #20;

        /* Check all the values from the array */
        for (i = TABLE_SIZE - 1; i >= 0; i = i - 1)
            begin
                In = values[i];
                Clock = ~Clock; #10;
                Clock = ~Clock; #10;
            end

        $display("Done...");
    end

endmodule
    
