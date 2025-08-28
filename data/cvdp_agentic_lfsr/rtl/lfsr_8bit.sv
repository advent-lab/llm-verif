module lfsr_8bit (
    input wire clk,
    input wire rst,
    input wire [7:0] seed,  // User-defined initial seed
    output reg [7:0] lfsr_out
);

    always @(posedge clk or posedge rst) begin
        if (rst)
            lfsr_out <= 8'b00000001;
        else begin
            lfsr_out <= {lfsr_out[6:0], lfsr_out[7] ^ lfsr_out[5] ^ lfsr_out[3]};
        end
    end
endmodule