
//------------------------------------------------------------------------------
// Title: memory scheduler test
// Description: UVM test for This is a description of memory_scheduler_test.
//------------------------------------------------------------------------------
import uvm_pkg::*;
`include "uvm_macros.svh"

class memory_scheduler_test extends uvm_test;
  `uvm_component_utils(memory_scheduler_test)
  
  //Member variable declaration

  memory_scheduler_env env;
  memory_scheduler_base_sequence base_seq;
  memory_scheduler_full_sequence seq1;

  virtual memory_scheduler_if vif;


  function new(string name = "memory_scheduler_test", uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Add build phase code here
	
	if(!uvm_config_db#(virtual memory_scheduler_if)::get(this,"","vif",vif))
        `uvm_error("memory_scheduler_test","Can't get vif from the config db")
    uvm_config_db#(virtual memory_scheduler_if)::set(this,"env","vif",vif);

 
	env = memory_scheduler_env::type_id::create("env", this);
    base_seq=memory_scheduler_base_sequence::type_id::create("base_seq");
    seq1=memory_scheduler_full_sequence::type_id::create("seq1");

  endfunction

  task run_phase(uvm_phase phase);
    super.run_phase(phase);
    phase.raise_objection(this);
    
    // Add run phase code here
    base_seq.start(env.agent.sqr);
    #200;
    seq1.start(env.agent.sqr);
    #200;

    phase.drop_objection(this);
  endtask

endclass
