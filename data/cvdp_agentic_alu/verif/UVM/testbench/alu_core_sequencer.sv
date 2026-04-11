
class alu_core_sequencer extends uvm_sequencer #(alu_core_seq_item);
    `uvm_component_utils(alu_core_sequencer)

    function new(string name = "alu_core_sequencer", uvm_component parent = null);
        super.new(name, parent);
    endfunction
endclass
