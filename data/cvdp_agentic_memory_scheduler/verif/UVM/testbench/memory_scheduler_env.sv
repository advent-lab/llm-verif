
//--------------------------------------------------------------
// memory_scheduler_env.sv
// UVM Environment for memory_scheduler
//--------------------------------------------------------------

`ifndef MEMORY_SCHEDULER_ENV_SV
`define MEMORY_SCHEDULER_ENV_SV

// Import UVM
import uvm_pkg::*;
//`include "uvm_macros.svh" // Assume included at top-level

//--------------------------------------------------------------
// Class: memory_scheduler_env
// Description: UVM environment for memory_scheduler
//--------------------------------------------------------------
class memory_scheduler_env extends uvm_env;
  `uvm_component_utils(memory_scheduler_env)

  // ----------------------------------------------------------
  // Sub-components
  // ----------------------------------------------------------
  memory_scheduler_agent      agent;      // Agent (driver, monitor, sequencer)
  memory_scheduler_scoreboard scb;        // Scoreboard
  //ZI memory_scheduler_subscriber cov;        // Coverage subscriber
  memory_scheduler_ref_model  ref_model;  // Reference model
  //memory_scheduler_reg_model reg_model; // Register model (not provided, commented out)

  // Virtual interface handle
  virtual memory_scheduler_if vif;

  // ----------------------------------------------------------
  // Constructor
  // ----------------------------------------------------------
  function new(string name = "memory_scheduler_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  // ----------------------------------------------------------
  // Build Phase
  // ----------------------------------------------------------
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // --------------------------------------------------------
    // Virtual interface configuration
    // --------------------------------------------------------
    if (!uvm_config_db#(virtual memory_scheduler_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass virtual interface down to agent
    uvm_config_db#(virtual memory_scheduler_if)::set(this, "agent", "vif", vif);

    // --------------------------------------------------------
    // Agent mode configuration
    // --------------------------------------------------------
    // (Single agent: set to ACTIVE by default)
    uvm_config_db#(uvm_active_passive_enum)::set(this, "agent", "is_active", UVM_ACTIVE);

    // --------------------------------------------------------
    // Coverage configuration
    // --------------------------------------------------------
    // (Coverage enabled if subscriber exists)
    //ZI uvm_config_db#(bit)::set(this, "cov", "enable_coverage", 1'b1);

    // --------------------------------------------------------
    // Register model configuration (not provided)
    // --------------------------------------------------------
    //uvm_config_db#(bit)::set(this, "reg_model", "enable_reg_model", 1'b1);

    // --------------------------------------------------------
    // Component instantiation
    // --------------------------------------------------------
    agent     = memory_scheduler_agent     ::type_id::create("agent", this);
    scb       = memory_scheduler_scoreboard::type_id::create("scb", this);
    //ZIcov       = memory_scheduler_subscriber::type_id::create("cov", this);
    ref_model = memory_scheduler_ref_model ::type_id::create("ref_model", this);
    //reg_model = memory_scheduler_reg_model ::type_id::create("reg_model", this); // Not provided

  endfunction : build_phase

  // ----------------------------------------------------------
  // Connect Phase
  // ----------------------------------------------------------
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // --------------------------------------------------------
    // Analysis connections
    // --------------------------------------------------------

    // agent.agent_ap -> ref_model.in_imp
    agent.agent_ap.connect(ref_model.in_imp);

    // ref_model.out_ap -> scb.expected_imp
    ref_model.out_ap.connect(scb.expected_imp);

    // agent.agent_ap -> scb.actual_imp
    agent.agent_ap.connect(scb.actual_imp);

    // agent.agent_ap -> cov.analysis_export (called 'imp' in subscriber)
    //ZI agent.agent_ap.connect(cov.analysis_export);

    // Register model connections (not provided)
    //reg_model.connect_some_port(...);

  endfunction : connect_phase

endclass : memory_scheduler_env

`endif // MEMORY_SCHEDULER_ENV_SV
