module spi_master #(
    parameter OP_WIDTH     = 'd16, // Operands data width in bits
    parameter RESULT_WIDTH = 'd32, // Results data width in bits
    parameter CLK_DIV      = 'd2   // Clock divider for SPI clock generation
)(
    input  logic                    clk,          // System clock
    input  logic                    rst_async_n,  // Asynchronous active-low reset
    input  logic [OP_WIDTH-1:0]     Ar,           // Real part of data A
    input  logic [OP_WIDTH-1:0]     Ai,           // Imaginary part of data A
    input  logic [OP_WIDTH-1:0]     Br,           // Real part of data B
    input  logic [OP_WIDTH-1:0]     Bi,           // Imaginary part of data B
    input  logic                    start,        // Start signal to initiate transmission
    input  logic [1:0]              slave_select, // Seleção de slave (00: none; 01: slave 0; 10: slave 1; 11: slave 2)
    output logic [RESULT_WIDTH-1:0] Cr,           // Real part of data C (Result)
    output logic [RESULT_WIDTH-1:0] Ci,           // Imaginary part of data C (Result)
    // SPI Interface
    output logic       spi_rst_async_n, // SPI asynchronous active-low reset
    output logic       spi_sck,         // SPI clock
    output logic [2:0] spi_cs_n,        // Chip select signals for 3 slaves (active low)
    output logic       spi_mosi,        // Master Out Slave In (data line to slaves)
    input  logic       spi_miso         // Master In Slave Out (data line from slaves)
);
    // Define FSM states 
    typedef enum logic [2:0] {
        IDLE,
        TRANSFER,
        DONE,
        UPDATE_REG
    } state_t;

    state_t state;

    // Internal variables
    localparam BYTE_WIDTH = 'd8;

    logic [BYTE_WIDTH-1:0] shift_reg;   // Shift register for store a byte
    logic [2:0]            bit_cnt;     // Bit counter
    logic [2:0]            byte_cnt;    // Byte counter
    logic [CLK_DIV-1:0]    clk_div_cnt; // Clock divider counter
    logic                  spi_clk_ff;  // SPI clock generation
    logic                  spi_clk_en;  // SPI clock enable

    // Sequential logic of FSM
    always_ff @(posedge clk or negedge rst_async_n) begin
        if (!rst_async_n) begin
            state           <= IDLE;
            spi_clk_ff      <= 1'b0;
            spi_cs_n        <= 3'b111; // Deactivate all slaves
            spi_mosi        <= 1'b0;
            bit_cnt         <= 'd0;
            byte_cnt        <= 'd0;
            clk_div_cnt     <= 'd0;
            spi_clk_en      <= 1'b0;
            shift_reg       <= 'd0;
            Cr              <= 'd0;
            Ci              <= 'd0;
        end else begin
            case (state)
                IDLE: begin
                    if (start) begin
                        state <= TRANSFER;
                        case (slave_select)
                            2'b00: spi_cs_n <= 3'b111; // Activate all slaves
                            2'b01: spi_cs_n <= 3'b110; // Activate slave 0
                            2'b10: spi_cs_n <= 3'b101; // Activate slave 1
                            2'b11: spi_cs_n <= 3'b011; // Activate slave 2                            
                        endcase
                        shift_reg   <= {Ar[14:8], 1'b0}; // Load data to shift registers
                        spi_mosi    <= Ar[15];
                        bit_cnt     <= BYTE_WIDTH - 1'b1;
                        byte_cnt    <= 'd0;
                        clk_div_cnt <= 'd0;
                        spi_clk_en  <= 1'b1;
                    end
                end

                TRANSFER: begin
                    if (clk_div_cnt == CLK_DIV - 1) begin
                        clk_div_cnt <= 'd0;
                        spi_clk_ff  <= ~spi_clk_ff; // Toggle SPI clock

                        if (spi_clk_ff == 1'b0) begin
                            // On rising edge, sample MISO
                            case (byte_cnt)
                                8'd0: Cr[31:24] <= {Cr[30:24], spi_miso};
                                8'd1: Cr[23:16] <= {Cr[22:16], spi_miso};
                                8'd2: Cr[15:8]  <= {Cr[14:8] , spi_miso};
                                8'd3: Cr[7:0]   <= {Cr[6:0]  , spi_miso};
                                8'd4: Ci[31:24] <= {Ci[30:24], spi_miso};
                                8'd5: Ci[23:16] <= {Ci[22:16], spi_miso};
                                8'd6: Ci[15:8]  <= {Ci[14:8] , spi_miso};
                                8'd7: Ci[7:0]   <= {Ci[6:0]  , spi_miso};
                            endcase
                        end else begin
                            // On falling edge, shift out MOSI
                            spi_mosi  <= shift_reg[BYTE_WIDTH-1];           // Send MSB of first slave's data
                            shift_reg <= {shift_reg[BYTE_WIDTH-2:0], 1'b0}; // Shift left
                            if (bit_cnt == 'd0) begin
                                state      <= DONE;
                                spi_clk_en <= 1'b0;
                            end else begin
                                bit_cnt <= bit_cnt - 1'b1;
                            end
                        end
                    end else begin
                        clk_div_cnt <= clk_div_cnt + 1'b1;
                    end
                end

                DONE: begin
                    spi_cs_n <= 3'b111; // Deactivate all slaves
                    if (byte_cnt == 'd7) begin
                        state <= IDLE;
                    end else begin
                        state <= UPDATE_REG;
                    end
                end

                UPDATE_REG: begin
                    state       <= TRANSFER;
                    byte_cnt    <= byte_cnt + 1'b1;
                    bit_cnt     <= BYTE_WIDTH - 1'b1;
                    clk_div_cnt <= 'd0;
                    spi_clk_en  <= 1'b1;
                    case (slave_select)
                        2'b00: spi_cs_n <= 3'b111; // Activate all slaves
                        2'b01: spi_cs_n <= 3'b110; // Activate slave 0
                        2'b10: spi_cs_n <= 3'b101; // Activate slave 1
                        2'b11: spi_cs_n <= 3'b011; // Activate slave 2                            
                    endcase
                    case (byte_cnt)
                        8'd0: begin
                            shift_reg <= {Ar[6:0], 1'b0};
                            spi_mosi  <= Ar[7];
                        end
                        8'd1: begin
                            shift_reg <= {Ai[14:8], 1'b0};
                            spi_mosi  <= Ai[15];
                        end
                        8'd2: begin
                            shift_reg <= {Ai[6:0], 1'b0};
                            spi_mosi  <= Ai[7];
                        end
                        8'd3: begin
                            shift_reg <= {Br[14:8], 1'b0};
                            spi_mosi  <= Br[15];
                        end
                        8'd4: begin
                            shift_reg <= {Br[6:0], 1'b0};
                            spi_mosi  <= Br[7];
                        end
                        8'd5: begin
                            shift_reg <= {Bi[14:8], 1'b0};
                            spi_mosi  <= Bi[15];
                        end
                        8'd6: begin
                            shift_reg <= {Bi[6:0], 1'b0};
                            spi_mosi  <= Bi[7];
                        end
                    endcase
                end
            endcase
        end
    end

    // SPI clock gating
    assign spi_sck = (spi_clk_en) ? spi_clk_ff : 1'b0;

    // Drive the asynchronous active-low reset
    assign spi_rst_async_n = rst_async_n;

endmodule