module wptr_full 
    #(
        parameter p_addr_width = 16  // Parameter to define the address width of the FIFO
    )(
        input  wire                     i_wr_clk,         // Write clock
        input  wire                     i_wr_rst_n,       // Write reset (active low)
        input  wire                     i_wr_en,          // Write enable signal
        input  wire [p_addr_width  :0]  i_rd_ptr_sync,    // Synchronized read pointer from the read clock domain
        output reg                      o_fifo_full,      // Output flag indicating if the FIFO is full
        output wire [p_addr_width-1:0]  o_wr_bin_addr,    // Output binary write address
        output reg  [p_addr_width  :0]  o_wr_grey_addr    // Output Gray-coded write address
    );

    // Internal registers and wires
    reg  [p_addr_width:0] r_wr_bin_addr_pointer;  // Register to store the current binary write address
    wire [p_addr_width:0] w_wr_next_bin_addr_pointer; // Wire for the next binary write address
    wire [p_addr_width:0] w_wr_next_grey_addr_pointer; // Wire for the next Gray-coded write address
    wire                  w_wr_full;             // Wire indicating if the FIFO is full

    // Always block for updating the write address pointers
    // GRAYSTYLE2 pointer update mechanism
    always @(posedge i_wr_clk or negedge i_wr_rst_n) begin
        if (!i_wr_rst_n) begin
            // Reset the write address pointers to 0 on reset
            r_wr_bin_addr_pointer <= {p_addr_width{1'b0}};
            o_wr_grey_addr <= {p_addr_width{1'b0}};
        end else begin
            // Update the write address pointers on each clock edge
            r_wr_bin_addr_pointer <= w_wr_next_bin_addr_pointer;
            o_wr_grey_addr <= w_wr_next_grey_addr_pointer;
        end
    end

    // Assign the binary write address for addressing the memory
    assign o_wr_bin_addr = r_wr_bin_addr_pointer[p_addr_width-1:0];

    // Calculate the next binary write address, only increment if write enable is active and FIFO is not full
    assign w_wr_next_bin_addr_pointer  = r_wr_bin_addr_pointer + (i_wr_en & ~o_fifo_full);

    // Convert the next binary write address to Gray code
    assign w_wr_next_grey_addr_pointer = (w_wr_next_bin_addr_pointer >> 1) ^ w_wr_next_bin_addr_pointer;

    // Check if the FIFO is full by comparing the next Gray-coded write address with the synchronized read pointer
    // FIFO is full if the next write address matches the read pointer with the MSB inverted
    assign w_wr_full = (w_wr_next_grey_addr_pointer == {~i_rd_ptr_sync[p_addr_width:p_addr_width-1], i_rd_ptr_sync[p_addr_width-2:0]});

    // Always block for updating the FIFO full flag
    always @(posedge i_wr_clk or negedge i_wr_rst_n) begin
        if (!i_wr_rst_n) begin
            // Reset the FIFO full flag to 0 on reset
            o_fifo_full <= 1'b0;
        end else begin
            // Update the FIFO full flag based on the calculated full condition
            o_fifo_full <= w_wr_full;
        end
    end

endmodule