module fifo_memory
    #(
        parameter p_data_width = 32,    // Memory data word width
        parameter p_addr_width = 16     // Number of memory address bits
    ) (
        input  wire                i_wr_clk,       // Write clock
        input  wire                i_wr_clk_en,    // Write clock enable
        input  wire [p_addr_width-1:0] i_wr_addr,    // Write address
        input  wire [p_data_width-1:0] i_wr_data,    // Write data
        input  wire                i_wr_full,      // Write full flag
        input  wire                i_rd_clk,       // Read clock
        input  wire                i_rd_clk_en,    // Read clock enable
        input  wire [p_addr_width-1:0] i_rd_addr,    // Read address
        output wire [p_data_width-1:0] o_rd_data     // Read data output
    );

    // Calculate the depth of the memory based on the address size
    localparam p_depth = 1 << p_addr_width;

    // Define the memory array with depth p_depth and data width p_data_width
    reg [p_data_width-1:0] r_memory [0:p_depth-1];
    reg [p_data_width-1:0] r_rd_data;  // Register to hold read data

    // Write operation
    always @(posedge i_wr_clk) begin
        if (i_wr_clk_en && !i_wr_full)          // If write is enabled and FIFO is not full
            r_memory[i_wr_addr] <= i_wr_data;   // Write data to memory at specified address
    end

    // Read operation
    always @(posedge i_rd_clk) begin
        if (i_rd_clk_en)                        // If read is enabled
            r_rd_data <= r_memory[i_rd_addr];   // Read data from memory at specified address
    end

    // Assign the read data register to the output
    assign o_rd_data = r_rd_data;

endmodule