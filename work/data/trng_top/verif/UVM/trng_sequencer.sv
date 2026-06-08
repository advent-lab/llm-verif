class trng_sequencer extends uvm_sequencer#(trng_seq_item);
    `uvm_component_utils(trng_sequencer)

    function new(string name = "trng_sequencer", uvm_component parent = null);
        super.new(name, parent);
    endfunction
endclass : trng_sequencer