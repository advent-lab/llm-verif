`ifndef TRNG_ENV_SV
`define TRNG_ENV_SV

class trng_env extends uvm_env;
    `uvm_component_utils(trng_env)

    // Component handles
    trng_agent agent;
    // ZI trng_subscriber cov;

    // Virtual interface handle
    virtual trng_if vif;

    // Constructor
    function new(string name = "trng_env", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    //build phase to create components and get the interface
    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual trng_if)::get(this, "", "vif", vif)) begin
            `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
        end

        // pass the virtual interface to the agent
        uvm_config_db#(virtual trng_if)::set(this, "agent", "vif", vif);

        // instantiate the agent and coverage subscriber
        agent = trng_agent::type_id::create("agent", this);
        // ZI cov = trng_subscriber::type_id::create("cov", this);
    endfunction

    // Connect phase to connect the analysis port to the coverage subscriber
    virtual function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        // Connect the agent's analysis port to the coverage subscriber
        // ZI agent.ap.connect(cov.analysis_export);
    endfunction
endclass : trng_env

`endif
