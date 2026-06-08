module debouncer(clk100Mhz, rst, i_sig, o_sig_debounced);
   input clk100Mhz, rst;      
   input  i_sig;
   output o_sig_debounced;

   reg isig_rg, isig_sync_rg;                      // Registers in 2FF Synchronizer
   reg sig_rg, sig_d_rg, sig_debounced_rg ;        // Registers for switch's state
   reg [3:0] counter_rg;                           // Counter
   
   always @(posedge clk100Mhz)
   begin
       // Reset  
       if (rst) begin
          // Internal Registers
          sig_rg <= 0;
          sig_d_rg <= 0;
          sig_debounced_rg <= 0;
          counter_rg <= 1;
       end
       // Out of reset
       else begin
          // Register state of switch      
          sig_rg <= isig_sync_rg;
          sig_d_rg <= sig_rg;
   
          // Increment counter if two consecutive states are same, otherwise reset
          counter_rg <= (sig_d_rg == sig_rg) ? counter_rg + 1 : 1;
     
          // Counter overflow, valid state registered
          if (counter_rg [3]) begin
             sig_debounced_rg <= sig_d_rg ;
          end
       end
   end
   
   always @(posedge clk100Mhz) begin
       // Reset  
       if (rst) begin
          // Internal Registers
          isig_rg <= 0;
          isig_sync_rg <= 0;
         
       end
       // Out of reset
       else begin
          isig_rg <= i_sig;               // Metastable flop
          isig_sync_rg <= isig_rg;        // Synchronizing flop
       end
   end
   assign o_sig_debounced = sig_debounced_rg;

endmodule