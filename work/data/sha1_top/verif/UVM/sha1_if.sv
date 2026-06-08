
interface sha1_if();

  // ------------------------------------------------------------------
  // External bus interface signals — unchanged
  // ------------------------------------------------------------------
  logic        clk;
  logic        reset_n;
  logic        cs;
  logic        we;
  logic [7:0]  address;
  logic [31:0] write_data;
  logic [31:0] read_data;
  logic        error;

  // ------------------------------------------------------------------
  // Internal DUT probe signals — read-only, used by coverage monitor
  // These are hierarchical references into the DUT bound at the top
  // level.  No driver or modport touches these; they are purely
  // observational and have no effect on any other component.
  // ------------------------------------------------------------------
  logic        ready_reg;        // dut.ready_reg
  logic        digest_valid_reg; // dut.digest_valid_reg
  logic [1:0]  fsm_state;        // dut.core.sha1_ctrl_reg
  logic [6:0]  round_ctr;        // dut.core.round_ctr_reg
  logic [159:0] digest_reg;      // dut.digest_reg

  // ------------------------------------------------------------------
  // DUT modport — unchanged, does not include probe signals
  // ------------------------------------------------------------------
  modport DUT (
    input  clk, reset_n, cs, we, address, write_data,
    output read_data, error
  );

endinterface //sha1 design interface
