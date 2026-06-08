`ifndef RGB_COLOR_SPACE_HSV_DRIVER_SV
`define RGB_COLOR_SPACE_HSV_DRIVER_SV

class rgb_color_space_hsv_driver extends uvm_driver #(rgb_color_space_hsv_seq_item);

  // Register the driver with the UVM factory
  `uvm_component_utils(rgb_color_space_hsv_driver)
  
  // Declare a virtual interface
  virtual rgb_color_space_hsv_if vif;

  // Declare a sequence item handle named trans
  rgb_color_space_hsv_seq_item trans;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Get the virtual interface
    if (!uvm_config_db#(virtual rgb_color_space_hsv_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end
    // Create a new sequence item using type_id
    trans = rgb_color_space_hsv_seq_item::type_id::create("trans");
  endfunction
  
  // Drives transactions to the DUT
  virtual task run_phase(uvm_phase phase);
    forever begin
      @(posedge vif.clk);
      seq_item_port.get_next_item(trans);
      drive_transaction(trans);
      seq_item_port.item_done();
    end
  endtask
  
  // Task to drive the transaction signals onto the interface
  virtual task drive_transaction(rgb_color_space_hsv_seq_item trans);
    // Avoid operations that assign 1 or 0.
    vif.we          = trans.we;
    vif.waddr       = trans.waddr;
    vif.wdata       = trans.wdata;
    vif.valid_in    = trans.valid_in;
    vif.r_component = trans.r_component;
    vif.g_component = trans.g_component;
    vif.b_component = trans.b_component;
  endtask
  
endclass

`endif
