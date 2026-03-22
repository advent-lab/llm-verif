
//------------------------------------------------------------------------------
// Title: sha1_test
// Description: UVM test for This is a description of sha1_test.
//------------------------------------------------------------------------------

`include "uvm_macros.svh"

class sha1_test extends uvm_test;
  `uvm_component_utils(sha1_test)
  
  //Member variable declaration

  sha1_env env;
  sha1_base_sequence base_seq;
  sha1_random_sequence seq1;
  sha1_directed_sequence seq2;

  virtual sha1_if vif;


  function new(string name = "sha1_test", uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Add build phase code here
	
	if(!uvm_config_db#(virtual sha1_if)::get(this,"","vif",vif))
        `uvm_error("sha1_test","Can't get vif from the config db")
    uvm_config_db#(virtual sha1_if)::set(this,"env","vif",vif);

 
	env = sha1_env::type_id::create("env", this);
    base_seq=sha1_base_sequence::type_id::create("base_seq");
    seq1=sha1_random_sequence::type_id::create("seq1");
    seq2=sha1_directed_sequence::type_id::create("seq2");

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
