`include "../design_context/sd_defines.h"

module sd_wb_sel_ctrl(
           input wb_clk,
           input rst,
           input ena,
           input [31:0] base_adr_i,
           input [31:0] wbm_adr_i,
           input [`BLKSIZE_W+`BLKCNT_W-1:0] xfersize,
           output [3:0] wbm_sel_o
       );

function [3:0] get_first_sel;
    input [1:0] byte_addr;
    begin
        case (byte_addr)
            2'b00: get_first_sel = 4'b1111;
            2'b01: get_first_sel = 4'b0111;
            2'b10: get_first_sel = 4'b0011;
            2'b11: get_first_sel = 4'b0001;
        endcase
    end
endfunction

function [3:0] get_last_sel;
    input [1:0] byte_addr;
    begin
        case (byte_addr)
            2'b00: get_last_sel = 4'b1111;
            2'b01: get_last_sel = 4'b1000;
            2'b10: get_last_sel = 4'b1100;
            2'b11: get_last_sel = 4'b1110;
        endcase
    end
endfunction

reg [31:0] base_adr_reg;
reg [`BLKSIZE_W+`BLKCNT_W-1:0] xfersize_reg;
wire [31:0] base_adr_plus_xfersize;

wire [3:0] first_mask;
wire [3:0] second_mask;

assign base_adr_plus_xfersize = base_adr_reg + xfersize_reg;
assign first_mask = base_adr_reg[31:2] == wbm_adr_i[31:2] ?
                    get_first_sel(base_adr_reg[1:0]) :
                    4'b1111;
assign second_mask = base_adr_plus_xfersize[31:2] == wbm_adr_i[31:2] ?
                   get_last_sel(base_adr_plus_xfersize[1:0]) :
                   4'b1111;
assign wbm_sel_o = first_mask & second_mask;

always @(posedge wb_clk or posedge rst)
    if (rst) begin
        base_adr_reg <= 0;
        xfersize_reg <= 0;
    end
    else begin
        if (!ena) begin
            base_adr_reg <= base_adr_i;
            xfersize_reg <= xfersize;
        end
    end

endmodule

    
