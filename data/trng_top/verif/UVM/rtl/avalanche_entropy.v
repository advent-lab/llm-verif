module avalanche_entropy(
                         input wire           clk,
                         input wire           reset_n,

                         input wire           noise,

                         input wire           cs,
                         input wire           we,
                         input wire  [7 : 0]  address,
                         input wire  [31 : 0] write_data,
                         output wire [31 : 0] read_data,
                         output wire          error,

                         input wire           discard,
                         input wire           test_mode,
                         output wire          security_error,

                         output wire          entropy_enabled,
                         output wire [31 : 0] entropy_data,
                         output wire          entropy_valid,
                         input wire           entropy_ack,

                         output wire [7 : 0]  debug,
                         input wire           debug_update
                        );


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign read_data      = 32'h00000000;
  assign error          = 0;
  assign security_error = 0;

  assign entropy_enabled = 1;
  assign entropy_data    = 32'h11223344;
  assign entropy_valid   = 1;

  assign debug           = 8'haa;

endmodule // avalanche_entropy

//======================================================================
// EOF avalanche_entropy.v
//======================================================================
