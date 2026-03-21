`ifndef RGB_COLOR_SPACE_HSV_MONITOR_SV
`define RGB_COLOR_SPACE_HSV_MONITOR_SV

class rgb_color_space_hsv_monitor extends uvm_monitor;

  `uvm_component_utils(rgb_color_space_hsv_monitor)
  // Declare a virtual interface
  virtual rgb_color_space_hsv_if vif;

  // Declare analysis port named ap
  uvm_analysis_port #(rgb_color_space_hsv_seq_item) ap;

  // Declare events
  uvm_event end_of_frame_evt;
  uvm_event data_ready_evt;

  // Declare sequence item to store monitored data
  rgb_color_space_hsv_seq_item seq_item;

  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap = new("ap", this);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Get the virtual interface
    if (!uvm_config_db#(virtual rgb_color_space_hsv_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", "virtual interface must be set for rgb_color_space_hsv_monitor")
    end

    // Create a new sequence item using type_id
    seq_item = rgb_color_space_hsv_seq_item::type_id::create("seq_item");

    // Get global events
    end_of_frame_evt = uvm_event_pool::get_global("end_of_frame_evt");
    data_ready_evt   = uvm_event_pool::get_global("data_ready_evt");
  endfunction

  // Run phase to monitor the signals
  virtual task run_phase(uvm_phase phase);
    forever begin
	rgb_color_space_hsv_seq_item item_c;
	item_c = rgb_color_space_hsv_seq_item::type_id::create("item_c");

      @(posedge vif.clk);

      // Non-blocking assignment to simulate hardware behavior
      item_c.clk         = vif.clk;
      item_c.rst         = vif.rst;
      item_c.we          = vif.we;
      item_c.waddr       = vif.waddr;
      item_c.wdata       = vif.wdata;
      item_c.valid_in    = vif.valid_in;
      item_c.r_component = vif.r_component;
      item_c.g_component = vif.g_component;
      item_c.b_component = vif.b_component;
      item_c.h_component = vif.h_component;
      item_c.s_component = vif.s_component;
      item_c.v_component = vif.v_component;
      item_c.valid_out   = vif.valid_out;

      // Trigger events if corresponding signals are asserted
      if (item_c.valid_out) begin
        data_ready_evt.trigger();
      end

      // Example: if you have a frame end signal, trigger end_of_frame_evt
      // if (vif.end_of_frame) begin
      //   end_of_frame_evt.trigger();
      // end

      // Send the sequence item to the analysis port
	//item_c.copy(seq_item);
      ap.write(item_c);
    end
  endtask

endclass

`endif
