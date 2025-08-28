module spi_top #(
    parameter OP_WIDTH     = 16, // Operands data width in bits
    parameter RESULT_WIDTH = 32, // Results data width in bits
    parameter CLK_DIV      = 2   // Clock divider for SPI clock generation
)(
    input  logic                    clk,          // System clock
    input  logic                    rst_async_n,  // Asynchronous active-low reset
    // Control Interface
    input  logic                    start,        // Start signal to initiate transmission
    input  logic [1:0]              slave_select, // Slave selection (01: slave 0; 10: slave 1; 11: slave 2)
    // Data Inputs
    input  logic [OP_WIDTH-1:0]     Ar,           // Real part of operand A
    input  logic [OP_WIDTH-1:0]     Ai,           // Imaginary part of operand A
    input  logic [OP_WIDTH-1:0]     Br,           // Real part of operand B
    input  logic [OP_WIDTH-1:0]     Bi,           // Imaginary part of operand B
    // Data Outputs
    output logic [RESULT_WIDTH-1:0] Cr,           // Real part of result
    output logic [RESULT_WIDTH-1:0] Ci            // Imaginary part of result
);

    // SPI Master Interface Signals
    logic       spi_rst_async_n;
    logic       spi_sck;
    logic [2:0] spi_cs_n;
    logic       spi_mosi;
    logic       spi_miso;
    
    // Individual slave MISO signals
    logic slave0_miso;
    logic slave1_miso;
    logic slave2_miso;
    
    // SPI Master
    spi_master #(
        .OP_WIDTH     (OP_WIDTH     ),
        .RESULT_WIDTH (RESULT_WIDTH ),
        .CLK_DIV      (CLK_DIV      )
    ) u_spi_master (
        .clk             (clk            ),
        .rst_async_n     (rst_async_n    ),
        .Ar              (Ar             ),
        .Ai              (Ai             ),
        .Br              (Br             ),
        .Bi              (Bi             ),
        .start           (start          ),
        .slave_select    (slave_select   ),
        .Cr              (Cr             ),
        .Ci              (Ci             ),
        .spi_rst_async_n (spi_rst_async_n),
        .spi_sck         (spi_sck        ),
        .spi_cs_n        (spi_cs_n       ),
        .spi_mosi        (spi_mosi       ),
        .spi_miso        (spi_miso       )
    );
    
    // SPI Slave 0
    spi_complex_mult #(
        .IN_WIDTH  (OP_WIDTH    ),
        .OUT_WIDTH (RESULT_WIDTH)
    ) uu_spi_slave_0 (
        .rst_async_n (spi_rst_async_n),
        .spi_sck     (spi_sck        ),
        .spi_cs_n    (spi_cs_n[0]    ),
        .spi_mosi    (spi_mosi       ),
        .spi_miso    (slave0_miso    )
    );

    // SPI Slave 1
    spi_complex_mult #(
        .IN_WIDTH  (OP_WIDTH    ),
        .OUT_WIDTH (RESULT_WIDTH)
    ) uu_spi_slave_1 (
        .rst_async_n (spi_rst_async_n),
        .spi_sck     (spi_sck        ),
        .spi_cs_n    (spi_cs_n[1]    ),
        .spi_mosi    (spi_mosi       ),
        .spi_miso    (slave1_miso    )
    );

    // SPI Slave 2
    spi_complex_mult #(
        .IN_WIDTH  (OP_WIDTH    ),
        .OUT_WIDTH (RESULT_WIDTH)
    ) uu_spi_slave_2 (
        .rst_async_n (spi_rst_async_n),
        .spi_sck     (spi_sck        ),
        .spi_cs_n    (spi_cs_n[2]    ),
        .spi_mosi    (spi_mosi       ),
        .spi_miso    (slave2_miso    )
    );
    
    // MISO multiplexer - only selected slave drives the line
    always_comb begin
        if (!spi_cs_n[0]) begin
            spi_miso = slave0_miso;
        end else if (!spi_cs_n[1]) begin
            spi_miso = slave1_miso;
        end else if (!spi_cs_n[2]) begin
            spi_miso = slave2_miso;
        end else begin
            spi_miso = 1'bz; // High impedance when no slave selected
        end
    end

endmodule