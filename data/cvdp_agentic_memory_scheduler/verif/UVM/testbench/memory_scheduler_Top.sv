
module memory_scheduler_Top();
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // Interface instantiation
    memory_scheduler_if ifc();
    
    // DUT instantiation
    memory_scheduler  dut (
        .clk(ifc.clk),
        .reset(ifc.reset),
        .request(ifc.request),
        .qos(ifc.qos),
        .address0(ifc.address0),
        .address1(ifc.address1),
        .address2(ifc.address2),
        .address3(ifc.address3),
        .mem_address(ifc.mem_address),
        .mem_cmd_valid(ifc.mem_cmd_valid),
        .mem_cmd_type(ifc.mem_cmd_type),
        .mem_ack(ifc.mem_ack),
        .grant(ifc.grant)
    );

    // Cov instantiation
    tb_llm  cov_dut (
        .clk(ifc.clk),
        .reset(ifc.reset),
        .request(ifc.request),
        .qos(ifc.qos),
        .address0(ifc.address0),
        .address1(ifc.address1),
        .address2(ifc.address2),
        .address3(ifc.address3),
        .mem_address(ifc.mem_address),
        .mem_cmd_valid(ifc.mem_cmd_valid),
        .mem_cmd_type(ifc.mem_cmd_type),
        .mem_ack(ifc.mem_ack),
        .grant(ifc.grant)
    );

    // Clock and reset generation
    
    initial begin
        ifc.clk = 0;
        forever #5 ifc.clk = ~ifc.clk; // 100MHz clock
    end
    
    
    initial begin
        ifc.reset = 1;
        #100 ifc.reset = 0; // Reset for 100ns
    end
            

    // UVM configuration
    initial begin
        uvm_config_db#(virtual memory_scheduler_if)::set(null, "uvm_test_top", "vif", ifc);
        run_test("memory_scheduler_test");  
    end

    // Waveform recording
    //initial begin
    //    $fsdbDumpfile("sim.fsdb");
    //    $fsdbDumpvars();
    //end

endmodule
    
