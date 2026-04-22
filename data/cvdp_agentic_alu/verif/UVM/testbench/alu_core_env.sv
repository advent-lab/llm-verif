
//------------------------------------------------------------------------------
// Title: alu_core_env
// Description: UVM environment for alu_core DUT
//------------------------------------------------------------------------------

class alu_core_env extends uvm_env;

  // Register this environment with the UVM factory
  `uvm_component_utils(alu_core_env)

  //--------------------------------------------------------------------------
  // Component Declarations
  //--------------------------------------------------------------------------

  // Agent (drives and monitors DUT interface)
  alu_core_agent      agent;

  // Scoreboard (checks actual vs expected results)
  alu_core_scoreboard scb;

  // Coverage subscriber (functional coverage)
  // ZI alu_core_subscriber cov;

  // Reference model (predicts expected results)
  alu_core_ref_model  ref_model;

  // Optional: Register model (not provided, so commented out)
  // alu_core_reg_model reg_model;

  // Virtual interface handle
  virtual alu_core_if vif;

  //--------------------------------------------------------------------------
  // Constructor
  //--------------------------------------------------------------------------

  function new(string name = "alu_core_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  //--------------------------------------------------------------------------
  // Build Phase
  //--------------------------------------------------------------------------

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Retrieve the virtual interface from config_db
    if (!uvm_config_db#(virtual alu_core_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass the virtual interface to the agent via config_db
    uvm_config_db#(virtual alu_core_if)::set(this, "agent", "vif", vif);

    //--------------------------------------------------------------------------
    // Instantiate sub-components using factory
    //--------------------------------------------------------------------------

    agent     = alu_core_agent     ::type_id::create("agent", this);
    scb       = alu_core_scoreboard::type_id::create("scb",   this);
    // ZI cov       = alu_core_subscriber::type_id::create("cov",   this);
    ref_model = alu_core_ref_model ::type_id::create("ref_model", this);

    // Optional: Register model instantiation (not provided)
    // reg_model = alu_core_reg_model::type_id::create("reg_model", this);

    //--------------------------------------------------------------------------
    // Agent Mode Configuration (ACTIVE/PASSIVE)
    //--------------------------------------------------------------------------
    // If multiple agents are present, configure as needed here.
    // For single agent, default is ACTIVE.
    // Example (if needed):
    // agent.is_active = UVM_ACTIVE;

    //--------------------------------------------------------------------------
    // Coverage Configuration
    //--------------------------------------------------------------------------
    // If coverage subscriber exists, coverage is enabled.
    // (No explicit switch needed; instantiation is sufficient.)

    //--------------------------------------------------------------------------
    // Register Model Configuration
    //--------------------------------------------------------------------------
    // If reg_model exists, configure here.
    // (Commented out since reg_model is not provided.)
    // uvm_config_db#(alu_core_reg_model)::set(this, "agent.*", "reg_model", reg_model);

  endfunction

  //--------------------------------------------------------------------------
  // Connect Phase
  //--------------------------------------------------------------------------

  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    //--------------------------------------------------------------------------
    // Analysis Connections
    //--------------------------------------------------------------------------

    // agent.agent_ap: uvm_analysis_port #(alu_core_seq_item)
    // ref_model.in_imp: uvm_analysis_imp #(alu_core_item, alu_core_ref_model)
    // ref_model.out_ap: uvm_analysis_port #(alu_core_item)
    // scb.expected_imp: uvm_analysis_imp_expected #(alu_core_seq_item, alu_core_scoreboard)
    // scb.actual_imp:   uvm_analysis_imp_actual   #(alu_core_seq_item, alu_core_scoreboard)
    // cov.analysis_imp: uvm_analysis_imp #(alu_core_seq_item, alu_core_subscriber)

    // Connect agent's analysis port to reference model's input
    agent.agent_ap.connect(ref_model.in_imp);

    // Connect reference model's output to scoreboard's expected input
    ref_model.out_ap.connect(scb.expected_imp);

    // Connect agent's analysis port to scoreboard's actual input
    agent.agent_ap.connect(scb.actual_imp);

    // Connect agent's analysis port to coverage subscriber
    // ZI agent.agent_ap.connect(cov.analysis_export);

    // Optional: Register model connections (not provided)
    // agent.reg_adapter.connect(reg_model.bus_export);

  endfunction

endclass
