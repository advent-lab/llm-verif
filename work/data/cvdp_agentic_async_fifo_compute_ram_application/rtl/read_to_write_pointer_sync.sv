module read_to_write_pointer_sync 
    #(
        parameter p_addr_width = 16  // Parameter to define the address width of the FIFO
    )(
        input  wire              i_wr_clk,           // Write clock
        input  wire              i_wr_rst_n,         // Write reset (active low)
        input  wire [p_addr_width:0] i_rd_grey_addr, // Gray-coded read address from the read clock domain
        output reg  [p_addr_width:0] o_rd_ptr_sync   // Synchronized read pointer in the write clock domain
    );

    // Internal register to hold the intermediate synchronized read pointer
    reg [p_addr_width:0] r_rd_ptr_ff;

    // Always block for synchronizing the read pointer to the write clock domain
    always @(posedge i_wr_clk or negedge i_wr_rst_n) 
    begin
        if (!i_wr_rst_n) begin
            // If reset is asserted (active low), reset the synchronized pointers to 0
            o_rd_ptr_sync <= {p_addr_width+1{1'b0}};
            r_rd_ptr_ff <= {p_addr_width+1{1'b0}};
        end else begin
            // If reset is not asserted, synchronize the read pointer to the write clock domain
            r_rd_ptr_ff <= i_rd_grey_addr;  // First stage of synchronization
            o_rd_ptr_sync <= r_rd_ptr_ff;   // Second stage of synchronization
        end
    end

endmodule