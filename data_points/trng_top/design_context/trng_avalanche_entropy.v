module trng_avalanche_entropy(
                              // Clock and reset.
                              input wire clk,
                              input wire reset_n,
			      input wire avalanche_noise,
                             );


  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------



  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------


  //----------------------------------------------------------------
  // core instantiations.
  //----------------------------------------------------------------
  avalance_entropy_core entropy1(
                                 .clk(clk),
                                 .reset_n(reset_n),

                                 .enable(entropy1_enable),

                                 .noise(avalanche_noise),

                                 .raw_entropy(entropy1_raw),
                                 .stats(entropy1_stats),

                                 .enabled(entropy1_enabled),
                                 .entropy_syn(entropy1_syn),
                                 .entropy_data(entropy1_data),
                                 .entropy_ack(entropy1_ack),
                                 .led()
                                );


  //----------------------------------------------------------------
  // reg_update
  //
  // Update functionality for all registers in the core.
  // All registers are positive edge triggered with asynchronous
  // active low reset. All registers have write enable.
  //----------------------------------------------------------------
  always @ (posedge clk or negedge reset_n)
    begin
      if (!reset_n)
        begin

        end

      else
        begin

        end
    end // reg_update

endmodule // trng_avalanche_entropy

//======================================================================
// EOF trng_avalanche_entropy.v
//======================================================================
