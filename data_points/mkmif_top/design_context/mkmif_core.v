module mkmif_core(
                  input wire           clk,
                  input wire           reset_n,

                  output wire          spi_sclk,
                  output wire          spi_cs_n,
                  input wire           spi_do,
                  output wire          spi_di,

                  input wire           read_op,
                  input wire           write_op,
                  input wire           init_op,
                  output wire          ready,
                  output wire          valid,
                  input wire [15 : 0]  sclk_div,
                  input wire [15 : 0]  addr,
                  input wire [31 : 0]  write_data,
                  output wire [31 : 0] read_data
                 );


  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------
  localparam SPI_READ_DATA_CMD    = 8'h03;
  localparam SPI_WRITE_DATA_CMD   = 8'h02;
  localparam SPI_READ_STATUS_CMD  = 8'h05;
  localparam SPI_WRITE_STATUS_CMD = 8'h01;

  localparam SEQ_MODE_NO_HOLD = 8'b01000001;

  localparam CTRL_IDLE        = 0;
  localparam CTRL_READY       = 1;
  localparam CTRL_READ        = 2;
  localparam CTRL_WRITE       = 3;
  localparam CTRL_INIT        = 4;
  localparam CTRL_OP_START    = 5;
  localparam CTRL_OP_WAIT     = 6;


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg          ready_reg;
  reg          ready_new;
  reg          ready_we;
  reg          valid_reg;
  reg          valid_new;
  reg          valid_we;

  reg [31 : 0] read_data_reg;
  reg          read_data_we;

  reg [3 : 0]  mkmif_ctrl_reg;
  reg [3 : 0]  mkmif_ctrl_new;
  reg          mkmif_ctrl_we;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  wire [31 : 0] spi_read_data;
  reg  [55 : 0] spi_write_data;
  reg           spi_set;
  reg           spi_start;
  wire          spi_ready;
  reg   [2 : 0] spi_length;


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign ready     = ready_reg;
  assign valid     = valid_reg;
  assign read_data = read_data_reg;


  //----------------------------------------------------------------
  // spi
  // The actual spi interfacce
  //----------------------------------------------------------------
  mkmif_spi spi(
                .clk(clk),
                .reset_n(reset_n),

                .spi_sclk(spi_sclk),
                .spi_cs_n(spi_cs_n),
                .spi_do(spi_do),
                .spi_di(spi_di),

                .set(spi_set),
                .start(spi_start),
                .length(spi_length),
                .divisor(sclk_div),
                .ready(spi_ready),
                .wr_data(spi_write_data),
                .rd_data(spi_read_data)
               );


  //----------------------------------------------------------------
  // reg_update
  // Update functionality for all registers in the core.
  // All registers are positive edge triggered with asynchronous
  // active low reset.
  //----------------------------------------------------------------
  always @ (posedge clk or negedge reset_n)
    begin
      if (!reset_n)
        begin
          ready_reg      <= 0;
          valid_reg      <= 0;
          read_data_reg  <= 32'h0;
          mkmif_ctrl_reg <= CTRL_IDLE;
        end
      else
        begin
          if (ready_we)
            ready_reg <= ready_new;

          if (valid_we)
            valid_reg <= valid_new;

          if (read_data_we)
            read_data_reg <= spi_read_data;

          if (mkmif_ctrl_we)
            mkmif_ctrl_reg <= mkmif_ctrl_new;
        end
    end // reg_update


  //----------------------------------------------------------------
  // mkmif_ctrl
  // Main control FSM.
  //----------------------------------------------------------------
  always @*
    begin : mkmif_ctrl
      spi_set        = 0;
      spi_start      = 0;
      spi_length     = 3'h0;
      spi_write_data = 56'h0;
      read_data_we   = 0;
      ready_new      = 0;
      ready_we       = 0;
      valid_new      = 0;
      valid_we       = 0;
      mkmif_ctrl_new = CTRL_IDLE;
      mkmif_ctrl_we  = 0;

      case (mkmif_ctrl_reg)
        CTRL_IDLE:
          begin
            mkmif_ctrl_new = CTRL_INIT;
            mkmif_ctrl_we  = 1;
          end

        CTRL_READY:
          begin
            ready_new = 1;
            ready_we  = 1;

            if (read_op)
              begin
                ready_new      = 0;
                ready_we       = 1;
                valid_new      = 0;
                valid_we       = 1;
                mkmif_ctrl_new = CTRL_READ;
                mkmif_ctrl_we  = 1;
              end

            if (write_op)
              begin
                ready_new      = 0;
                ready_we       = 1;
                mkmif_ctrl_new = CTRL_WRITE;
                mkmif_ctrl_we  = 1;
              end

            if (init_op)
              begin
                ready_new      = 0;
                ready_we       = 1;
                mkmif_ctrl_new = CTRL_INIT;
                mkmif_ctrl_we  = 1;
              end
          end

        CTRL_READ:
          begin
            spi_set        = 1;
            spi_write_data = {SPI_READ_DATA_CMD, addr, 32'h0};
            spi_length     = 3'h7;
            mkmif_ctrl_new = CTRL_OP_START;
            mkmif_ctrl_we  = 1;
          end

        CTRL_WRITE:
          begin
            spi_set        = 1;
            spi_write_data = {SPI_WRITE_DATA_CMD, addr, write_data};
            spi_length     = 3'h7;
            mkmif_ctrl_new = CTRL_OP_START;
            mkmif_ctrl_we  = 1;
          end

        CTRL_INIT:
          begin
            if (spi_ready)
              begin
                spi_set        = 1;
                spi_write_data = {SPI_WRITE_STATUS_CMD, SEQ_MODE_NO_HOLD, 40'h0};
                spi_length     = 3'h2;
                mkmif_ctrl_new = CTRL_OP_START;
                mkmif_ctrl_we  = 1;
              end
          end

        CTRL_OP_START:
          begin
            spi_start      = 1;
            mkmif_ctrl_new = CTRL_OP_WAIT;
            mkmif_ctrl_we  = 1;
          end

        CTRL_OP_WAIT:
          begin
            if (spi_ready)
              begin
                read_data_we   = 1;
                valid_new      = 1;
                valid_we       = 1;
                mkmif_ctrl_new = CTRL_READY;
                mkmif_ctrl_we  = 1;
              end
          end

        default:
          begin
          end
      endcase // case (mkmif_ctrl_reg)
    end // mkmif_ctrl
endmodule // mkmif

//======================================================================
// EOF mkmif.v
//======================================================================
