`timescale 1ns / 1ps

module fixed_priority_arbiter_tb;

    localparam CLK_PERIOD = 10;

    // DUT Inputs
    reg clk;
    reg reset;
    reg enable;
    reg clear;
    reg [7:0] req;
    reg [7:0] priority_override;

    // DUT Outputs
    wire [7:0] grant;
    wire       valid;
    wire [2:0] grant_index;
    wire [2:0] active_grant;

    // Instantiate the DUT
    fixed_priority_arbiter dut (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .clear(clear),
        .req(req),
        .priority_override(priority_override),
        .grant(grant),
        .valid(valid),
        .grant_index(grant_index),
        .active_grant(active_grant)
    );

    // Clock Generation
    always #(CLK_PERIOD / 2) clk = ~clk;

    // Apply Reset
    task apply_reset;
        begin
            reset = 1;
            enable = 0;
            clear = 0;
            req = 0;
            priority_override = 0;
            #(2 * CLK_PERIOD);
            reset = 0;
        end
    endtask

    // Stimulus Generator
    task drive_stimulus(
        input [7:0] test_req,
        input [7:0] test_override,
        input       enable_i,
        input       clear_i,
        string      label
    );
        begin
            enable = enable_i;
            clear  = clear_i;
            req    = test_req;
            priority_override = test_override;

            #(CLK_PERIOD);
            $display(">>> %s", label);
        end
    endtask

    // Main Test Sequence
    initial begin
        // Init
        clk = 0;
        reset = 0;
        enable = 0;
        clear = 0;
        req = 0;
        priority_override = 0;

        apply_reset;
        $display("RESET complete.\n");

        drive_stimulus(8'b00000100, 8'b0, 1, 0, "Stimulus 1: Single request");
        drive_stimulus(8'b00100110, 8'b0, 1, 0, "Stimulus 2: Multiple requests");
        drive_stimulus(8'b00100110, 8'b00010000, 1, 0, "Stimulus 3: Priority override active");
        drive_stimulus(8'b00000000, 8'b00000000, 1, 0, "Stimulus 4: No requests or override");
        drive_stimulus(8'b00001000, 8'b00000000, 1, 1, "Stimulus 5: Clear signal asserted");
        drive_stimulus(8'b00000010, 8'b00000000, 0, 0, "Stimulus 6: Enable = 0 (arbiter disabled)");
        drive_stimulus(8'b00000001, 8'b00000000, 1, 0, "Stimulus 7: active_grant test");

        $display("Stimulus-only testbench completed.");
        #20;
        $finish;
    end

    // Optional waveform dump
    initial begin
        $dumpfile("fixed_priority_arbiter_tb.vcd");
        $dumpvars(0, fixed_priority_arbiter_tb);
    end

endmodule