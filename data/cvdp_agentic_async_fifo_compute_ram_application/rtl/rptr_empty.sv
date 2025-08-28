module rptr_empty 
    #(
        parameter p_addr_width = 16  // Parameter to define the address width of the FIFO
    )(
        input  wire                i_rd_clk,         // Read clock
        input  wire                i_rd_rst_n,       // Read reset (active low)
        input  wire                i_rd_en,          // Read enable signal
        input  wire [p_addr_width  :0] i_wr_ptr_sync, // Synchronized write pointer from the write clock domain
        output reg                 o_fifo_empty,     // Output flag indicating if the FIFO is empty
        output wire [p_addr_width-1:0] o_rd_bin_addr, // Output binary read address
        output reg  [p_addr_width  :0] o_rd_grey_addr // Output Gray-coded read address
    );

    // Internal registers and wires
    reg  [p_addr_width:0] r_rd_bin_addr_pointer; // Register to store the current binary read address
    wire [p_addr_width:0] w_rd_next_grey_addr_pointer; // Wire for the next Gray-coded read address
    wire [p_addr_width:0] w_rd_next_bin_addr_pointer; // Wire for the next binary read address
    wire                  w_rd_empty;             // Wire indicating if the FIFO is empty

    //-------------------
    // GRAYSTYLE2 pointer
    //-------------------
    always @(posedge i_rd_clk or negedge i_rd_rst_n) 
    begin
        if (!i_rd_rst_n) begin
            // Reset the read address pointers to 0 on reset
            r_rd_bin_addr_pointer <= {p_addr_width+1{1'b0}};
            o_rd_grey_addr <= {p_addr_width+1{1'b0}};
        end else begin
            // Update the read address pointers on each clock edge
            r_rd_bin_addr_pointer <= w_rd_next_bin_addr_pointer;
            o_rd_grey_addr <= w_rd_next_grey_addr_pointer;
        end
    end
    
    // Memory read-address pointer (binary addressing for memory access)
    assign o_rd_bin_addr = r_rd_bin_addr_pointer[p_addr_width-1:0];

    // Calculate the next binary read address, increment only if read enable is active and FIFO is not empty
    assign w_rd_next_bin_addr_pointer = r_rd_bin_addr_pointer + (i_rd_en & ~o_fifo_empty);

    // Convert the next binary read address to Gray code
    assign w_rd_next_grey_addr_pointer = (w_rd_next_bin_addr_pointer >> 1) ^ w_rd_next_bin_addr_pointer;

    //---------------------------------------------------------------
    // FIFO is empty when the next Gray-coded read address matches the synchronized write pointer or on reset
    //---------------------------------------------------------------
    assign w_rd_empty = (w_rd_next_grey_addr_pointer == i_wr_ptr_sync);

    // Always block for updating the FIFO empty flag
    always @(posedge i_rd_clk or negedge i_rd_rst_n) begin
        if (!i_rd_rst_n) begin
            // Reset the FIFO empty flag to 1 on reset
            o_fifo_empty <= 1'b1;
        end else begin
            // Update the FIFO empty flag based on the calculated empty condition
            o_fifo_empty <= w_rd_empty;
        end
    end

endmodule