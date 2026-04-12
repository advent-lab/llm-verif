
//------------------------------------------------------------------------------
// Title: rgb_color_space_hsv_scoreboard_example_2
// Description: This is a description of rgb_color_space_hsv_scb_example.
//------------------------------------------------------------------------------

`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_expected)

class rgb_color_space_hsv_scoreboard extends uvm_scoreboard;
   `uvm_component_utils(rgb_color_space_hsv_scoreboard)
    
    // Analysis ports (corrected naming)
    uvm_analysis_imp_actual #(rgb_color_space_hsv_seq_item, rgb_color_space_hsv_scoreboard) actual_imp;
    uvm_analysis_imp_expected #(rgb_color_space_hsv_seq_item, rgb_color_space_hsv_scoreboard) expected_imp;

    // Transaction queues
    rgb_color_space_hsv_seq_item expected_queue[$];
    rgb_color_space_hsv_seq_item actual_queue[$];


   int match_count = 0;
   int mismatch_count = 0;
   int total_checked = 0;

   real Pass_rate = 0.0;

   function new(string name, uvm_component parent);
        super.new(name, parent);
        actual_imp = new("actual_imp", this);
        expected_imp = new("expected_imp", this);
   endfunction

   
   // Required write method for actual DUT results
   function void write_actual(rgb_color_space_hsv_seq_item actual);
        actual_queue.push_back(actual);
        check_pairs();
   endfunction


   // Required write method for expected results
   function void write_expected(rgb_color_space_hsv_seq_item expected);
        expected_queue.push_back(expected);
        check_pairs();
   endfunction


   // Check matching transaction pairs
   function void check_pairs();
        while (expected_queue.size() > 0 && actual_queue.size() > 0) begin
            // Compare output fields
            bit match = 1'b1;
            string mismatch_fields = "";

            rgb_color_space_hsv_seq_item expected = expected_queue.pop_front();
            rgb_color_space_hsv_seq_item actual = actual_queue.pop_front();
            
            total_checked++;

            // ----------------- LLM Supplementation Begins -----------------
            // Only compare output signals, avoid using the 'compare' function.
            // Field-by-field comparison with exact mismatch identification.
            // If any output signal is X, skip this comparison without printing.
            // Only compare when handshake signals (valid_out) are active.
            // Otherwise, skip this comparison without printing.

            // Check for X state in output signals (actual)
            // Output signals: h_component, s_component, v_component, valid_out
            // Handshake: valid_out

            // Check for X in output signals
            if ($isunknown(actual.h_component) || $isunknown(actual.s_component) ||
                $isunknown(actual.v_component) || $isunknown(actual.valid_out)) begin
                // Skip comparison, do not print
                continue;
            end

            // Only compare when valid_out is asserted
            if (!actual.valid_out) begin
                // Skip comparison, do not print
                continue;
            end

            // Only compare when expected.valid_out is also asserted
            if (!expected.valid_out) begin
                // Skip comparison, do not print
                continue;
            end



            if (actual.h_component !== expected.h_component) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, $sformatf("h_component (exp=0x%0h, act=0x%0h) ", expected.h_component, actual.h_component)};
            end
            if (actual.s_component !== expected.s_component) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, $sformatf("s_component (exp=0x%0h, act=0x%0h) ", expected.s_component, actual.s_component)};
            end
            if (actual.v_component !== expected.v_component) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, $sformatf("v_component (exp=0x%0h, act=0x%0h) ", expected.v_component, actual.v_component)};
            end
            if (actual.valid_out !== expected.valid_out) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, $sformatf("valid_out (exp=%0b, act=%0b) ", expected.valid_out, actual.valid_out)};
            end

            if (match) begin
                match_count++;
                `uvm_info("SCB_MATCH", $sformatf("MATCH: Transaction #%0d\n  Input: rst=%0b we=%0b waddr=0x%0h wdata=0x%0h valid_in=%0b rgb=(%0d,%0d,%0d)\n  Output: h=0x%0h s=0x%0h v=0x%0h valid_out=%0b",
                    total_checked,
                    actual.rst, actual.we, actual.waddr, actual.wdata, actual.valid_in,
                    actual.r_component, actual.g_component, actual.b_component,
                    actual.h_component, actual.s_component, actual.v_component, actual.valid_out
                ), UVM_LOW)
            end else begin
                mismatch_count++;
                `uvm_error("SCB_MISMATCH", $sformatf(
                    "MISMATCH: Transaction #%0d\n  Input: rst=%0b we=%0b waddr=0x%0h wdata=0x%0h valid_in=%0b rgb=(%0d,%0d,%0d)\n  Expected Output: h=0x%0h s=0x%0h v=0x%0h valid_out=%0b\n  Actual Output:   h=0x%0h s=0x%0h v=0x%0h valid_out=%0b\n  Mismatch Fields: %s\n  Timestamp: %0t",
                    total_checked,
                    actual.rst, actual.we, actual.waddr, actual.wdata, actual.valid_in,
                    actual.r_component, actual.g_component, actual.b_component,
                    expected.h_component, expected.s_component, expected.v_component, expected.valid_out,
                    actual.h_component, actual.s_component, actual.v_component, actual.valid_out,
                    mismatch_fields, $time
                ))
            end
            // ----------------- LLM Supplementation Ends -----------------
        end
   endfunction

 
   function void report_phase(uvm_phase phase);
        total_checked = mismatch_count + match_count;
        if (total_checked > 0) begin
            Pass_rate = match_count / real'(total_checked) * 100.0;
        end

        `uvm_info("SCB", "----------------------------------------", UVM_NONE)
        `uvm_info("SCB", "SCOREBOARD SUMMARY", UVM_NONE)
        `uvm_info("SCB", $sformatf("Total checked:  %0d", total_checked), UVM_NONE)
        `uvm_info("SCB", $sformatf("Matches:        %0d", match_count), UVM_NONE)
        `uvm_info("SCB", $sformatf("Mismatches:     %0d", mismatch_count), UVM_NONE)
        `uvm_info("SCB", $sformatf("Pass_rate:     %.2f%%", Pass_rate), UVM_NONE)

        if (mismatch_count > 0) begin
           $write("%c[7;31m", 27);
           $display("TEST FAILED");
           $write("%c[0m", 27);
        end else begin
           $write("%c[7;32m", 27);
           $display("TEST PASSED");
           $write("%c[0m", 27);
        end

   endfunction

endclass
