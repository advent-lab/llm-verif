
//----------------------------------------------------------------------
// sha1_env.sv
// UVM environment for the sha1 module
//----------------------------------------------------------------------
// This environment instantiates the sha1_agent and sha1_subscriber
// components, connects the agent's analysis port directly to the
// coverage subscriber, and handles virtual interface configuration.
// No scoreboard or reference model is present in this environment.
//----------------------------------------------------------------------

`ifndef SHA1_ENV_SV
`define SHA1_ENV_SV

class sha1_env extends uvm_env;
  `uvm_component_utils(sha1_env)

  // ----------------------------------------------------------
  // Component handles
  // ----------------------------------------------------------
  sha1_agent      agent;   // The single agent instance
  // ZI sha1_subscriber cov;     // Coverage subscriber

  // Virtual interface handle
  virtual sha1_if vif;

  // ----------------------------------------------------------
  // Constructor
  // ----------------------------------------------------------
  function new(string name = "sha1_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  // ----------------------------------------------------------
  // build_phase
  //   - Retrieve and propagate virtual interface
  //   - Instantiate agent and coverage subscriber
  //   - Configure agent mode (ACTIVE/PASSIVE) if needed
  // ----------------------------------------------------------
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Retrieve virtual interface from config DB
    if (!uvm_config_db#(virtual sha1_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass virtual interface down to agent
    uvm_config_db#(virtual sha1_if)::set(this, "agent", "vif", vif);

    // Instantiate agent (single instance, so always ACTIVE)
    agent = sha1_agent::type_id::create("agent", this);

    // Instantiate coverage subscriber
    // ZI cov = sha1_subscriber::type_id::create("cov", this);

    // Note: No scoreboard or reference model present in this environment.
    // If a register model is added in the future, instantiate and configure here.
  endfunction

  // ----------------------------------------------------------
  // connect_phase
  //   - Connect agent's analysis port directly to coverage
  //     subscriber (no reference model or scoreboard)
  // ----------------------------------------------------------
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // Connect agent's analysis port to coverage subscriber
    // (agent_ap is the analysis port in sha1_agent, cov is a uvm_subscriber)
    // ZI agent.agent_ap_cov.connect(cov.analysis_export);

    // No scoreboard or reference model connections required.
  endfunction

endclass : sha1_env

`endif // SHA1_ENV_SV
