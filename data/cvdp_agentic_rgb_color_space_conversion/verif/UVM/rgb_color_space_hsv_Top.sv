
module rgb_color_space_hsv_Top();
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // Interface instantiation
    rgb_color_space_hsv_if ifc();
    
    // DUT instantiation
    rgb_color_space_hsv  dut (
        .clk(ifc.clk),
        .rst(ifc.rst),
        .we(ifc.we),
        .waddr(ifc.waddr),
        .wdata(ifc.wdata),
        .valid_in(ifc.valid_in),
        .r_component(ifc.r_component),
        .g_component(ifc.g_component),
        .b_component(ifc.b_component),
        .h_component(ifc.h_component),
        .s_component(ifc.s_component),
        .v_component(ifc.v_component),
        .valid_out(ifc.valid_out)
    );

    // Clock and reset generation
    
    initial begin
        ifc.clk = 0;
        forever #5 ifc.clk = ~ifc.clk; // 100MHz clock
    end
    
    
    initial begin
        ifc.rst = 1;
        #100 ifc.rst = 0; // Reset for 100ns
    end
            

    // UVM configuration
    initial begin
        uvm_config_db#(virtual rgb_color_space_hsv_if)::set(null, "uvm_test_top", "vif", ifc);
        run_test("rgb_color_space_hsv_test");  
    end

    // Waveform recording
    initial begin
        $fsdbDumpfile("sim.fsdb");
        $fsdbDumpvars();
    end

endmodule
    
