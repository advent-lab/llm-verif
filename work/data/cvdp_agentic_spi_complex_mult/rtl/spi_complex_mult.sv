module spi_complex_mult #(
    parameter IN_WIDTH  = 'd16, // Parameter defining the input width
    parameter OUT_WIDTH = 'd32  // Parameter defining the output width
) (
    input  logic                 rst_async_n,  // Asynchronous reset signal, active low
    input  logic                 spi_sck,      // SPI clock signal
    input  logic                 spi_cs_n,     // SPI chip select signal, active low
    input  logic                 spi_mosi,     // SPI master out, slave in signal (data from master to slave)
    output logic                 spi_miso,     // SPI master in, slave out signal (data from slave to master)
    output logic                 mult_valid_o, // Indicates that the complex multiplication result is valid
    output logic [OUT_WIDTH-1:0] mult_real_o,  // Real part of the complex multiplication result
    output logic [OUT_WIDTH-1:0] mult_imag_o   // Imaginary part of the complex multiplication result
);

    // Internal signals
    logic signed [IN_WIDTH-1:0] Ar;
    logic signed [IN_WIDTH-1:0] Ai;
    logic signed [IN_WIDTH-1:0] Br;
    logic signed [IN_WIDTH-1:0] Bi;

    logic       data_ready;
    logic       spi_ready;
    logic       mult_ready;
    logic [7:0] shift_reg;
    logic [2:0] bit_count;
    logic [2:0] byte_count;

    logic signed [OUT_WIDTH-1:0] mult_real;
    logic signed [OUT_WIDTH-1:0] mult_imag;

    // Shift register to store incoming SPI MOSI data
    always_ff @(negedge spi_sck or negedge rst_async_n or negedge spi_cs_n) begin
        if (!rst_async_n) begin
            shift_reg <= 'd0;
            bit_count <= 'd0;
            data_ready <= 'd0;
        end else begin
            if (!spi_cs_n && !data_ready) begin
                shift_reg <= {shift_reg[6:0], spi_mosi};
                bit_count <= bit_count + 1'b1;
            end

            if (bit_count == 3'd7) begin
                data_ready <= 1'b1;
            end else begin
                data_ready <= 1'b0;
            end
        end
    end

    // Store data in the operands
    always_ff @(posedge spi_sck or negedge rst_async_n) begin
        if (!rst_async_n) begin
            byte_count <= 'd0;
        end else if (data_ready) begin
            byte_count <= byte_count + 1'b1;

            if (byte_count == 'd0) begin
                Ar[15:8] <= shift_reg;
                spi_ready <= 1'b0;
            end else if (byte_count == 'd1) begin
                Ar[7:0] <= shift_reg;
            end else if (byte_count == 'd2) begin
                Ai[15:8] <= shift_reg;
            end else if (byte_count == 'd3) begin
                Ai[7:0] <= shift_reg;
            end else if (byte_count == 'd4) begin
                Br[15:8] <= shift_reg;
            end else if (byte_count == 'd5) begin
                Br[7:0] <= shift_reg;
            end else if (byte_count == 'd6) begin
                Bi[15:8] <= shift_reg;
            end else if (byte_count == 'd7) begin
                Bi[7:0] <= shift_reg;
                spi_ready <= 1'b1;
            end
        end
    end

    // Complex multiplication
    always_ff @(negedge spi_sck or negedge rst_async_n) begin
        if (!rst_async_n) begin
            mult_real  <= 'd0;
            mult_imag  <= 'd0;
            mult_ready <= 'd0;
        end else if (spi_ready) begin
            mult_real  <= (Ar * Br) - (Ai * Bi);
            mult_imag  <= (Ar * Bi) + (Ai * Br);
            mult_ready <= 1'b1;
        end
    end

    // Logic for transmitting the data result via the SPI MISO line
    always_ff @(negedge spi_sck or negedge rst_async_n or negedge spi_cs_n) begin
        if (!rst_async_n) begin
            spi_miso <= 'd0;
        end else if (!spi_cs_n) begin
            if (byte_count == 'd0) begin
                spi_miso <= mult_real[32 - (bit_count + 1)];  
            end else if (byte_count == 'd1) begin
                spi_miso <= mult_real[24 - (bit_count + 1)];
            end else if (byte_count == 'd2) begin
                spi_miso <= mult_real[16 - (bit_count + 1)];
            end else if (byte_count == 'd3) begin
                spi_miso <= mult_real[8 - (bit_count + 1)];
            end else if (byte_count == 'd4) begin
                spi_miso <= mult_imag[32 - (bit_count + 1)];
            end else if (byte_count == 'd5) begin
                spi_miso <= mult_imag[24 - (bit_count + 1)];
            end else if (byte_count == 'd6) begin
                spi_miso <= mult_imag[16 - (bit_count + 1)];
            end else if (byte_count == 'd7) begin
                spi_miso <= mult_imag[8 - (bit_count + 1)];
            end
        end
    end

    // Drive the output interface signals with multiplication results
    always_comb begin
        mult_valid_o = mult_ready;
        mult_real_o  = mult_real;
        mult_imag_o  = mult_imag;
    end

endmodule