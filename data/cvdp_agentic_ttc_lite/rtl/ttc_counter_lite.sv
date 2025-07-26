`timescale 1ns / 1ps
module ttc_counter_lite (
    input wire          clk,                // Clock signal
    input wire          reset,              // Reset signal
    input wire [3:0]    axi_addr,           // AXI address for read/write
    input wire [31:0]   axi_wdata,          // AXI write data
    input wire          axi_write_en,       // AXI write enable
    input wire          axi_read_en,        // AXI read enable
    output reg [31:0]   axi_rdata,          // AXI read data
    output reg          interrupt           // Interrupt signal
);

    // Timer registers
    reg [15:0] count;                       // Counter register
    reg [15:0] match_value;                 // Match value for interval mode
    reg [15:0] reload_value;                // Reload value in interval mode
    reg        enable;                      // Timer enable flag
    reg        interval_mode;               // Interval mode enable flag
    reg        interrupt_enable;            // Interrupt enable flag
    reg [3:0]  prescaler;                   // Prescaler value
    reg [3:0]  prescaler_count;             // Prescaler counter

    // Address map
    localparam ADDR_COUNT        = 4'b0000; // Counter register (read only)
    localparam ADDR_MATCH_VALUE  = 4'b0001; // Match value register
    localparam ADDR_RELOAD_VALUE = 4'b0010; // Reload value register
    localparam ADDR_CONTROL      = 4'b0011; // Control register
    localparam ADDR_STATUS       = 4'b0100; // Status register
    localparam ADDR_PRESCALER    = 4'b0101; // Prescaler register

    // Interrupt flag
    reg match_flag;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            prescaler_count <= 4'b0;
		count    <= 16'b0;   
    end else if (enable) begin
            if (prescaler_count == prescaler) begin
                prescaler_count <= 4'b0;
                if (interval_mode && match_flag) begin
                    count <= reload_value;
                end 
                else if (count != match_value) begin
                    count <= count + 16'b1;  
                end
            end else begin
                prescaler_count <= prescaler_count + 4'b1; 
            end
        end
    end

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            match_flag <= 1'b0; 
        end else begin
            match_flag <= (count == match_value); 
        end
    end

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            interrupt <= 1'b0; 
        end else if (match_flag && interrupt_enable) begin
            interrupt <= 1'b1; 
        end else if (axi_write_en && axi_addr == ADDR_STATUS) begin
            interrupt <= 1'b0; 
        end
    end

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            match_value      <= 16'b0; 
            reload_value     <= 16'b0; 
            enable           <= 1'b0; 
            interval_mode    <= 1'b0; 
            interrupt_enable <= 1'b0; 
            prescaler        <= 4'b0; 
        end else if (axi_write_en) begin
            case (axi_addr)
                ADDR_MATCH_VALUE:  match_value      <= axi_wdata[15:0]; 
                ADDR_RELOAD_VALUE: reload_value     <= axi_wdata[15:0]; 
                ADDR_CONTROL: begin
                    enable           <= axi_wdata[0]; 
                    interval_mode    <= axi_wdata[1]; 
                    interrupt_enable <= axi_wdata[2]; 
                end
                ADDR_PRESCALER: prescaler <= axi_wdata[3:0]; 
                default: ; 
            endcase
        end
    end

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            axi_rdata <= 32'b0; 
        end else if (axi_read_en) begin
            case (axi_addr)
                ADDR_COUNT:        axi_rdata <= {16'b0, count};       
                ADDR_MATCH_VALUE:  axi_rdata <= {16'b0, match_value}; 
                ADDR_RELOAD_VALUE: axi_rdata <= {16'b0, reload_value}; 
                ADDR_CONTROL:      axi_rdata <= {29'b0, interrupt_enable, interval_mode, enable}; 
                ADDR_STATUS:       axi_rdata <= {31'b0, interrupt};   
                ADDR_PRESCALER:    axi_rdata <= {28'b0, prescaler};  
                default:           axi_rdata <= 32'b0;               
            endcase
        end
    end

endmodule