
/* 
 * Finite State Machine 1 Verilog example (iverilog 10.1)
 *
 * Required behavior:
 * 1. One input & one output
 * 2. Sets '1' on the output after input is set to '011' and keeps until input sequence changes to '100'
 * 3. System works in a continuous manner
 */
 
 module fsm
 (
     input clock,
     input reset,
     output reg out,
     input [2:0] in
 );

    reg state;

    parameter IN_1 = 3'b011;
    parameter IN_0 = 3'b100;

    parameter S0 = 0;
    parameter S1 = 1;

    always @ (posedge(clock))
    if (reset)
        state <= S0;
    else
        begin
            case (in)
                IN_0:
                    begin
                        state <= S0;
                    end
                IN_1:
                    begin
                        state <= S1;
                    end
                default:
                    state <= state; 
            endcase
        end   

    always @ (*)
    if (state == S1)
        out <= 1;
    else
        out <= 0;


endmodule