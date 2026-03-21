`ifndef TRNG_AGENT_SV
`define TRNG_AGENT_SV

class trng_agent extends uvm_agent;
    `uvm_component_utils(trng_agent)

    trng_sequencer sqr;
    trng_driver drv;
    trng_monitor mon;

    // Virtual interface handle
    virtual trng_if vif;

    // Analysis port to send transactions to the coverage subscriber
    uvm_analysis_port#(trng_seq_item) ap;

    uvm_active_passive_enum is_active;

    // Constructor
    function new(string name = "trng_agent", uvm_component parent = null);
        super.new(name, parent);
        ap = new("ap", this);
        is_active = UVM_ACTIVE; // Set the agent to active by default
    endfunction

    // Build phase to get the virtual interface
    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual trng_if)::get(this, "", "vif", vif)) begin
            `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
        end

	// Pass the virtual interface to driver and monitor via config DB
	uvm_config_db#(virtual trng_if)::set(this, "drv", "vif", vif);
	uvm_config_db#(virtual trng_if)::set(this, "mon", "vif", vif);

        // Instantiate the sequencer, driver, and monitor
        if (is_active == UVM_ACTIVE) begin
            sqr = trng_sequencer::type_id::create("sqr", this);
            drv = trng_driver::type_id::create("drv", this);
        end
        mon = trng_monitor::type_id::create("mon", this);
    endfunction

    // Connect phase to connect the sequencer to the driver and the monitor to the analysis port
    virtual function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);

        if (is_active == UVM_ACTIVE) begin
            drv.seq_item_port.connect(sqr.seq_item_export);
        end
        // Connect the monitor's virtual interface
        mon.ap.connect(ap);
    endfunction

endclass : trng_agent

`endif
