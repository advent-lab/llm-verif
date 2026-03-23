`ifndef MEMORY_SCHEDULER_MONITOR_SV
`define MEMORY_SCHEDULER_MONITOR_SV

class memory_scheduler_monitor extends uvm_monitor;

  `uvm_component_utils(memory_scheduler_monitor)
  
  // Declare a virtual interface
  virtual memory_scheduler_if vif;

  // Declare analysis port named ap
  uvm_analysis_port #(memory_scheduler_seq_item) ap;

  // Declare events (none needed as per requirements and signal list)

  // Declare sequence item to store monitored data
  memory_scheduler_seq_item seq_item;

  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap = new("ap", this);
  endfunction

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Get the virtual interface
    if (!uvm_config_db#(virtual memory_scheduler_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", $sformatf("Virtual interface must be set for: %s", get_full_name()))
    // Create a new sequence item using type_id
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    // Get global events (none needed)
  endfunction

  // Run phase to monitor the signals
  virtual task run_phase(uvm_phase phase);
    forever begin
	memory_scheduler_seq_item item_c;
	item_c = memory_scheduler_seq_item::type_id::create("item_c", this);
      @(posedge vif.clk);
      // Non-blocking assignments to simulate hardware behavior
      item_c.clk           = vif.clk;
      item_c.reset         = vif.reset;
      item_c.request       = vif.request;
      item_c.qos           = vif.qos;
      item_c.address0      = vif.address0;
      item_c.address1      = vif.address1;
      item_c.address2      = vif.address2;
      item_c.address3      = vif.address3;
      item_c.mem_ack       = vif.mem_ack;
      item_c.mem_address   = vif.mem_address;
      item_c.mem_cmd_valid = vif.mem_cmd_valid;
      item_c.mem_cmd_type  = vif.mem_cmd_type;
      item_c.grant         = vif.grant;

      ap.write(item_c);
    end
  endtask

endclass

`endif
