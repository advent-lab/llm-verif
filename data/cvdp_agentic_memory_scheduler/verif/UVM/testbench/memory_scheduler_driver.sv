`ifndef MEMORY_SCHEDULER_DRIVER_SV
`define MEMORY_SCHEDULER_DRIVER_SV

class memory_scheduler_driver extends uvm_driver #(memory_scheduler_seq_item);

  // Register the driver with the UVM factory
  `uvm_component_utils(memory_scheduler_driver)
  
  // Declare a virtual interface
  virtual memory_scheduler_if vif;

  // Declare a sequence item handle named trans
  memory_scheduler_seq_item trans;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual memory_scheduler_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end
    trans = memory_scheduler_seq_item::type_id::create("trans");
  endfunction
  
  // Drives transactions to the DUT
  virtual task run_phase(uvm_phase phase);
    // Wait for reset deassertion if present
    if (vif.reset !== 'x) begin
      @(negedge vif.reset);
    end
    forever begin
      @(posedge vif.clk);
      seq_item_port.get_next_item(trans);
      drive_transaction(trans);
      seq_item_port.item_done();
    end
  endtask
  
  // Task to drive the transaction signals onto the interface
  virtual task drive_transaction(memory_scheduler_seq_item trans);
    // Avoid operations that assign 1 or 0 directly
    vif.request    <= trans.request;
    vif.qos        <= trans.qos;
    vif.address0   <= trans.address0;
    vif.address1   <= trans.address1;
    vif.address2   <= trans.address2;
    vif.address3   <= trans.address3;
    vif.mem_ack    <= trans.mem_ack;
  endtask
  
endclass

`endif