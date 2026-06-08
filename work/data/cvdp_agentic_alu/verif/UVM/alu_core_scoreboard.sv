
`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_expected)

//------------------------------------------------------------------------------
// Title: alu_core_scoreboard_example_2
// Description: This is a description of alu_core_scb_example.
//------------------------------------------------------------------------------

class alu_core_scoreboard extends uvm_scoreboard;
   `uvm_component_utils(alu_core_scoreboard)
    
    // Analysis ports (corrected naming)
    uvm_analysis_imp_actual #(alu_core_seq_item, alu_core_scoreboard) actual_imp;
    uvm_analysis_imp_expected #(alu_core_seq_item, alu_core_scoreboard) expected_imp;

    // Transaction queues
    alu_core_seq_item expected_queue[$];
    alu_core_seq_item actual_queue[$];


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
   function void write_actual(alu_core_seq_item actual);
        actual_queue.push_back(actual);
        check_pairs();
   endfunction


   // Required write method for expected results
   function void write_expected(alu_core_seq_item expected);
        expected_queue.push_back(expected);
        check_pairs();
   endfunction


   // Check matching transaction pairs
   function void check_pairs();
        // Compare transactions while both queues are non-empty
        while (expected_queue.size() > 0 && actual_queue.size() > 0) begin
            alu_core_seq_item expected = expected_queue.pop_front();
            alu_core_seq_item actual = actual_queue.pop_front();
            
            // Output signal to be compared: result
            // Before comparing, check if actual.result is X
            if (^actual.result === 1'bx) begin
                // If actual.result contains X, skip this comparison silently
                continue;
            end

            // If handshake signals (e.g., valid/ready) existed, would check here
            // No handshake signals in this design, so proceed

            total_checked++;

            // Field-by-field comparison of output signals (only result)
            if (actual.result === expected.result) begin
                match_count++;
                `uvm_info("SCB_MATCH", $sformatf(
                    "MATCH at time %0t: opcode=0x%0h op1=%0d op2=%0d op3=%0d result=%0d",
                    $time, actual.opcode, actual.operand1, actual.operand2, actual.operand3, actual.result
                ), UVM_LOW)
            end else begin
                mismatch_count++;
                `uvm_error("SCB_MISMATCH", $sformatf(
                    "MISMATCH at time %0t:\n  Inputs:   opcode=0x%0h op1=%0d op2=%0d op3=%0d\n  Expected: result=%0d\n  Actual:   result=%0d",
                    $time, actual.opcode, actual.operand1, actual.operand2, actual.operand3, expected.result, actual.result
                ))
            end
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
