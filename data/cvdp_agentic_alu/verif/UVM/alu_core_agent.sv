
`ifndef ALU_CORE_AGENT_SV
`define ALU_CORE_AGENT_SV

//------------------------------------------------------------------------------
// alu_core_agent: UVM agent for alu_core DUT
//------------------------------------------------------------------------------

class alu_core_agent extends uvm_agent;
  `uvm_component_utils(alu_core_agent)

  // Agent mode: ACTIVE (default) or PASSIVE
  uvm_active_passive_enum is_active = UVM_ACTIVE;

  // Sub-components
  alu_core_sequencer sqr;
  alu_core_driver    drv;
  alu_core_monitor   mon;

  // Virtual interface handle
  virtual alu_core_if vif;

  // Analysis port for broadcasting monitored transactions
  uvm_analysis_port #(alu_core_seq_item) agent_ap;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
    agent_ap = new("agent_ap", this);
  endfunction

  // Build phase: create sub-components and configure interface
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Get the virtual interface from the config DB
    if (!uvm_config_db#(virtual alu_core_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", "Virtual interface must be set for alu_core_agent via config DB with name 'vif'")
    end

    // Pass the interface to driver and monitor via config DB
    uvm_config_db#(virtual alu_core_if)::set(this, "drv", "vif", vif);
    uvm_config_db#(virtual alu_core_if)::set(this, "mon", "vif", vif);

    // Create sub-components
    sqr = alu_core_sequencer::type_id::create("sqr", this);
    drv = alu_core_driver   ::type_id::create("drv", this);
    mon = alu_core_monitor  ::type_id::create("mon", this);

    // Set agent mode (default ACTIVE)
    if (!uvm_config_db#(uvm_active_passive_enum)::get(this, "", "is_active", is_active))
      is_active = UVM_ACTIVE;
  endfunction

  // Connect phase: connect sequencer, driver, and monitor
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // Only connect sequencer and driver in ACTIVE mode
    if (is_active == UVM_ACTIVE) begin
      drv.seq_item_port.connect(sqr.seq_item_export);
    end

    // Connect monitor's analysis port to agent's analysis port
    mon.ap.connect(agent_ap);
  endfunction

endclass

`endif
