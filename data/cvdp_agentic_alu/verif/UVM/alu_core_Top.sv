
module alu_core_Top();
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // Interface instantiation
    alu_core_if ifc();
    
    // DUT instantiation
    alu_core #(32) dut (
        .opcode(ifc.opcode),
        .operand1(ifc.operand1),
        .operand2(ifc.operand2),
        .operand3(ifc.operand3),
        .result(ifc.result)
    );

    // Clock and reset generation
    
    initial begin
        ifc.clk = 0;
        forever #5 ifc.clk = ~ifc.clk; // 100MHz clock
    end
    
    // No reset signal detected

    // UVM configuration
    initial begin
        uvm_config_db#(virtual alu_core_if)::set(null, "uvm_test_top", "vif", ifc);
        run_test("alu_core_test");  
    end

    // Waveform recording
    initial begin
        $fsdbDumpfile("sim.fsdb");
        $fsdbDumpvars();
    end

endmodule
    