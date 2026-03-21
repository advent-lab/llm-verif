`ifndef SHA1_MONITOR_SV
`define SHA1_MONITOR_SV

// =============================================================================
// sha1_monitor
//
// Samples the bus on every clock where cs is asserted and broadcasts
// two item types:
//   ap     — sha1_seq_item      for scoreboard / other subscribers
//   ap_cov — sha1_coverage_item for the coverage subscriber
//
// Timing: samples one cycle after cs is observed high, matching the
// driver which drives on cycle N and the DUT latches on cycle N+1.
// =============================================================================

class sha1_monitor extends uvm_monitor;

  `uvm_component_utils(sha1_monitor)

  virtual sha1_if vif;

  uvm_analysis_port #(sha1_seq_item)      ap;
  uvm_analysis_port #(sha1_coverage_item) ap_cov;

  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap     = new("ap",     this);
    ap_cov = new("ap_cov", this);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual sha1_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "Virtual interface must be set for sha1_monitor")
  endfunction

  virtual task run_phase(uvm_phase phase);
    forever begin
      // Wait for cycle N where driver has asserted cs and driven signals.
      // Sample immediately on this same edge — bus signals (address, we,
      // write_data) are valid here. read_data is combinational so it is
      // also valid on this cycle for reads.
      // The DUT's reg_update latches on cycle N+1 internally but the
      // signals we need to sample for coverage are all present on cycle N.
      @(posedge vif.clk);
      if (vif.cs)
        sample_and_broadcast();
    end
  endtask

  local task sample_and_broadcast();
    sha1_seq_item      base_item;
    sha1_coverage_item cov_item;

    base_item = sha1_seq_item::type_id::create("base_item");
    cov_item  = sha1_coverage_item::type_id::create("cov_item");

    // Sample bus signals
    base_item.clk        = vif.clk;
    base_item.reset_n    = vif.reset_n;
    base_item.cs         = vif.cs;
    base_item.we         = vif.we;
    base_item.address    = vif.address;
    base_item.write_data = vif.write_data;
    base_item.read_data  = vif.read_data;
    base_item.error      = vif.error;

    // Copy into coverage item
    cov_item.clk        = base_item.clk;
    cov_item.reset_n    = base_item.reset_n;
    cov_item.cs         = base_item.cs;
    cov_item.we         = base_item.we;
    cov_item.address    = base_item.address;
    cov_item.write_data = base_item.write_data;
    cov_item.read_data  = base_item.read_data;
    cov_item.error      = base_item.error;

    // Decode control bits
    if (vif.cs && vif.we && vif.address == 8'h08) begin
      cov_item.ctrl_init = vif.write_data[0];
      cov_item.ctrl_next = vif.write_data[1];
      cov_item.ctrl_set  = vif.write_data[2];
    end else begin
      cov_item.ctrl_init = 1'b0;
      cov_item.ctrl_next = 1'b0;
      cov_item.ctrl_set  = 1'b0;
    end

    // Sample internal DUT signals
    cov_item.status_ready = vif.ready_reg;
    cov_item.status_valid = vif.digest_valid_reg;
    cov_item.fsm_state    = vif.fsm_state;
    cov_item.round_ctr    = vif.round_ctr;
    cov_item.digest       = vif.digest_reg;

    ap.write(base_item);
    ap_cov.write(cov_item);
  endtask

endclass

`endif // SHA1_MONITOR_SV
