module pseudo_entropy(
                      input wire           clk,
                      input wire           reset_n,

                      input wire           enable,

                      output wire [31 : 0] raw_entropy,
                      output wire [31 : 0] stats,

                      output wire          enabled,
                      output wire          entropy_syn,
                      output wire [31 : 0] entropy_data,
                      input wire           entropy_ack
                     );


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign enabled      = enable;

  assign raw_entropy  = enable ? 32'h00ff00ff : 32'h00000000;
  assign stats        = enable ? 32'hff00ff00 : 32'h00000000;

  assign entropy_syn  = enable;
  assign entropy_data = enable ? 32'hf1e2d3c4 : 32'h00000000;

endmodule // pseudo_entropy

//======================================================================
// EOF pseudo_entropy.v
//======================================================================
