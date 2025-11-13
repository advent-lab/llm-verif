module custom_byte_enable_ram 
  #(
    parameter XLEN  = 32,
    parameter LINES = 8192
  )
  (
    input  logic                     clk,
    input  logic[$clog2(LINES)-1:0]  addr_a,
    input  logic                     en_a,
    input  logic[XLEN/8-1:0]         be_a,
    input  logic[XLEN-1:0]           data_in_a,
    output logic[XLEN-1:0]           data_out_a,
    input  logic[$clog2(LINES)-1:0]  addr_b,
    input  logic                     en_b,
    input  logic[XLEN/8-1:0]         be_b,
    input  logic[XLEN-1:0]           data_in_b,
    output logic[XLEN-1:0]           data_out_b
  );

  localparam ADDR_WIDTH = $clog2(LINES);

  logic [XLEN-1:0] ram [LINES-1:0];

  logic [ADDR_WIDTH-1:0] addr_a_reg;
  logic                  en_a_reg;
  logic [XLEN/8-1:0]     be_a_reg;
  logic [XLEN-1:0]       data_in_a_reg;

  logic [ADDR_WIDTH-1:0] addr_b_reg;
  logic                  en_b_reg;
  logic [XLEN/8-1:0]     be_b_reg;
  logic [XLEN-1:0]       data_in_b_reg;

  always_ff @(posedge clk) begin
    addr_a_reg    <= addr_a;
    en_a_reg      <= en_a;
    be_a_reg      <= be_a;
    data_in_a_reg <= data_in_a;

    addr_b_reg    <= addr_b;
    en_b_reg      <= en_b;
    be_b_reg      <= be_b;
    data_in_b_reg <= data_in_b;
  end

  always_ff @(posedge clk) begin
    if (en_a_reg && en_b_reg && (addr_a_reg == addr_b_reg)) begin
      if (be_a_reg[0])
        ram[addr_a_reg][7:0] <= data_in_a_reg[7:0];
      else if (be_b_reg[0])
        ram[addr_a_reg][7:0] <= data_in_b_reg[7:0];

      if (be_a_reg[1])
        ram[addr_a_reg][15:8] <= data_in_a_reg[15:8];
      else if (be_b_reg[1])
        ram[addr_a_reg][15:8] <= data_in_b_reg[15:8];

      if (be_a_reg[2])
        ram[addr_a_reg][23:16] <= data_in_a_reg[23:16];
      else if (be_b_reg[2])
        ram[addr_a_reg][23:16] <= data_in_b_reg[23:16];

      if (be_a_reg[3])
        ram[addr_a_reg][31:24] <= data_in_a_reg[31:24];
      else if (be_b_reg[3])
        ram[addr_a_reg][31:24] <= data_in_b_reg[31:24];
    end else begin
      if (en_a_reg) begin
        if (be_a_reg[0])
          ram[addr_a_reg][7:0] <= data_in_a_reg[7:0];
        if (be_a_reg[1])
          ram[addr_a_reg][15:8] <= data_in_a_reg[15:8];
        if (be_a_reg[2])
          ram[addr_a_reg][23:16] <= data_in_a_reg[23:16];
        if (be_a_reg[3])
          ram[addr_a_reg][31:24] <= data_in_a_reg[31:24];
      end

      if (en_b_reg) begin
        if (be_b_reg[0])
          ram[addr_b_reg][7:0] <= data_in_b_reg[7:0];
        if (be_b_reg[1])
          ram[addr_b_reg][15:8] <= data_in_b_reg[15:8];
        if (be_b_reg[2])
          ram[addr_b_reg][23:16] <= data_in_b_reg[23:16];
        if (be_b_reg[3])
          ram[addr_b_reg][31:24] <= data_in_b_reg[31:24];
      end
    end

    data_out_a <= ram[addr_a_reg];
    data_out_b <= ram[addr_b_reg];
  end

endmodule