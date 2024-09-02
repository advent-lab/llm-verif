/* 
 * Finite State Machine 2 Verilog example (iverilog 10.1)
 *
 * Required behavior:
 * 1. Serial 3 bit slicing input
 * 2. After detecting an odd number sets output to 1 for 3 clock cycles
 * 3. MSB goes first
 */
 
 module fsm
 (
     input clock,
     input reset,
     output reg out,
     input in
 );

    reg [1:0] state;
    reg [2:0] bit_shift_reg;

    parameter [1:0] S0 = 2'd0;
    parameter [1:0] S1 = 2'd1;
    parameter [3:0] S2 = 2'd2;

    always @ (posedge(clock))
    if (reset)
        state <= S0;
    else
        begin
            case (state)
            S0:
                begin
                    bit_shift_reg <= {bit_shift_reg[1:0], in};
                    state <= S1;
                    if (bit_shift_reg % 2 == 0 || bit_shift_reg == 0)
                        out <= 0;
                    else
                        out <= 1;
                end
            S1:
                begin
                    bit_shift_reg <= {bit_shift_reg[1:0], in};
                    state <= S2;
                end
            S2:
                begin
                    bit_shift_reg <= {bit_shift_reg[1:0], in};
                    state <= S0;
                end    
            default:
                state <= S0; 
            endcase
        end    
endmodule