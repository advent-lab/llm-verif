
`ifndef RGB_COLOR_SPACE_HSV_AGENT_SV
`define RGB_COLOR_SPACE_HSV_AGENT_SV

//------------------------------------------------------------------------------
// rgb_color_space_hsv_agent
// UVM Agent for rgb_color_space_hsv DUT
//------------------------------------------------------------------------------

class rgb_color_space_hsv_agent extends uvm_agent;

  // Register with UVM factory
  `uvm_component_utils(rgb_color_space_hsv_agent)

  // Agent sub-components
  rgb_color_space_hsv_sequencer sqr;
  rgb_color_space_hsv_driver    drv;
  rgb_color_space_hsv_monitor   mon;

  // Virtual interface handle
  virtual rgb_color_space_hsv_if vif;

  // Analysis port for broadcasting monitored transactions
  uvm_analysis_port #(rgb_color_space_hsv_seq_item) agent_ap;

  // Agent mode (ACTIVE/PASSIVE)
  uvm_active_passive_enum is_active;

  // Constructor
  function new(string name, uvm_component parent);
    super.new(name, parent);
    agent_ap = new("agent_ap", this);
    is_active = UVM_ACTIVE; // Default to ACTIVE
  endfunction

  // Build phase: create sub-components and configure interface
  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);

    // Get the virtual interface from config DB
    if (!uvm_config_db#(virtual rgb_color_space_hsv_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end

    // Pass the interface to driver and monitor via config DB
    uvm_config_db#(virtual rgb_color_space_hsv_if)::set(this, "drv", "vif", vif);
    uvm_config_db#(virtual rgb_color_space_hsv_if)::set(this, "mon", "vif", vif);

    // Create sub-components
    if (is_active == UVM_ACTIVE) begin
      sqr = rgb_color_space_hsv_sequencer::type_id::create("sqr", this);
      drv = rgb_color_space_hsv_driver   ::type_id::create("drv", this);
    end
    mon = rgb_color_space_hsv_monitor::type_id::create("mon", this);
  endfunction

  // Connect phase: connect ports and exports
  virtual function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // Connect driver and sequencer if ACTIVE
    if (is_active == UVM_ACTIVE) begin
      drv.seq_item_port.connect(sqr.seq_item_export);
    end

    // Connect monitor's analysis port to agent's analysis port
    mon.ap.connect(agent_ap);
  endfunction

endclass

`endif // RGB_COLOR_SPACE_HSV_AGENT_SV
