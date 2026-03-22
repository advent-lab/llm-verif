
//--------------------------------------------------------------
// UVM Environment for rgb_color_space_hsv
//--------------------------------------------------------------
class rgb_color_space_hsv_env extends uvm_env;
  `uvm_component_utils(rgb_color_space_hsv_env)

  // Agent, Scoreboard, Coverage Subscriber, Reference Model handles
  rgb_color_space_hsv_agent      agent;
  rgb_color_space_hsv_scoreboard scb;
  rgb_color_space_hsv_subscriber cov;
  rgb_color_space_hsv_ref_model ref_model;
  // rgb_color_space_hsv_reg_model reg_model; // Uncomment if reg_model exists

  // Virtual interface handle
  virtual rgb_color_space_hsv_if vif;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  // Build phase: instantiate and configure all sub-components
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Retrieve the virtual interface from config DB
    if (!uvm_config_db#(virtual rgb_color_space_hsv_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", "Virtual interface must be set for rgb_color_space_hsv_env")
    end

    // Pass the interface to the agent via config DB
    uvm_config_db#(virtual rgb_color_space_hsv_if)::set(this, "agent", "vif", vif);

    // Instantiate mandatory components
    agent     = rgb_color_space_hsv_agent     ::type_id::create("agent",     this);
    scb       = rgb_color_space_hsv_scoreboard::type_id::create("scb",       this);
    cov       = rgb_color_space_hsv_subscriber::type_id::create("cov",       this);
    ref_model = rgb_color_space_hsv_ref_model::type_id::create("ref_model", this);

    // Optional: Instantiate register model if provided
    // reg_model = rgb_color_space_hsv_reg_model::type_id::create("reg_model", this);

    // Agent mode configuration (ACTIVE/PASSIVE)
    // If multiple agents, configure as needed; here, single agent is ACTIVE by default
    uvm_config_db#(uvm_active_passive_enum)::set(this, "agent", "is_active", UVM_ACTIVE);

    // Coverage configuration: enable/disable based on cov existence (always enabled here)
    // uvm_config_db#(bit)::set(this, "cov", "enable_coverage", 1);

    // Register model configuration (commented out, since reg_model not provided)
    // uvm_config_db#(bit)::set(this, "reg_model", "enable_reg_model", 1);

  endfunction

  // Connect phase: connect analysis ports/exports
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // Connect agent's analysis port to reference model's input
    agent.agent_ap.connect(ref_model.in_imp);

    // Connect reference model's output to scoreboard's expected input
    ref_model.out_ap.connect(scb.expected_imp);

    // Connect agent's analysis port to scoreboard's actual input
    agent.agent_ap.connect(scb.actual_imp);

    // Connect agent's analysis port to coverage subscriber
    agent.agent_ap.connect(cov.sub_imp);

    // Register model connections would go here if present
    // reg_model.some_export.connect(...);

  endfunction

endclass : rgb_color_space_hsv_env
