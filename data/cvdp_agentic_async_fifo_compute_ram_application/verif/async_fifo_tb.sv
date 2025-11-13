`timescale 1ns/1ps

module async_fifo_tb;

    parameter p_data_width = 32;
    parameter p_addr_width = 4;  // Small FIFO for testing

    // Write domain signals
    logic             wr_clk;
    logic             wr_rst_n;
    logic             wr_en;
    logic [p_data_width-1:0] wr_data;
    wire              fifo_full;

    // Read domain signals
    logic             rd_clk;
    logic             rd_rst_n;
    logic             rd_en;
    wire [p_data_width-1:0] rd_data;
    wire              fifo_empty;

    // DUT instantiation
    async_fifo #(
        .p_data_width(p_data_width),
        .p_addr_width(p_addr_width)
    ) dut (
        .i_wr_clk(wr_clk),
        .i_wr_rst_n(wr_rst_n),
        .i_wr_en(wr_en),
        .i_wr_data(wr_data),
        .o_fifo_full(fifo_full),
        .i_rd_clk(rd_clk),
        .i_rd_rst_n(rd_rst_n),
        .i_rd_en(rd_en),
        .o_rd_data(rd_data),
        .o_fifo_empty(fifo_empty)
    );

    // Clock generation - different frequencies for async testing
    initial begin
        wr_clk = 0;
        forever #5 wr_clk = ~wr_clk;  // 100MHz
    end

    initial begin
        rd_clk = 0;
        forever #7 rd_clk = ~rd_clk;  // ~71MHz
    end

    // Test sequence
    initial begin
        // Initialize
        wr_rst_n = 0;
        rd_rst_n = 0;
        wr_en = 0;
        rd_en = 0;
        wr_data = 0;

        // Release resets
        #20;
        wr_rst_n = 1;
        rd_rst_n = 1;
        #20;

        // Write some data
        repeat(10) begin
            @(posedge wr_clk);
            if (!fifo_full) begin
                wr_en = 1;
                wr_data = $random;
            end else begin
                wr_en = 0;
            end
        end

        @(posedge wr_clk);
        wr_en = 0;

        // Read some data
        #50;
        repeat(10) begin
            @(posedge rd_clk);
            if (!fifo_empty) begin
                rd_en = 1;
            end else begin
                rd_en = 0;
            end
        end

        @(posedge rd_clk);
        rd_en = 0;

        // Additional writes and reads
        repeat(5) begin
            @(posedge wr_clk);
            wr_en = !fifo_full;
            wr_data = $random;
        end

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t wr_en=%b wr_data=%h full=%b rd_en=%b rd_data=%h empty=%b",
                 $time, wr_en, wr_data, fifo_full, rd_en, rd_data, fifo_empty);
    end

endmodule
