`timescale 1ns/1ps

module tb_llm;
    
    // Parameters
    parameter CLK_PERIOD = 10;
    
    // Testbench signals
    logic           clk;
    logic           reset_n;
    logic           cs;
    logic           we;
    logic  [7:0]    address;
    logic  [31:0]   write_data;
    logic  [31:0]   read_data;
    logic           error;
    
    // Derived signals for coverage
    logic ctrl_init, ctrl_next;
    logic status_ready, status_valid;
    
    // Instantiate DUT
    sha1 dut (
        .clk(clk),
        .reset_n(reset_n),
        .cs(cs),
        .we(we),
        .address(address),
        .write_data(write_data),
        .read_data(read_data),
        .error(error)
    );
    
    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end
    
    // Extract control bits
    always_comb begin
        ctrl_init = (address == 8'h08) && we && cs && write_data[0];
        ctrl_next = (address == 8'h08) && we && cs && write_data[1];
    end
    
    // ===========================================================================
    // FUNCTIONAL COVERAGE
    // ===========================================================================
    
    covergroup cg_sha1_interface @(posedge clk iff cs);
        option.cross_auto_bin_max = 0;
        
        cp_address: coverpoint address {
            bins name0 = {8'h00};
            bins name1 = {8'h01};
            bins version = {8'h02};
            bins ctrl = {8'h08};
            bins status = {8'h09};
            bins block_range[] = {[8'h10:8'h1F]};
            bins digest_range[] = {[8'h20:8'h24]};
            bins invalid_low = {[8'h03:8'h07]};
            bins invalid_mid = {[8'h0A:8'h0F]};
            bins invalid_high = {[8'h25:8'hFF]};
        }
        
        cp_write_enable: coverpoint we {
            bins read_op = {1'b0};
            bins write_op = {1'b1};
        }
        
        cp_write_data_ctrl: coverpoint write_data[1:0] iff (address == 8'h08 && we) {
            bins init_only = {2'b01};
            bins next_only = {2'b10};
            bins init_next = {2'b11};
            bins none = {2'b00};
        }
        
        cp_block_data: coverpoint write_data iff (address >= 8'h10 && address <= 8'h1F && we) {
            bins all_zero = {32'h00000000};
            bins all_ones = {32'hFFFFFFFF};
            bins alternating_01 = {32'hAAAAAAAA};
            bins alternating_10 = {32'h55555555};
            bins pattern_ff00 = {32'hFF00FF00};
            bins pattern_00ff = {32'h00FF00FF};
            bins low_range = {[32'h00000001:32'h0000FFFF]};
            bins mid_range = {[32'h00010000:32'h7FFFFFFF]};
            bins high_range = {[32'h80000000:32'hFFFFFFFE]};
        }
        
        cross_addr_op: cross cp_address, cp_write_enable {
            bins read_name = binsof(cp_address.name0) && binsof(cp_write_enable.read_op);
            bins read_version = binsof(cp_address.version) && binsof(cp_write_enable.read_op);
            bins read_status = binsof(cp_address.status) && binsof(cp_write_enable.read_op);
            bins write_ctrl = binsof(cp_address.ctrl) && binsof(cp_write_enable.write_op);
            bins write_block = binsof(cp_address.block_range) && binsof(cp_write_enable.write_op);
            bins read_block = binsof(cp_address.block_range) && binsof(cp_write_enable.read_op);
            bins read_digest = binsof(cp_address.digest_range) && binsof(cp_write_enable.read_op);
            
            ignore_bins write_readonly = binsof(cp_address) intersect {8'h00, 8'h01, 8'h02, 8'h09} &&
                                          binsof(cp_write_enable.write_op);
        }
        
        cross_ctrl_addr: cross cp_write_data_ctrl, cp_address {
            bins init_to_ctrl = binsof(cp_write_data_ctrl.init_only) && binsof(cp_address.ctrl);
            bins next_to_ctrl = binsof(cp_write_data_ctrl.next_only) && binsof(cp_address.ctrl);
            ignore_bins non_ctrl = !binsof(cp_address.ctrl);
        }
        
    endgroup
    
    covergroup cg_control_commands @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_ctrl_init: coverpoint ctrl_init {
            bins inactive = {1'b0};
            bins active = {1'b1};
        }
        
        cp_ctrl_next: coverpoint ctrl_next {
            bins inactive = {1'b0};
            bins active = {1'b1};
        }
        
        cp_ctrl_sequence: coverpoint {ctrl_init, ctrl_next} {
            bins init_cmd = {2'b10};
            bins next_cmd = {2'b01};
            bins idle = {2'b00};
            bins init_next_simul = {2'b11};
        }
        
        cp_cmd_transitions: coverpoint {ctrl_init, ctrl_next} {
            bins init_to_next = (2'b10 => 2'b01);
            bins next_to_next = (2'b01 => 2'b01);
            bins init_to_idle = (2'b10 => 2'b00);
            bins next_to_idle = (2'b01 => 2'b00);
            bins idle_to_init = (2'b00 => 2'b10);
            bins idle_to_next = (2'b00 => 2'b01);
        }
        
    endgroup
    
    covergroup cg_status @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_ready: coverpoint dut.ready_reg {
            bins not_ready = {1'b0};
            bins ready_state = {1'b1};
        }
        
        cp_digest_valid: coverpoint dut.digest_valid_reg {
            bins invalid = {1'b0};
            bins valid_state = {1'b1};
        }
        
        cp_ready_trans: coverpoint dut.ready_reg {
            bins ready_rise = (1'b0 => 1'b1);
            bins ready_fall = (1'b1 => 1'b0);
            bins stay_ready = (1'b1 => 1'b1);
            bins stay_busy = (1'b0 => 1'b0);
        }
        
        cp_valid_trans: coverpoint dut.digest_valid_reg {
            bins valid_rise = (1'b0 => 1'b1);
            bins valid_fall = (1'b1 => 1'b0);
            bins stay_valid = (1'b1 => 1'b1);
            bins stay_invalid = (1'b0 => 1'b0);
        }
        
        cross_ready_valid: cross cp_ready, cp_digest_valid {
            bins idle_no_digest = binsof(cp_ready.ready_state) && binsof(cp_digest_valid.invalid);
            bins busy_no_digest = binsof(cp_ready.not_ready) && binsof(cp_digest_valid.invalid);
            bins ready_with_digest = binsof(cp_ready.ready_state) && binsof(cp_digest_valid.valid_state);
            bins busy_digest_hold = binsof(cp_ready.not_ready) && binsof(cp_digest_valid.valid_state);
        }
        
    endgroup
    
    covergroup cg_core_fsm @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_fsm_state: coverpoint dut.core.sha1_ctrl_reg {
            bins idle_state = {2'b00};
            bins rounds_state = {2'b01};
            bins done_state = {2'b10};
            ignore_bins invalid_state_illegal = {2'b11};
        }
        
        cp_fsm_trans: coverpoint dut.core.sha1_ctrl_reg {
            bins idle_to_rounds = (2'b00 => 2'b01);
            bins rounds_to_done = (2'b01 => 2'b10);
            bins done_to_idle = (2'b10 => 2'b00);
            bins idle_to_idle = (2'b00 => 2'b00);
            bins rounds_to_rounds = (2'b01 => 2'b01);
        }
        
        cp_round_counter: coverpoint dut.core.round_ctr_reg {
            bins round_0 = {7'd0};
            bins rounds_1_19 = {[7'd1:7'd19]};
            bins rounds_20_39 = {[7'd20:7'd39]};
            bins rounds_40_59 = {[7'd40:7'd59]};
            bins rounds_60_78 = {[7'd60:7'd78]};
            bins round_79 = {7'd79};
        }
        
        cross_fsm_rounds: cross cp_fsm_state, cp_round_counter {
            bins idle_round0 = binsof(cp_fsm_state.idle_state) && binsof(cp_round_counter.round_0);
            bins rounds_early = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_1_19);
            bins rounds_mid1 = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_20_39);
            bins rounds_mid2 = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_40_59);
            bins rounds_late = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.rounds_60_78);
            bins rounds_last = binsof(cp_fsm_state.rounds_state) && binsof(cp_round_counter.round_79);
            bins done_any_round = binsof(cp_fsm_state.done_state);
            
            ignore_bins idle_nonzero = binsof(cp_fsm_state.idle_state) && 
                                        (!binsof(cp_round_counter.round_0));
        }
        
    endgroup
    
    covergroup cg_w_mem @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_w_counter: coverpoint dut.core.w_mem_inst.w_ctr_reg {
            bins initial_phase = {[7'd0:7'd15]};
            bins expansion_phase = {[7'd16:7'd79]};
        }
        
        cp_w_value: coverpoint dut.core.w_mem_inst.w {
            bins zero = {32'h00000000};
            bins all_ones = {32'hFFFFFFFF};
            bins low_val = {[32'h00000001:32'h7FFFFFFF]};
            bins high_val = {[32'h80000000:32'hFFFFFFFE]};
        }
        
    endgroup
    
    covergroup cg_digest @(posedge clk iff dut.digest_valid_reg);
        option.cross_auto_bin_max = 0;
        
        cp_digest_h0: coverpoint dut.digest_reg[159:128] {
            bins low_range = {[32'h00000000:32'h3FFFFFFF]};
            bins mid_low = {[32'h40000000:32'h7FFFFFFF]};
            bins mid_high = {[32'h80000000:32'hBFFFFFFF]};
            bins high_range = {[32'hC0000000:32'hFFFFFFFF]};
        }
        
        cp_digest_h4: coverpoint dut.digest_reg[31:0] {
            bins low_range = {[32'h00000000:32'h3FFFFFFF]};
            bins mid_low = {[32'h40000000:32'h7FFFFFFF]};
            bins mid_high = {[32'h80000000:32'hBFFFFFFF]};
            bins high_range = {[32'hC0000000:32'hFFFFFFFF]};
        }
        
    endgroup
    
    covergroup cg_errors @(posedge clk iff cs);
        option.cross_auto_bin_max = 0;
        
        cp_error_flag: coverpoint error {
            bins no_error = {1'b0};
            bins error_detected = {1'b1};
        }
        
        cp_error_addr: coverpoint address iff (error) {
            bins invalid_addrs = {[8'h03:8'h07], [8'h0A:8'h0F], [8'h25:8'hFF]};
        }
        
    endgroup
    
    covergroup cg_back_to_back @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_cs_pattern: coverpoint cs {
            bins active = {1'b1};
            bins inactive = {1'b0};
        }
        
        cp_we_pattern: coverpoint we {
            bins write_mode = {1'b1};
            bins read_mode = {1'b0};
        }
        
        cp_cs_transitions: coverpoint cs {
            bins cs_rise = (1'b0 => 1'b1);
            bins cs_fall = (1'b1 => 1'b0);
            bins cs_stay_high = (1'b1 => 1'b1);
            bins cs_stay_low = (1'b0 => 1'b0);
        }
        
    endgroup
    
    // Instantiate covergroups
    cg_sha1_interface cg_iface_inst;
    cg_control_commands cg_ctrl_inst;
    cg_status cg_status_inst;
    cg_core_fsm cg_fsm_inst;
    cg_w_mem cg_wmem_inst;
    cg_digest cg_digest_inst;
    cg_errors cg_error_inst;
    cg_back_to_back cg_b2b_inst;
    
    initial begin
        cg_iface_inst = new();
        cg_ctrl_inst = new();
        cg_status_inst = new();
        cg_fsm_inst = new();
        cg_wmem_inst = new();
        cg_digest_inst = new();
        cg_error_inst = new();
        cg_b2b_inst = new();
    end
    
    // ===========================================================================
    // HELPER TASKS
    // ===========================================================================
    
    task write_reg(input [7:0] addr, input [31:0] data);
        @(posedge clk);
        cs = 1;
        we = 1;
        address = addr;
        write_data = data;
        @(posedge clk);
        cs = 0;
        we = 0;
    endtask
    
    task read_reg(input [7:0] addr, output [31:0] data);
        @(posedge clk);
        cs = 1;
        we = 0;
        address = addr;
        @(posedge clk);
        data = read_data;
        cs = 0;
    endtask
    
    task load_block(input [511:0] block_data);
        integer i;
        for (i = 0; i < 16; i = i + 1) begin
            write_reg(8'h10 + i, block_data[511 - i*32 -: 32]);
        end
    endtask
    
    task wait_ready();
        logic [31:0] status;
        do begin
            read_reg(8'h09, status);
            @(posedge clk);
        end while (status[0] == 0);
    endtask
    
    task read_digest(output [159:0] digest);
        logic [31:0] word;
        read_reg(8'h20, word); digest[159:128] = word;
        read_reg(8'h21, word); digest[127:96] = word;
        read_reg(8'h22, word); digest[95:64] = word;
        read_reg(8'h23, word); digest[63:32] = word;
        read_reg(8'h24, word); digest[31:0] = word;
    endtask
    
    // BEGIN_STIMULUS
    initial begin
        //ADD STIMULUS HERE
        
        $finish;
    end
    // END_STIMULUS
    
    // Timeout watchdog
    initial begin
        #1000000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end
    
endmodule
