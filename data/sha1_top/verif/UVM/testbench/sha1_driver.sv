`ifndef SHA1_DRIVER_SV
`define SHA1_DRIVER_SV

// =============================================================================
// sha1_driver
//
// Timing matches both the Verilog and SystemVerilog reference testbenches:
//
//   @(posedge clk)             — sync to rising edge
//   drive cs/we/address/data   — signals stable for the coming cycle
//   @(posedge clk)             — DUT latches on this edge
//   capture read_data          — combinational output valid here
//   deassert cs/we             — clean bus between transactions
//
// cs is asserted for exactly one clock cycle per transaction.
// =============================================================================

class sha1_driver extends uvm_driver #(sha1_seq_item);

  `uvm_component_utils(sha1_driver)

  virtual sha1_if vif;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual sha1_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s",
                                     get_full_name()))
  endfunction

  virtual task run_phase(uvm_phase phase);
    // Idle bus before any transactions
    idle_bus();
    forever begin
      sha1_seq_item trans;
      seq_item_port.get_next_item(trans);
      drive_transaction(trans);
      seq_item_port.item_done();
    end
  endtask

  // ---------------------------------------------------------------------------
  // drive_transaction
  //   Cycle 1: sync to posedge, drive signals
  //   Cycle 2: DUT latches; capture read_data; deassert
  // ---------------------------------------------------------------------------
  virtual task drive_transaction(sha1_seq_item trans);
    // Cycle 1 — drive
    @(posedge vif.clk);
    vif.reset_n    = trans.reset_n;
    vif.cs         = trans.cs;
    vif.we         = trans.we;
    vif.address    = trans.address;
    vif.write_data = trans.write_data;

    // Cycle 2 — DUT samples on this edge; read_data is valid
    @(posedge vif.clk);
    trans.read_data = vif.read_data;
    trans.error     = vif.error;

    // Deassert in the same time step — no extra clock consumed
    vif.cs         = 0;
    vif.we         = 0;
    vif.address    = '0;
    vif.write_data = '0;
  endtask

  // ---------------------------------------------------------------------------
  // idle_bus — deassert all control signals, keep reset_n high
  // ---------------------------------------------------------------------------
  task idle_bus();
    @(posedge vif.clk);
    vif.reset_n    = 1;
    vif.cs         = 0;
    vif.we         = 0;
    vif.address    = '0;
    vif.write_data = '0;
  endtask

endclass

`endif // SHA1_DRIVER_SV
