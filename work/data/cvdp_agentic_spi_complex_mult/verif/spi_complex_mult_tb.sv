module spi_complex_mult_tb();

    // Parameters
    parameter IN_WIDTH   = 'd16;
    parameter OUT_WIDTH  = 'd32;
    parameter CLK_PERIOD = 'd10;

    // SPI signals
    logic                 rst_async_n;
    logic                 spi_sck;
    logic                 spi_cs_n;
    logic                 spi_mosi;
    logic                 spi_miso;
    logic                 mult_valid_o;
    logic [OUT_WIDTH-1:0] mult_real_o;
    logic [OUT_WIDTH-1:0] mult_imag_o;

    logic                 spi_sck_cg;
    logic                 spi_sck_en;

    // Instantiate DUT
    spi_complex_mult #(
        .IN_WIDTH  (IN_WIDTH ),
        .OUT_WIDTH (OUT_WIDTH)
    ) dut (
        .rst_async_n  (rst_async_n ),
        .spi_sck      (spi_sck_cg  ),
        .spi_cs_n     (spi_cs_n    ),
        .spi_mosi     (spi_mosi    ),
        .spi_miso     (spi_miso    ),
        .mult_valid_o (mult_valid_o),
        .mult_real_o  (mult_real_o ),
        .mult_imag_o  (mult_imag_o )
    );

    // Testbench signals
    parameter CYCLES = 100;
    int       errors = 0;

    logic [7:0] msb_Ar;
    logic [7:0] lsb_Ar;
    logic [7:0] msb_Ai;
    logic [7:0] lsb_Ai;
    logic [7:0] msb_Br;
    logic [7:0] lsb_Br;
    logic [7:0] msb_Bi;
    logic [7:0] lsb_Bi;

    logic signed [IN_WIDTH-1:0] Ar;
    logic signed [IN_WIDTH-1:0] Ai;
    logic signed [IN_WIDTH-1:0] Br;
    logic signed [IN_WIDTH-1:0] Bi;

    logic signed [OUT_WIDTH-1:0] expected_real;
    logic signed [OUT_WIDTH-1:0] expected_imag;

    logic [7:0] byte3_Cr;
    logic [7:0] byte2_Cr;
    logic [7:0] byte1_Cr;
    logic [7:0] byte0_Cr;
    logic [7:0] byte3_Ci;
    logic [7:0] byte2_Ci;
    logic [7:0] byte1_Ci;
    logic [7:0] byte0_Ci;
    
    int received_real;
    int received_imag;

    // Clock generation
    initial begin
        spi_sck    = 0;
        spi_sck_en = 0;
    end
    always begin
        #(CLK_PERIOD / 2) spi_sck = ~spi_sck;
        assign spi_sck_cg = (spi_sck_en) ? spi_sck : 1'b0;
    end

    // Task to send one byte over SPI
    task automatic spi_send_byte(input byte data);
        @(negedge spi_sck);
        spi_cs_n   = 0;
        spi_sck_en = 1;

        for (int i = 7; i >= 0; i--) begin
            spi_mosi = data[i];
            @(negedge spi_sck or negedge spi_cs_n);
        end
        
        #(CLK_PERIOD / 2)
        spi_sck_en = 0;
        spi_cs_n   = 1;
    endtask

    // Task to read one byte from MISO
    task automatic spi_read_byte(output byte data);
        @(negedge spi_sck);
        spi_cs_n   = 0;
        spi_sck_en = 1;
        data = 0;

        for (int i = 7; i >= 0; i--) begin
            @(posedge spi_sck);
            data[i] = spi_miso;
        end
        
        #(CLK_PERIOD)
        spi_sck_en = 0;
        spi_cs_n   = 1;
    endtask

    // Convert a 16-bit signed number from two bytes
    function signed [IN_WIDTH-1:0] combine16(input byte msb, input byte lsb);
        return {msb, lsb};
    endfunction

    // Compute complex multiplication
    task reference_complex_mult(
        input  signed [IN_WIDTH-1:0]  Ar,
        input  signed [IN_WIDTH-1:0]  Ai,
        input  signed [IN_WIDTH-1:0]  Br,
        input  signed [IN_WIDTH-1:0]  Bi,
        output signed [OUT_WIDTH-1:0] Cr,
        output signed [OUT_WIDTH-1:0] Ci
    );
        Cr = (Ar * Br) - (Ai * Bi);
        Ci = (Ar * Bi) + (Ai * Br);
    endtask

    // Main task procedure
    task main();
        // Generate random input values
        msb_Ar = $urandom_range(0, 255);
        lsb_Ar = $urandom_range(0, 255);
        msb_Ai = $urandom_range(0, 255);
        lsb_Ai = $urandom_range(0, 255);
        msb_Br = $urandom_range(0, 255);
        lsb_Br = $urandom_range(0, 255);
        msb_Bi = $urandom_range(0, 255);
        lsb_Bi = $urandom_range(0, 255);

        Ar = combine16(msb_Ar, lsb_Ar);
        Ai = combine16(msb_Ai, lsb_Ai);
        Br = combine16(msb_Br, lsb_Br);
        Bi = combine16(msb_Bi, lsb_Bi);

        reference_complex_mult(Ar, Ai, Br, Bi, expected_real, expected_imag);

        // Apply reset
        spi_cs_n = 1;
        spi_mosi = 0;
        rst_async_n = 0;
        repeat (5) @(posedge spi_sck);
        rst_async_n = 1;

        // Verify signal values after reset
        if (dut.shift_reg  !== 0 ||
            dut.bit_count  !== 0 ||
            dut.data_ready !== 0 ||
            dut.byte_count !== 0 ||
            spi_miso       !== 0 ||
            mult_real_o    !== 0 ||
            mult_imag_o    !== 0 ||
            mult_valid_o   !== 0    ) begin
            $error(1, "[FAIL] Signals not properly reset.");
            errors += 1;
        end

        $display("[INFO] Reset completed. Starting SPI transaction...");

        // First transaction — send operands
        spi_send_byte(msb_Ar);
        spi_send_byte(lsb_Ar);
        spi_send_byte(msb_Ai);
        spi_send_byte(lsb_Ai);
        spi_send_byte(msb_Br);
        spi_send_byte(lsb_Br);
        spi_send_byte(msb_Bi);
        spi_send_byte(lsb_Bi);

        // Check the parallel outputs (mult_real_o and mult_imag_o)
        if (mult_real_o !== expected_real || mult_imag_o !== expected_imag) begin
            $display("[FAIL] Parallel outputs do not match expected values:");
            $display("       mult_real_o = 0x%08X, expected = 0x%08X", mult_real_o, expected_real);
            $display("       mult_imag_o = 0x%08X, expected = 0x%08X", mult_imag_o, expected_imag);
            $error(1, "Parallel output mismatch.");
            errors += 1;
        end else begin
            $display("[PASS] Parallel outputs match expected values.");
        end

        // Second transaction — read result from MISO
        spi_read_byte(byte3_Cr);
        spi_read_byte(byte2_Cr);
        spi_read_byte(byte1_Cr);
        spi_read_byte(byte0_Cr);
        spi_read_byte(byte3_Ci);
        spi_read_byte(byte2_Ci);
        spi_read_byte(byte1_Ci);
        spi_read_byte(byte0_Ci);

        @(negedge spi_sck);
        received_real = {byte3_Cr, byte2_Cr, byte1_Cr, byte0_Cr};
        received_imag = {byte3_Ci, byte2_Ci, byte1_Ci, byte0_Ci};

        $display("[INFO] Result received from spi_miso:");
        $display("  Cr = 0x%08X", received_real);
        $display("  Ci = 0x%08X", received_imag);

        // Validate the MISO results
        if (received_real !== expected_real) begin
            $display("[FAIL] Real part mismatch: expected 0x%08X, got 0x%08X", expected_real, received_real);
            $error(1, "Test failed due to Cr mismatch.");
            errors += 1;
        end else begin
            $display("[PASS] Real part matches expected result.");
        end

        if (received_imag !== expected_imag) begin
            $display("[FAIL] Imaginary part mismatch: expected 0x%08X, got 0x%08X", expected_imag, received_imag);
            $error(1, "Test failed due to Ci mismatch.");
            errors += 1;
        end else begin
            $display("[PASS] Imaginary part matches expected result.");
        end
    endtask

    initial begin
        repeat(CYCLES) main();
        if (errors == 0) begin
            $display("Testbench PASSED all tests!!!");
        end else begin
            $display("Testbench finished with %d errors!!!", errors);
        end
        $finish;
    end

    initial begin
        $dumpfile("waveform.vcd");
        $dumpvars(0, spi_complex_mult_tb);
    end
endmodule