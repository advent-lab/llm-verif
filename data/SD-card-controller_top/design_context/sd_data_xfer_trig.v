`include "sd_defines.h" 

module sd_data_xfer_trig (
           input sd_clk,
           input rst,
           input cmd_with_data_start_i,
           input r_w_i,
           input [`INT_CMD_SIZE-1:0] cmd_int_status_i,
           output reg start_tx_o,
           output reg start_rx_o
       );

reg r_w_reg;
parameter SIZE = 2;
reg [SIZE-1:0] state;
reg [SIZE-1:0] next_state;
parameter IDLE             = 2'b00;
parameter WAIT_FOR_CMD_INT = 2'b01;
parameter TRIGGER_XFER     = 2'b10;

always @(state or cmd_with_data_start_i or r_w_i or cmd_int_status_i)
begin: FSM_COMBO
    case(state)
        IDLE: begin
            if (cmd_with_data_start_i & r_w_i)
                next_state = TRIGGER_XFER;
            else if (cmd_with_data_start_i)
                next_state = WAIT_FOR_CMD_INT;
            else
                next_state = IDLE;
        end
        WAIT_FOR_CMD_INT: begin
            if (cmd_int_status_i[`INT_CMD_CC])
                next_state = TRIGGER_XFER;
            else if (cmd_int_status_i[`INT_CMD_EI])
                next_state = IDLE;
            else
                next_state = WAIT_FOR_CMD_INT;
        end
        TRIGGER_XFER: begin
            next_state = IDLE;
        end
        default: next_state = IDLE;
    endcase
end

always @(posedge sd_clk or posedge rst)
begin: FSM_SEQ
    if (rst) begin
        state <= IDLE;
    end
    else begin
        state <= next_state;
    end
end

always @(posedge sd_clk or posedge rst)
begin
    if (rst) begin
        start_tx_o <= 0;
        start_rx_o <= 0;
        r_w_reg <= 0;
    end
    else begin
        case(state)
            IDLE: begin
                start_tx_o <= 0;
                start_rx_o <= 0;
                r_w_reg <= r_w_i;
            end
            WAIT_FOR_CMD_INT: begin
                start_tx_o <= 0;
                start_rx_o <= 0;
            end
            TRIGGER_XFER: begin
                start_tx_o <= ~r_w_reg;
                start_rx_o <= r_w_reg;
            end
        endcase
    end
end

endmodule