
`ifndef ALU_CORE_AGENT_SV
`define ALU_CORE_AGENT_AGENT_SV

// UVM agent for {modulename}
class alu_core_agent extends uvm_agent;

  // Register with UVM factory
  `uvm_component_utils(alu_core_agent)

  // Agent mode (ACTIVE/PASSIVE)
  uvm_active_passive_enum is_active = UVM_ACTIVE;

  // Sub-components
  alu_core_sequencer sqr;
  alu_core_driver    drv;
  alu_core_monitor   mon;

  // Virtual interface
  virtual alu_core_if vif;

  // Analysis port for broadcasting monitored transactions
  uvm_analysis_port #(alu_core_seq_item) agent_ap;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
    agent_ap = new("agent_ap", this);
  endfunction

  // Build phase: instantiate and configure sub-components
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Retrieve the virtual interface from config_db
    if (!uvm_config_db#(virtual alu_core_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass the virtual interface to driver and monitor via config_db
    uvm_config_db#(virtual alu_core_if)::set(this, "*drv", "vif", vif);
    uvm_config_db#(virtual alu_core_if)::set(this, "*mon", "vif", vif);

    // Create sub-components
    if (is_active == UVM_ACTIVE) begin
      sqr = alu_core_sequencer::type_id::create("sqr", this);
      drv = alu_core_driver   ::type_id::create("drv", this);
    end
    mon = alu_core_monitor::type_id::create("mon", this);
  endfunction

  // Connect phase: connect sequencer, driver, and monitor
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    if (is_active == UVM_ACTIVE) begin
      // Connect driver and sequencer
      drv.seq_item_port.connect(sqr.seq_item_export);
    end

    // Connect monitor's analysis port to agent's analysis port
    mon.ap.connect(agent_ap);
  endfunction

endclass

`endif
