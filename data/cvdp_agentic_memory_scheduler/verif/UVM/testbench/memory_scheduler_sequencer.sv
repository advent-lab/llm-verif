
class memory_scheduler_sequencer extends uvm_sequencer #(memory_scheduler_seq_item);
    `uvm_component_utils(memory_scheduler_sequencer)

    function new(string name = "memory_scheduler_sequencer", uvm_component parent = null);
        super.new(name, parent);
    endfunction
endclass
