
`ifndef SHA1_AGENT_SV
`define SHA1_AGENT_SV

// UVM agent for the sha1 module
class sha1_agent extends uvm_agent;

  // Register the agent with the UVM factory
  `uvm_component_utils(sha1_agent)

  // Agent sub-components
  sha1_sequencer sqr;   // Sequencer
  sha1_driver    drv;   // Driver
  sha1_monitor   mon;   // Monitor

  // Virtual interface handle
  virtual sha1_if vif;

  // Analysis port for broadcasting monitored transactions
  uvm_analysis_port#(sha1_seq_item) agent_ap;
  uvm_analysis_port #(sha1_coverage_item) agent_ap_cov;  // ADD THIS

  // Agent mode (ACTIVE/PASSIVE)
  uvm_active_passive_enum is_active;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
    agent_ap = new("agent_ap", this);
    agent_ap_cov = new("agent_ap_cov", this);  // ADD THIS
    is_active = UVM_ACTIVE; // Default to ACTIVE mode
  endfunction

  // Build phase: create and configure sub-components
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Retrieve the virtual interface from the config DB
    if (!uvm_config_db#(virtual sha1_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass the virtual interface to driver and monitor via config DB
    uvm_config_db#(virtual sha1_if)::set(this, "drv", "vif", vif);
    uvm_config_db#(virtual sha1_if)::set(this, "mon", "vif", vif);

    // Create sub-components
    if (is_active == UVM_ACTIVE) begin
      sqr = sha1_sequencer::type_id::create("sqr", this);
      drv = sha1_driver   ::type_id::create("drv", this);
    end
    mon = sha1_monitor::type_id::create("mon", this);
  endfunction

  // Connect phase: wire up sequencer, driver, and monitor
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // Connect driver and sequencer in ACTIVE mode
    if (is_active == UVM_ACTIVE) begin
      drv.seq_item_port.connect(sqr.seq_item_export);
    end

    // Connect monitor's analysis port to agent's analysis port
    mon.ap.connect(agent_ap);
    mon.ap_cov.connect(agent_ap_cov);  // ADD THIS
  endfunction

endclass

`endif
