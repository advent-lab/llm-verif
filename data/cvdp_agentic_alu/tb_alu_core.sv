module tb_llm;
    // Parameters
    parameter DATA_WIDTH = 32;
    parameter CLK_PERIOD = 10;
    
    // Testbench signals
    logic [3:0]                         opcode;
    logic signed [DATA_WIDTH-1:0]       operand1;
    logic signed [DATA_WIDTH-1:0]       operand2;
    logic signed [DATA_WIDTH-1:0]       operand3;
    logic signed [DATA_WIDTH-1:0]       result;
    
    // Instantiate DUT
    alu_core #(
        .DATA_WIDTH(DATA_WIDTH)
    ) dut (
        .opcode(opcode),
        .operand1(operand1),
        .operand2(operand2),
        .operand3(operand3),
        .result(result)
    );
    
    // Functional Coverage
    covergroup cg_alu_advanced;
        
        // Cover all opcodes including invalid ones
        cp_opcode: coverpoint opcode {
            bins add = {4'h0};
            bins sub = {4'h1};
            bins mul = {4'h2};
            bins div = {4'h3};
            bins and_op = {4'h4};
            bins or_op = {4'h5};
            bins xor_op = {4'h6};
            bins invalid[] = {[4'h7:4'hF]};
        }
        
        // Cover operand1 with challenging corner cases
        cp_operand1: coverpoint operand1 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins almost_max_pos = {32'h7FFFFFFE};
            bins almost_max_neg = {32'h80000001};
            bins small_positive = {[2:100]};
            bins small_negative = {[-100:-2]};
            bins mid_positive = {[101:32'h3FFFFFFF]};
            bins mid_negative = {[32'hC0000000:-101]};
            bins power_of_2[] = {32'h1, 32'h2, 32'h4, 32'h8, 32'h10, 32'h20, 
                                  32'h40, 32'h80, 32'h100, 32'h200, 32'h400, 
                                  32'h800, 32'h1000, 32'h2000, 32'h4000, 32'h8000,
                                  32'h10000, 32'h20000, 32'h40000, 32'h80000,
                                  32'h100000, 32'h200000, 32'h400000, 32'h800000,
                                  32'h1000000, 32'h2000000, 32'h4000000, 32'h8000000,
                                  32'h10000000, 32'h20000000, 32'h40000000};
        }
        
        // Cover operand2 with challenging corner cases
        cp_operand2: coverpoint operand2 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins almost_max_pos = {32'h7FFFFFFE};
            bins almost_max_neg = {32'h80000001};
            bins small_positive = {[2:100]};
            bins small_negative = {[-100:-2]};
            bins mid_positive = {[101:32'h3FFFFFFF]};
            bins mid_negative = {[32'hC0000000:-101]};
            bins all_ones = {32'hFFFFFFFF};
        }
        
        // Cover operand3 with corner cases
        cp_operand3: coverpoint operand3 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins small_positive = {[2:100]};
            bins small_negative = {[-100:-2]};
            bins mid_range = {[101:32'h3FFFFFFF], [32'hC0000000:-101]};
        }
        
        // Cover result patterns
        cp_result: coverpoint result {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins positive = {[2:32'h7FFFFFFE]};
            bins negative = {[32'h80000001:-2]};
        }
        
        // Cross coverage: Arithmetic operations with overflow conditions
        cross_arith_overflow: cross cp_opcode, cp_operand1, cp_operand2 {
            // Only track ADD, SUB, MUL operations with extreme values
            ignore_bins non_arith = binsof(cp_opcode) intersect {[4'h3:4'hF]};
            ignore_bins normal_values = binsof(cp_operand1.small_positive) || 
                                         binsof(cp_operand1.small_negative) ||
                                         binsof(cp_operand2.small_positive) ||
                                         binsof(cp_operand2.small_negative);
        }
        
        // Cross coverage: Division corner cases (div by zero, div by one, div by -1)
        cross_div_corner: cross cp_opcode, cp_operand2, cp_operand3 {
            bins div_by_zero = binsof(cp_opcode.div) && binsof(cp_operand2.zero);
            bins div_by_one = binsof(cp_opcode.div) && binsof(cp_operand2.one);
            bins div_by_neg_one = binsof(cp_opcode.div) && binsof(cp_operand2.neg_one);
            bins div_max_by_zero = binsof(cp_opcode.div) && binsof(cp_operand2.zero);
            bins div_max_by_one = binsof(cp_opcode.div) && binsof(cp_operand2.one);
            // Only care about division opcode
            ignore_bins non_div = binsof(cp_opcode) intersect {[4'h0:4'h2], [4'h4:4'hF]};
        }
        
        // Cross coverage: Bitwise operations with specific patterns
        cross_bitwise_patterns: cross cp_opcode, cp_operand1, cp_operand2 {
            // AND operation with all combinations of 0, -1, max values
            bins and_zero_combinations = binsof(cp_opcode.and_op) && 
                                          (binsof(cp_operand1.zero) || binsof(cp_operand2.zero));
            bins and_all_ones = binsof(cp_opcode.and_op) && 
                                binsof(cp_operand2.all_ones);
            
            // XOR with same values (should give 0)
            bins xor_same_max_pos = binsof(cp_opcode.xor_op) && 
                                     binsof(cp_operand1.max_pos) && 
                                     binsof(cp_operand2.max_pos);
            bins xor_same_max_neg = binsof(cp_opcode.xor_op) && 
                                     binsof(cp_operand1.max_neg) && 
                                     binsof(cp_operand2.max_neg);
            
            // Only track bitwise operations
            ignore_bins non_bitwise = binsof(cp_opcode) intersect {[4'h0:4'h3], [4'h7:4'hF]};
        }
        
        // Cross coverage: All three operands with extremes
        cross_triple_operand: cross cp_operand1, cp_operand2, cp_operand3 {
            bins all_zero = binsof(cp_operand1.zero) && 
                            binsof(cp_operand2.zero) && 
                            binsof(cp_operand3.zero);
            bins all_max_pos = binsof(cp_operand1.max_pos) && 
                               binsof(cp_operand2.max_pos) && 
                               binsof(cp_operand3.max_pos);
            bins all_max_neg = binsof(cp_operand1.max_neg) && 
                               binsof(cp_operand2.max_neg) && 
                               binsof(cp_operand3.max_neg);
            bins all_one = binsof(cp_operand1.one) && 
                          binsof(cp_operand2.one) && 
                          binsof(cp_operand3.one);
            bins all_neg_one = binsof(cp_operand1.neg_one) && 
                              binsof(cp_operand2.neg_one) && 
                              binsof(cp_operand3.neg_one);
            bins mixed_max = binsof(cp_operand1.max_pos) && 
                            binsof(cp_operand2.max_neg) && 
                            binsof(cp_operand3.zero);
        }
        
        // Cross coverage: Operation sequences (checking result patterns per operation)
        cross_op_result: cross cp_opcode, cp_result {
            bins add_overflow_pos = binsof(cp_opcode.add) && binsof(cp_result.max_pos);
            bins add_overflow_neg = binsof(cp_opcode.add) && binsof(cp_result.max_neg);
            bins sub_overflow_pos = binsof(cp_opcode.sub) && binsof(cp_result.max_pos);
            bins sub_overflow_neg = binsof(cp_opcode.sub) && binsof(cp_result.max_neg);
            bins mul_zero = binsof(cp_opcode.mul) && binsof(cp_result.zero);
            bins div_zero = binsof(cp_opcode.div) && binsof(cp_result.zero);
            bins bitwise_zero = binsof(cp_opcode) intersect {4'h4, 4'h5, 4'h6} && 
                               binsof(cp_result.zero);
        }
        
        // Cross: Invalid opcodes with various operand combinations (for robustness)
        cross_invalid_ops: cross cp_opcode, cp_operand1 {
            ignore_bins valid_ops = binsof(cp_opcode) intersect {[4'h0:4'h6]};
            bins invalid_with_zero = binsof(cp_opcode.invalid) && binsof(cp_operand1.zero);
            bins invalid_with_max = binsof(cp_opcode.invalid) && 
                                    (binsof(cp_operand1.max_pos) || binsof(cp_operand1.max_neg));
        }
        
    endgroup
    
    // Additional covergroup for sign combinations
    covergroup cg_sign_combinations;
        cp_op1_sign: coverpoint operand1[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cp_op2_sign: coverpoint operand2[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cp_op3_sign: coverpoint operand3[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cp_result_sign: coverpoint result[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        // All sign combinations for three operands
        cross_all_signs: cross cp_op1_sign, cp_op2_sign, cp_op3_sign;
        
        // Sign transitions from inputs to result
        cross_sign_transition: cross cp_op1_sign, cp_op2_sign, cp_result_sign;
    endgroup
    
    // Create covergroup instances
    cg_alu_advanced cg_alu_inst = new();
    cg_sign_combinations cg_sign_inst = new();
    
    // Sample coverage
    always @(opcode or operand1 or operand2 or operand3 or result) begin
        cg_alu_inst.sample();
        cg_sign_inst.sample();
    end
    
    // BEGIN_STIMULUS
    initial begin
        // Stimulus goes here
        
        $finish;
    end
    // END_STIMULUS
    
endmodule
