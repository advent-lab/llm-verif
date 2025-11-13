`timescale 1ns / 1ps

module fixed_priority_arbiter_tb;

    localparam CLK_PERIOD = 10;

    // DUT Inputs
    reg clk;
    reg reset;
    reg [7:0] req;
    reg [7:0] priority_override;

    // DUT Outputs
    wire [7:0] grant;
    wire       valid;
    wire [2:0] grant_index;

    // Instantiate the DUT
    fixed_priority_arbiter dut (
        .clk(clk),
        .reset(reset),
        .req(req),
        .priority_override(priority_override),
        .grant(grant),
        .valid(valid),
        .grant_index(grant_index)
    );

    // Clock Generation
    always #(CLK_PERIOD / 2) clk = ~clk;

    // Apply Reset
    task apply_reset;
        begin
            reset = 1;
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
        string      label
    );
        begin
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
        req = 0;
        priority_override = 0;

        apply_reset;
        $display("RESET complete.\n");

        drive_stimulus(8'b00000100, 8'b0, "Stimulus 1: Single request");
        drive_stimulus(8'b00100110, 8'b0, "Stimulus 2: Multiple requests");
        drive_stimulus(8'b00100110, 8'b00010000, "Stimulus 3: Priority override active");
        drive_stimulus(8'b00000000, 8'b00000000, "Stimulus 4: No requests or override");
        drive_stimulus(8'b00001000, 8'b00000000, "Stimulus 5: Multiple requests");
        drive_stimulus(8'b00000010, 8'b00000000, "Stimulus 6: Single bit request");
        drive_stimulus(8'b00000001, 8'b00000000, "Stimulus 7: Lowest priority request");

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