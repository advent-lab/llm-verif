
`ifndef MEMORY_SCHEDULER_AGENT_SV
`define MEMORY_SCHEDULER_AGENT_SV

// UVM agent for memory_scheduler
class memory_scheduler_agent extends uvm_agent;

  // Register with UVM factory
  `uvm_component_utils(memory_scheduler_agent)

  // Sub-components
  memory_scheduler_sequencer sqr;   // Sequencer
  memory_scheduler_driver    drv;   // Driver
  memory_scheduler_monitor   mon;   // Monitor

  // Virtual interface
  virtual memory_scheduler_if vif;

  // Analysis port for broadcasting monitored data
  uvm_analysis_port#(memory_scheduler_seq_item) agent_ap;

  // Agent mode (ACTIVE/PASSIVE)
  uvm_active_passive_enum is_active;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
    agent_ap = new("agent_ap", this);
  endfunction

  // Build phase: create and configure sub-components and interface
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Get agent mode (default ACTIVE)
    if (!uvm_config_db#(uvm_active_passive_enum)::get(this, "", "is_active", is_active))
      is_active = UVM_ACTIVE;

    // Get virtual interface from config DB
    if (!uvm_config_db#(virtual memory_scheduler_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass virtual interface to driver and monitor via config DB
    uvm_config_db#(virtual memory_scheduler_if)::set(this, "drv", "vif", vif);
    uvm_config_db#(virtual memory_scheduler_if)::set(this, "mon", "vif", vif);

    // Create sub-components
    if (is_active == UVM_ACTIVE) begin
      sqr = memory_scheduler_sequencer::type_id::create("sqr", this);
      drv = memory_scheduler_driver   ::type_id::create("drv", this);
    end
    mon = memory_scheduler_monitor::type_id::create("mon", this);
  endfunction

  // Connect phase: wire up sequencer, driver, and monitor
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    if (is_active == UVM_ACTIVE) begin
      // Connect sequencer and driver
      drv.seq_item_port.connect(sqr.seq_item_export);
    end

    // Connect monitor's analysis port to agent's analysis port
    mon.ap.connect(agent_ap);
  endfunction

endclass

`endif
