
//------------------------------------------------------------------------------
// Title: alu_core_test
// Description: UVM test for This is a description of alu_core_test.
//------------------------------------------------------------------------------

`include "uvm_macros.svh"

class alu_core_test extends uvm_test;
  `uvm_component_utils(alu_core_test)
  
  //Member variable declaration

  alu_core_env env;
  alu_core_base_sequence base_seq;
  alu_core_full_functional_sequence seq1;
  alu_core_full_functional_sequence seq2;

  virtual alu_core_if vif;


  function new(string name = "alu_core_test", uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Add build phase code here
	
	if(!uvm_config_db#(virtual alu_core_if)::get(this,"","vif",vif))
        `uvm_error("alu_core_test","Can't get vif from the config db")
    uvm_config_db#(virtual alu_core_if)::set(this,"env","vif",vif);

 
	env = alu_core_env::type_id::create("env", this);
    base_seq=alu_core_base_sequence::type_id::create("base_seq");
    seq1=alu_core_full_functional_sequence::type_id::create("seq1");
    seq2=alu_core_full_functional_sequence::type_id::create("seq2");

  endfunction

  task run_phase(uvm_phase phase);
    super.run_phase(phase);
    phase.raise_objection(this);
    
	// Add run phase code here
	base_seq.start(env.agent.sqr);
    #200;
    seq1.start(env.agent.sqr);
    #200;
    seq2.start(env.agent.sqr);
    #200;

    phase.drop_objection(this);
  endtask

endclass
