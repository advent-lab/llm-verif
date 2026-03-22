module trng_Top();
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // Instantiate the interface
    trng_if ifc();

    trng dut (
        .clk            (ifc.clk),
        .reset_n        (ifc.reset_n),
        .avalanche_noise(ifc.avalanche_noise),
        .cs             (ifc.cs),
        .we             (ifc.we),
        .address        (ifc.address),
        .write_data     (ifc.write_data),
        .read_data      (ifc.read_data),
        .error          (ifc.error),
        .debug          (ifc.debug),
        .debug_update   (ifc.debug_update),
        .security_error (ifc.security_error)
    );

    tb_llm cov_dut (
        .clk            (ifc.clk),
        .reset_n        (ifc.reset_n),
        .avalanche_noise(ifc.avalanche_noise),
        .cs             (ifc.cs),
        .we             (ifc.we),
        .address        (ifc.address),
        .write_data     (ifc.write_data),
        .read_data      (ifc.read_data),
        .error          (ifc.error),
        .debug          (ifc.debug),
        .debug_update   (ifc.debug_update),
        .security_error (ifc.security_error)
    );

    // Clock generation - 100MHz clock
    initial begin
        ifc.clk = 0;
        forever #5 ifc.clk = ~ifc.clk;
    end

    // Reset generation - active low reset
    initial begin
        ifc.reset_n = 0;
        #100 ifc.reset_n = 1;
    end

    // UVM configuration and test execution
    initial begin
        uvm_config_db#(virtual trng_if)::set(null, "uvm_test_top", "vif", ifc);
        run_test("trng_test");
    end

    // FSDB dump for waveform viewing
    initial begin
        $fsdbDumpfile("sim.fsdb");
        $fsdbDumpMDA;
        $fsdbDumpvars();
    end

endmodule
