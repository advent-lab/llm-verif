`timescale 1ns/1ps

module memory_scheduler(
    input  wire         clk,
    input  wire         reset,
    input  wire [3:0]   request,      
    input  wire [7:0]   qos,          
    input  wire [31:0]  address0,
    input  wire [31:0]  address1,
    input  wire [31:0]  address2,
    input  wire [31:0]  address3,
    output reg  [31:0]  mem_address,
    output reg          mem_cmd_valid,
    output reg  [1:0]   mem_cmd_type,  
    input  wire         mem_ack,
    output reg  [3:0]   grant
);

    wire [1:0] qos0 = qos[1:0];
    wire [1:0] qos1 = qos[3:2];
    wire [1:0] qos2 = qos[5:4];
    wire [1:0] qos3 = qos[7:6];
    reg [1:0] current_priority;     
    reg [1:0] round_robin_index;    
    reg [3:0] granted_request;       
    reg [3:0] next_granted_request;  
    reg [1:0] next_rr_index;         
    reg        local_found_prio;
    reg        local_found_rr;
    integer    i;
    integer    idx;
    reg [3:0]  temp_granted;  

    always @* begin
        
        temp_granted     = 4'b0000;
        local_found_prio = 1'b0;
        local_found_rr   = 1'b0;
        next_rr_index    = round_robin_index;

        for (i = 3; i >= 0; i = i - 1) begin
            if (local_found_prio == 1'b0) begin
                case (i)
                    3: if (request[3] && (qos3 == current_priority)) begin
                           temp_granted[3] = 1'b1;
                           local_found_prio = 1'b1;
                       end
                    2: if (request[2] && (qos2 == current_priority)) begin
                           temp_granted[2] = 1'b1;
                           local_found_prio = 1'b1;
                       end
                    1: if (request[1] && (qos1 == current_priority)) begin
                           temp_granted[1] = 1'b1;
                           local_found_prio = 1'b1;
                       end
                    0: if (request[0] && (qos0 == current_priority)) begin
                           temp_granted[0] = 1'b1;
                           local_found_prio = 1'b1;
                       end
                endcase
            end
        end

        if (local_found_prio == 1'b0) begin
            local_found_rr = 1'b0;
            for (i = 0; i < 4; i = i + 1) begin
                idx = (round_robin_index + i) % 4;
                if (local_found_rr == 1'b0) begin
                    case (idx)
                        0: if (request[0]) begin
                               temp_granted[0] = 1'b1;
                               local_found_rr  = 1'b1;
                               next_rr_index   = (idx + 1) % 4;
                           end
                        1: if (request[1]) begin
                               temp_granted[1] = 1'b1;
                               local_found_rr  = 1'b1;
                               next_rr_index   = (idx + 1) % 4;
                           end
                        2: if (request[2]) begin
                               temp_granted[2] = 1'b1;
                               local_found_rr  = 1'b1;
                               next_rr_index   = (idx + 1) % 4;
                           end
                        3: if (request[3]) begin
                               temp_granted[3] = 1'b1;
                               local_found_rr  = 1'b1;
                               next_rr_index   = (idx + 1) % 4;
                           end
                    endcase
                end
            end
        end
        next_granted_request = temp_granted;
    end

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            current_priority  <= 2'b11;  
            round_robin_index <= 2'b00;
            granted_request   <= 4'b0000;

            mem_cmd_valid <= 1'b0;
            mem_cmd_type  <= 2'b00;
            mem_address   <= 32'd0;
            grant         <= 4'b0000;
        end
        else begin
            if ((mem_cmd_valid == 1'b0) || (mem_ack == 1'b1)) begin

                granted_request <= next_granted_request;

                if (next_granted_request == 4'b0000) begin
                    mem_cmd_valid <= 1'b0;
                    grant         <= 4'b0000;
                end
                else begin
                    mem_cmd_valid <= 1'b1;
                    mem_cmd_type  <= 2'b00;
                    grant         <= next_granted_request;

                    case (next_granted_request)
                        4'b0001: mem_address <= address0;
                        4'b0010: mem_address <= address1;
                        4'b0100: mem_address <= address2;
                        4'b1000: mem_address <= address3;
                        default: mem_address <= 32'd0; 
                    endcase
                end

                if (current_priority == 2'b00) begin
                    current_priority <= 2'b11;
                end
                else begin
                    current_priority <= current_priority - 1'b1;
                end

                round_robin_index <= next_rr_index;
            end
        end
    end

endmodule