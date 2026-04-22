
`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_expected)

//------------------------------------------------------------------------------
// Title: memory_scheduler_scoreboard_example_2
// Description: This is a description of memory_scheduler_scb_example.
//------------------------------------------------------------------------------

class memory_scheduler_scoreboard extends uvm_scoreboard;
   `uvm_component_utils(memory_scheduler_scoreboard)
    
    // Analysis ports (corrected naming)
    uvm_analysis_imp_actual #(memory_scheduler_seq_item, memory_scheduler_scoreboard) actual_imp;
    uvm_analysis_imp_expected #(memory_scheduler_seq_item, memory_scheduler_scoreboard) expected_imp;

    // Transaction queues
    memory_scheduler_seq_item expected_queue[$];
    memory_scheduler_seq_item actual_queue[$];


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
   function void write_actual(memory_scheduler_seq_item actual);
        actual_queue.push_back(actual);
        check_pairs();
   endfunction


   // Required write method for expected results
   function void write_expected(memory_scheduler_seq_item expected);
        expected_queue.push_back(expected);
        check_pairs();
   endfunction


   // Check matching transaction pairs
   function void check_pairs();
        // Compare transactions in order, one by one
        while (expected_queue.size() > 0 && actual_queue.size() > 0) begin
            bit match = 1'b1;
            string mismatch_fields = "";
            string exp_str, act_str;
            string mismatch_detail = "";

            memory_scheduler_seq_item expected = expected_queue.pop_front();
            memory_scheduler_seq_item actual = actual_queue.pop_front();
            
            // Only compare when mem_cmd_valid is 1 (active), and skip if any output is X
            // Output signals: mem_cmd_valid, mem_cmd_type, mem_address, grant
            // Handshake: mem_cmd_valid (active high)
            // X-state check: any output signal is X, skip comparison

            // Check for X state in actual output signals
            if ($isunknown(actual.mem_cmd_valid) ||
                $isunknown(actual.mem_cmd_type)  ||
                $isunknown(actual.mem_address)   ||
                $isunknown(actual.grant)) begin
                // Skip this comparison, do not print
                continue;
            end

            // Only compare when mem_cmd_valid is 1
            if (actual.mem_cmd_valid !== 1'b1) begin
                // Skip this comparison, do not print
                continue;
            end

            // Compare mem_cmd_type
            if (actual.mem_cmd_type !== expected.mem_cmd_type) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, "mem_cmd_type; "};
                mismatch_detail = {mismatch_detail, $sformatf("  mem_cmd_type: expected=0x%0h actual=0x%0h\n", expected.mem_cmd_type, actual.mem_cmd_type)};
            end

            // Compare mem_address
            if (actual.mem_address !== expected.mem_address) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, "mem_address; "};
                mismatch_detail = {mismatch_detail, $sformatf("  mem_address: expected=0x%08h actual=0x%08h\n", expected.mem_address, actual.mem_address)};
            end

            // Compare grant
            if (actual.grant !== expected.grant) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, "grant; "};
                mismatch_detail = {mismatch_detail, $sformatf("  grant: expected=0x%0h actual=0x%0h\n", expected.grant, actual.grant)};
            end

            // Compare mem_cmd_valid (should both be 1 here)
            if (actual.mem_cmd_valid !== expected.mem_cmd_valid) begin
                match = 1'b0;
                mismatch_fields = {mismatch_fields, "mem_cmd_valid; "};
                mismatch_detail = {mismatch_detail, $sformatf("  mem_cmd_valid: expected=%0b actual=%0b\n", expected.mem_cmd_valid, actual.mem_cmd_valid)};
            end

            // If match, log info and increment match_count
            if (match) begin
                match_count++;
                `uvm_info("SCB_MATCH", $sformatf(
                    "MATCH @ %0t: Transaction matched.\n  Inputs: reset=%0b request=0x%0h qos=0x%0h address0=0x%08h address1=0x%08h address2=0x%08h address3=0x%08h mem_ack=%0b\n  Outputs: mem_cmd_valid=%0b mem_cmd_type=0x%0h mem_address=0x%08h grant=0x%0h",
                    $time,
                    actual.reset, actual.request, actual.qos,
                    actual.address0, actual.address1, actual.address2, actual.address3, actual.mem_ack,
                    actual.mem_cmd_valid, actual.mem_cmd_type, actual.mem_address, actual.grant
                ), UVM_LOW)
            end else begin
                mismatch_count++;
                `uvm_error("SCB_MISMATCH", $sformatf(
                    "MISMATCH @ %0t: Transaction mismatch detected!\n  Inputs: reset=%0b request=0x%0h qos=0x%0h address0=0x%08h address1=0x%08h address2=0x%08h address3=0x%08h mem_ack=%0b\n  Outputs:\n    Expected: mem_cmd_valid=%0b mem_cmd_type=0x%0h mem_address=0x%08h grant=0x%0h\n    Actual:   mem_cmd_valid=%0b mem_cmd_type=0x%0h mem_address=0x%08h grant=0x%0h\n  Mismatched fields: %s\n%s",
                    $time,
                    actual.reset, actual.request, actual.qos,
                    actual.address0, actual.address1, actual.address2, actual.address3, actual.mem_ack,
                    expected.mem_cmd_valid, expected.mem_cmd_type, expected.mem_address, expected.grant,
                    actual.mem_cmd_valid, actual.mem_cmd_type, actual.mem_address, actual.grant,
                    mismatch_fields, mismatch_detail
                ))
            end

            total_checked++;
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
