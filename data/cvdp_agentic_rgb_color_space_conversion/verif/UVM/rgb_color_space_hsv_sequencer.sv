
class rgb_color_space_hsv_sequencer extends uvm_sequencer #(rgb_color_space_hsv_seq_item);
    `uvm_component_utils(rgb_color_space_hsv_sequencer)

    function new(string name = "rgb_color_space_hsv_sequencer", uvm_component parent = null);
        super.new(name, parent);
    endfunction
endclass
