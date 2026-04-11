
class sha1_sequencer extends uvm_sequencer #(sha1_seq_item);
    `uvm_component_utils(sha1_sequencer)

    function new(string name = "sha1_sequencer", uvm_component parent = null);
        super.new(name, parent);
    endfunction
endclass
