module chacha_qr(
                 input wire           clk,

                 input wire [31 : 0]  a,
                 input wire [31 : 0]  b,
                 input wire [31 : 0]  c,
                 input wire [31 : 0]  d,

                 output wire [31 : 0] a_prim,
                 output wire [31 : 0] b_prim,
                 output wire [31 : 0] c_prim,
                 output wire [31 : 0] d_prim
                );

  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg [31 : 0] a0_reg;
  reg [31 : 0] a0_new;
  reg [31 : 0] a1_reg;
  reg [31 : 0] a1_new;
  reg [31 : 0] c0_reg;
  reg [31 : 0] c0_new;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  reg [31 : 0] internal_a_prim;
  reg [31 : 0] internal_b_prim;
  reg [31 : 0] internal_c_prim;
  reg [31 : 0] internal_d_prim;


  //----------------------------------------------------------------
  // Concurrent connectivity for ports.
  //----------------------------------------------------------------
  assign a_prim = internal_a_prim;
  assign b_prim = internal_b_prim;
  assign c_prim = internal_c_prim;
  assign d_prim = internal_d_prim;


  //----------------------------------------------------------------
  // reg_update
  //
  // Pipeline registers. Does not need reset.
  //----------------------------------------------------------------
  always @ (posedge clk)
    begin : reg_update
      a0_reg <= a0_new;
      a1_reg <= a1_new;
      c0_reg <= c0_new;
    end // reg_update


  //----------------------------------------------------------------
  // qr
  //
  // The actual quarterround function.
  //----------------------------------------------------------------
  always @*
    begin : qr
      reg [31 : 0] a0;
      reg [31 : 0] a1;

      reg [31 : 0] b0;
      reg [31 : 0] b1;
      reg [31 : 0] b2;
      reg [31 : 0] b3;

      reg [31 : 0] c0;
      reg [31 : 0] c1;

      reg [31 : 0] d0;
      reg [31 : 0] d1;
      reg [31 : 0] d2;
      reg [31 : 0] d3;

      a0 = a + b;
      a0_new = a0;

      d0 = d ^ a0_reg;
      d1 = {d0[15 : 0], d0[31 : 16]};

      c0 = c + d1;
      c0_new = c0;

      b0 = b ^ c0_reg;
      b1 = {b0[19 : 0], b0[31 : 20]};

      a1 = a0_reg + b1;
      a1_new = a1;

      d2 = d1 ^ a1_reg;
      d3 = {d2[23 : 0], d2[31 : 24]};
      c1 = c0_reg + d3;
      b2 = b1 ^ c1;
      b3 = {b2[24 : 0], b2[31 : 25]};

      internal_a_prim = a1_reg;
      internal_b_prim = b3;
      internal_c_prim = c1;
      internal_d_prim = d3;
    end // qr
endmodule // chacha_qr

//======================================================================
// EOF chacha_qr.v
//======================================================================
