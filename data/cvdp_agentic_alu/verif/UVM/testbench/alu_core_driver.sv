`ifndef ALU_CORE_DRIVER_SV
`define ALU_CORE_DRIVER_SV

class alu_core_driver extends uvm_driver #(alu_core_seq_item);

  // Register the driver with the UVM factory
  `uvm_component_utils(alu_core_driver)
  
  // Declare a virtual interface
  virtual alu_core_if vif;

  // Declare a sequence item handle named trans
  alu_core_seq_item trans;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Get the virtual interface
    if (!uvm_config_db#(virtual alu_core_if)::get(this, "", "vif", vif)) begin
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    end
    // Create a new sequence item using type_id
    trans = alu_core_seq_item::type_id::create("trans");
  endfunction
  
  // Drives transactions to the DUT
  virtual task run_phase(uvm_phase phase);
    forever begin
      @(negedge vif.clk);
      seq_item_port.get_next_item(trans);
      drive_transaction(trans);
      seq_item_port.item_done();
    end
  endtask
  
  // Task to drive the transaction signals onto the interface
  virtual task drive_transaction(alu_core_seq_item trans);
    vif.opcode   <= trans.opcode;
    vif.operand1 <= trans.operand1;
    vif.operand2 <= trans.operand2;
    vif.operand3 <= trans.operand3;
  endtask
  
endclass

`endif
