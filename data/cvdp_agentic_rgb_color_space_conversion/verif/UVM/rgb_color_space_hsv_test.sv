
//------------------------------------------------------------------------------
// Title: rgb_color_space_hsv_test
// Description: UVM test for This is a description of rgb_color_space_hsv_test.
//------------------------------------------------------------------------------

`include "uvm_macros.svh"

class rgb_color_space_hsv_test extends uvm_test;
  `uvm_component_utils(rgb_color_space_hsv_test)
  
  //Member variable declaration

  rgb_color_space_hsv_env env;
  rgb_color_space_hsv_base_sequence base_seq;
  rgb_color_space_hsv_random_sequence seq1;
  rgb_color_space_hsv_directed_sequence seq2;

  virtual rgb_color_space_hsv_if vif;


  function new(string name = "rgb_color_space_hsv_test", uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Add build phase code here
	
	if(!uvm_config_db#(virtual rgb_color_space_hsv_if)::get(this,"","vif",vif))
        `uvm_error("rgb_color_space_hsv_test","Can't get vif from the config db")
    uvm_config_db#(virtual rgb_color_space_hsv_if)::set(this,"env","vif",vif);

 
	env = rgb_color_space_hsv_env::type_id::create("env", this);
    base_seq=rgb_color_space_hsv_base_sequence::type_id::create("base_seq");
    seq1=rgb_color_space_hsv_random_sequence::type_id::create("seq1");
    seq2=rgb_color_space_hsv_directed_sequence::type_id::create("seq2");

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
