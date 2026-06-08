module async_fifo
    #(
        parameter p_data_width = 32,   // Parameter to define the width of the data
        parameter p_addr_width = 16    // Parameter to define the width of the address
    )(
        input  wire             i_wr_clk,           // Write clock
        input  wire             i_wr_rst_n,         // Write reset (active low)
        input  wire             i_wr_en,            // Write enable
        input  wire [p_data_width-1:0] i_wr_data,   // Data to be written to the FIFO
        output wire             o_fifo_full,        // FIFO full flag
        input  wire             i_rd_clk,           // Read clock
        input  wire             i_rd_rst_n,         // Read reset (active low)
        input  wire             i_rd_en,            // Read enable
        output wire [p_data_width-1:0] o_rd_data,   // Data read from the FIFO
        output wire             o_fifo_empty        // FIFO empty flag
    );

    // Internal signals for address synchronization
    wire [p_addr_width-1:0] w_wr_bin_addr, w_rd_bin_addr; // Binary addresses for write and read
    wire [p_addr_width  :0] w_wr_grey_addr, w_rd_grey_addr; // Gray-coded addresses for write and read
    wire [p_addr_width  :0] w_rd_ptr_sync, w_wr_ptr_sync;   // Synchronized pointers

    // Synchronize the read pointer from read domain to write domain
    read_to_write_pointer_sync
    #(p_addr_width)
    read_to_write_pointer_sync_inst (
        .o_rd_ptr_sync (w_rd_ptr_sync),    // Output synchronized read pointer
        .i_rd_grey_addr (w_rd_grey_addr),  // Input Gray-coded read address
        .i_wr_clk     (i_wr_clk),          // Write clock
        .i_wr_rst_n   (i_wr_rst_n)         // Write reset (active low)
    );

    // Synchronize the write pointer from write domain to read domain
    write_to_read_pointer_sync
    #(p_addr_width)
    write_to_read_pointer_sync_inst (
        .i_rd_clk     (i_rd_clk),          // Read clock
        .i_rd_rst_n   (i_rd_rst_n),        // Read reset (active low)
        .i_wr_grey_addr (w_wr_grey_addr),  // Input Gray-coded write address
        .o_wr_ptr_sync (w_wr_ptr_sync)     // Output synchronized write pointer
    );

    // Handle the write requests and manage the write pointer
    wptr_full
    #(p_addr_width)
    wptr_full_inst (
        .i_wr_clk     (i_wr_clk),          // Write clock
        .i_wr_rst_n   (i_wr_rst_n),        // Write reset (active low)
        .i_wr_en     (i_wr_en),            // Write enable
        .i_rd_ptr_sync (w_rd_ptr_sync),    // Synchronized read pointer
        .o_fifo_full    (o_fifo_full),     // FIFO full flag
        .o_wr_bin_addr    (w_wr_bin_addr), // Binary write address
        .o_wr_grey_addr     (w_wr_grey_addr) // Gray-coded write address
    );

    // Dual-port RAM for FIFO memory
    fifo_memory
    #(p_data_width, p_addr_width)
    fifo_memory_inst (
        .i_wr_clk   (i_wr_clk),            // Write clock
        .i_wr_clk_en (i_wr_en),            // Write clock enable
        .i_wr_addr  (w_wr_bin_addr),       // Write address
        .i_wr_data  (i_wr_data),           // Write data
        .i_wr_full  (o_fifo_full),         // FIFO full flag (write side)
        .i_rd_clk   (i_rd_clk),            // Read clock
        .i_rd_clk_en (i_rd_en),            // Read clock enable
        .i_rd_addr  (w_rd_bin_addr),       // Read address
        .o_rd_data  (o_rd_data)            // Read data output
    );

    // Handle the read requests and manage the read pointer
    rptr_empty
    #(p_addr_width)
    rptr_empty_inst (
        .i_rd_clk     (i_rd_clk),          // Read clock
        .i_rd_rst_n   (i_rd_rst_n),        // Read reset (active low)
        .i_rd_en     (i_rd_en),            // Read enable
        .i_wr_ptr_sync (w_wr_ptr_sync),    // Synchronized write pointer
        .o_fifo_empty   (o_fifo_empty),    // FIFO empty flag
        .o_rd_bin_addr    (w_rd_bin_addr), // Binary read address
        .o_rd_grey_addr     (w_rd_grey_addr) // Gray-coded read address
    );

endmodule