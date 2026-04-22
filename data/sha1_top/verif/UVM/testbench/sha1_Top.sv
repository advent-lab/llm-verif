module sha1_Top();
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // Interface instantiation
    sha1_if ifc();
    
    // DUT instantiation
    sha1 dut (
        .clk        (ifc.clk),
        .reset_n    (ifc.reset_n),
        .cs         (ifc.cs),
        .we         (ifc.we),
        .address    (ifc.address),
        .write_data (ifc.write_data),
        .read_data  (ifc.read_data),
        .error      (ifc.error)
    );

    // Cov instantiation
    tb_llm cov_dut (
        .clk        (ifc.clk),
        .reset_n    (ifc.reset_n),
        .cs         (ifc.cs),
        .we         (ifc.we),
        .address    (ifc.address),
        .write_data (ifc.write_data),
        .read_data  (ifc.read_data),
        .error      (ifc.error)
    );


    // ------------------------------------------------------------------
    // Internal signal probes — wire DUT hierarchy into interface so the
    // monitor can sample them for the coverage subscriber.
    // These are read-only observational connections; no DUT ports change.
    // ------------------------------------------------------------------
    assign ifc.ready_reg        = dut.ready_reg;
    assign ifc.digest_valid_reg = dut.digest_valid_reg;
    assign ifc.fsm_state        = dut.core.sha1_ctrl_reg;
    assign ifc.round_ctr        = dut.core.round_ctr_reg;
    assign ifc.digest_reg       = dut.digest_reg;

    // Clock generation — 100MHz (10ns period)
    initial begin
        ifc.clk = 0;
        forever #5 ifc.clk = ~ifc.clk;
    end

    // Reset generation — held low for 100ns then released
    initial begin
        ifc.reset_n = 0;
        #100 ifc.reset_n = 1;
    end

    // UVM configuration and test launch
    initial begin
        uvm_config_db#(virtual sha1_if)::set(null, "uvm_test_top", "vif", ifc);
        run_test("sha1_test");
    end

endmodule
