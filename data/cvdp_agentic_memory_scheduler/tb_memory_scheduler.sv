`timescale 1ns/1ps

module tb_llm;
    
    // Parameters
    parameter CLK_PERIOD = 10;
    
    // Testbench signals
    logic         clk;
    logic         reset;
    logic [3:0]   request;
    logic [7:0]   qos;
    logic [31:0]  address0;
    logic [31:0]  address1;
    logic [31:0]  address2;
    logic [31:0]  address3;
    logic [31:0]  mem_address;
    logic         mem_cmd_valid;
    logic [1:0]   mem_cmd_type;
    logic         mem_ack;
    logic [3:0]   grant;
    
    // Derived signals for coverage
    logic [1:0] qos0, qos1, qos2, qos3;
    assign qos0 = qos[1:0];
    assign qos1 = qos[3:2];
    assign qos2 = qos[5:4];
    assign qos3 = qos[7:6];
    
    // Instantiate DUT
    memory_scheduler dut (
        .clk(clk),
        .reset(reset),
        .request(request),
        .qos(qos),
        .address0(address0),
        .address1(address1),
        .address2(address2),
        .address3(address3),
        .mem_address(mem_address),
        .mem_cmd_valid(mem_cmd_valid),
        .mem_cmd_type(mem_cmd_type),
        .mem_ack(mem_ack),
        .grant(grant)
    );
    
    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end
    
    // ===========================================================================
    // FUNCTIONAL COVERAGE
    // ===========================================================================
    
    covergroup cg_scheduler_advanced @(posedge clk);
        option.cross_auto_bin_max = 0;  // ✅ DISABLE AUTO-GENERATED CROSS BINS
        
        // Cover all request patterns
        cp_request: coverpoint request {
            bins no_request = {4'b0000};
            bins single_req0 = {4'b0001};
            bins single_req1 = {4'b0010};
            bins single_req2 = {4'b0100};
            bins single_req3 = {4'b1000};
            bins two_req_adjacent[] = {4'b0011, 4'b0110, 4'b1100};
            bins two_req_nonadjacent[] = {4'b0101, 4'b1010, 4'b1001};
            bins three_req[] = {4'b0111, 4'b1011, 4'b1101, 4'b1110};
            bins all_req = {4'b1111};
        }
        
        // Cover grant patterns
        cp_grant: coverpoint grant {
            bins no_grant = {4'b0000};
            bins grant0 = {4'b0001};
            bins grant1 = {4'b0010};
            bins grant2 = {4'b0100};
            bins grant3 = {4'b1000};
        }
        
        // Cover individual QoS levels
        cp_qos0: coverpoint qos0 {
            bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11};
        }
        
        cp_qos1: coverpoint qos1 {
            bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11};
        }
        
        cp_qos2: coverpoint qos2 {
            bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11};
        }
        
        cp_qos3: coverpoint qos3 {
            bins prio[] = {2'b00, 2'b01, 2'b10, 2'b11};
        }
        
        // Cover QoS patterns
        cp_qos_combined: coverpoint qos {
            bins all_same_high = {8'b11_11_11_11};
            bins all_same_low = {8'b00_00_00_00};
            bins all_same_mid_low = {8'b01_01_01_01};
            bins all_same_mid_high = {8'b10_10_10_10};
            bins all_different = {8'b11_10_01_00, 8'b00_01_10_11};
            bins ascending = {8'b11_10_01_00};
            bins descending = {8'b00_01_10_11};
            bins alternating_high_low[] = {8'b11_00_11_00, 8'b00_11_00_11};
            bins two_high_two_low[] = {8'b11_11_00_00, 8'b00_00_11_11};
        }
        
        // Cover memory command valid
        cp_mem_cmd_valid: coverpoint mem_cmd_valid {
            bins inactive = {1'b0};
            bins active = {1'b1};
        }
        
        // Cover memory acknowledgment
        cp_mem_ack: coverpoint mem_ack {
            bins no_ack = {1'b0};
            bins ack = {1'b1};
        }
        
        // Cover address patterns
        cp_address: coverpoint mem_address {
            bins zero = {32'h00000000};
            bins low_range = {[32'h00000001:32'h000000FF]};
            bins aligned_4k = {32'h00001000, 32'h00002000, 32'h00003000};
            bins aligned_64k[] = {32'h00010000, 32'h00020000, 32'h00030000};
            bins high_address = {[32'hFFFF0000:32'hFFFFFFFF]};
            bins mid_range = {[32'h00010000:32'h7FFFFFFF]};
        }
        
        // Cross: Request with QoS
        cross_req_qos_prio: cross cp_request, cp_qos_combined {
            bins all_req_same_prio = binsof(cp_request.all_req) && 
                                      (binsof(cp_qos_combined.all_same_high) ||
                                       binsof(cp_qos_combined.all_same_low) ||
                                       binsof(cp_qos_combined.all_same_mid_low) ||
                                       binsof(cp_qos_combined.all_same_mid_high));
            bins all_req_diff_prio = binsof(cp_request.all_req) && 
                                      binsof(cp_qos_combined.all_different);
            ignore_bins no_contention = binsof(cp_request.no_request);
        }
        
        // Cross: Request with Grant
        cross_req_grant: cross cp_request, cp_grant {
            bins req0_grant0 = binsof(cp_request.single_req0) && binsof(cp_grant.grant0);
            bins req1_grant1 = binsof(cp_request.single_req1) && binsof(cp_grant.grant1);
            bins req2_grant2 = binsof(cp_request.single_req2) && binsof(cp_grant.grant2);
            bins req3_grant3 = binsof(cp_request.single_req3) && binsof(cp_grant.grant3);
            bins no_req_no_grant = binsof(cp_request.no_request) && binsof(cp_grant.no_grant);
        }
        
        // Cross: QoS with Grant (SIMPLIFIED to avoid explosion)
        cross_qos_grant_prio: cross cp_qos0, cp_qos1, cp_qos2, cp_qos3, cp_grant {
            // Same priority round-robin
            bins same_prio_rr = (binsof(cp_qos0.prio[3]) && binsof(cp_qos1.prio[3]) &&
                                 binsof(cp_qos2.prio[3]) && binsof(cp_qos3.prio[3])) &&
                                (binsof(cp_grant.grant0) || binsof(cp_grant.grant1) ||
                                 binsof(cp_grant.grant2) || binsof(cp_grant.grant3));
            
            // Req0 highest priority gets grant
            bins req0_highest = binsof(cp_qos0.prio[3]) && 
                                (binsof(cp_qos1.prio[0]) || binsof(cp_qos1.prio[1]) || binsof(cp_qos1.prio[2])) &&
                                binsof(cp_grant.grant0);
            
            // Req3 highest priority gets grant
            bins req3_highest = binsof(cp_qos3.prio[3]) && 
                                (binsof(cp_qos0.prio[0]) || binsof(cp_qos0.prio[1]) || binsof(cp_qos0.prio[2])) &&
                                binsof(cp_grant.grant3);
        }
        
        // Cross: Memory handshake
        cross_mem_handshake: cross cp_mem_cmd_valid, cp_mem_ack, cp_grant {
            bins valid_and_ack_with_grant = binsof(cp_mem_cmd_valid.active) && 
                                            binsof(cp_mem_ack.ack) &&
                                            (binsof(cp_grant.grant0) || binsof(cp_grant.grant1) ||
                                             binsof(cp_grant.grant2) || binsof(cp_grant.grant3));
            bins valid_no_ack = binsof(cp_mem_cmd_valid.active) && 
                                binsof(cp_mem_ack.no_ack);
            bins no_valid_with_ack = binsof(cp_mem_cmd_valid.inactive) && 
                                     binsof(cp_mem_ack.ack);
            bins idle_state = binsof(cp_mem_cmd_valid.inactive) && 
                              binsof(cp_mem_ack.no_ack) &&
                              binsof(cp_grant.no_grant);
        }
        
        // Cross: Grant with address
        cross_grant_address: cross cp_grant, cp_address {
            bins grant0_addr = binsof(cp_grant.grant0);
            bins grant1_addr = binsof(cp_grant.grant1);
            bins grant2_addr = binsof(cp_grant.grant2);
            bins grant3_addr = binsof(cp_grant.grant3);
            ignore_bins no_grant = binsof(cp_grant.no_grant);
        }
        
    endgroup
    
    // Covergroup for transitions
    covergroup cg_transitions @(posedge clk);
        option.cross_auto_bin_max = 0;  // ✅ DISABLE AUTO-GENERATED CROSS BINS
        
        cp_grant_trans: coverpoint grant {
            bins grant_rise_0 = (4'b0000 => 4'b0001);
            bins grant_rise_1 = (4'b0000 => 4'b0010);
            bins grant_rise_2 = (4'b0000 => 4'b0100);
            bins grant_rise_3 = (4'b0000 => 4'b1000);
            bins grant_fall_0 = (4'b0001 => 4'b0000);
            bins grant_fall_1 = (4'b0010 => 4'b0000);
            bins grant_fall_2 = (4'b0100 => 4'b0000);
            bins grant_fall_3 = (4'b1000 => 4'b0000);
            bins grant_switch_01 = (4'b0001 => 4'b0010);
            bins grant_switch_12 = (4'b0010 => 4'b0100);
            bins grant_switch_23 = (4'b0100 => 4'b1000);
            bins grant_switch_30 = (4'b1000 => 4'b0001);
        }
        
    endgroup
    
    // Covergroup for arbitration fairness
    covergroup cg_arbitration_fairness @(posedge clk iff (grant != 4'b0000));
        option.cross_auto_bin_max = 0;  // ✅ DISABLE AUTO-GENERATED CROSS BINS
        
        cp_granted_requestor: coverpoint grant {
            bins req0_served = {4'b0001};
            bins req1_served = {4'b0010};
            bins req2_served = {4'b0100};
            bins req3_served = {4'b1000};
        }
        
        cp_grant_sequence: coverpoint grant {
            bins rr_01 = (4'b0001 => 4'b0010);
            bins rr_12 = (4'b0010 => 4'b0100);
            bins rr_23 = (4'b0100 => 4'b1000);
            bins rr_30 = (4'b1000 => 4'b0001);
            bins rr_10 = (4'b0010 => 4'b0001);
            bins rr_21 = (4'b0100 => 4'b0010);
            bins rr_32 = (4'b1000 => 4'b0100);
            bins rr_03 = (4'b0001 => 4'b1000);
            bins skip_02 = (4'b0001 => 4'b0100);
            bins skip_13 = (4'b0010 => 4'b1000);
        }
        
    endgroup
    
    // Covergroup for edge cases
    covergroup cg_edge_cases @(posedge clk);
        option.cross_auto_bin_max = 0;  // ✅ DISABLE AUTO-GENERATED CROSS BINS
        
        cp_req_during_valid: coverpoint request iff (mem_cmd_valid) {
            bins req_present = {[4'b0001:4'b1111]};
            bins no_req_during_valid = {4'b0000};
        }
        
        cp_qos_during_valid: coverpoint qos iff (mem_cmd_valid) {
            bins qos_values = {[8'h00:8'hFF]};
        }
        
    endgroup
    
    // Instantiate covergroups
    cg_scheduler_advanced cg_sched_inst = new();
    cg_transitions cg_trans_inst = new();
    cg_arbitration_fairness cg_arb_inst = new();
    cg_edge_cases cg_edge_inst = new();
    
    // BEGIN_STIMULUS
    initial begin
	//ADD STIMULUS HERE
        $finish;
    end
    // END_STIMULUS
    
    // Timeout watchdog
    initial begin
        #100000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end
    
endmodule
