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
    covergroup cg_alu_functional;
        option.cross_auto_bin_max = 0;
        
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
        
        cp_operand1: coverpoint operand1 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins small_positive = {[2:1000]};
            bins small_negative = {[-1000:-2]};
            bins normal = default;
        }
        
        cp_operand2: coverpoint operand2 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins small_vals = {[-1000:1000]};
            bins normal = default;
        }
        
        cp_operand3: coverpoint operand3 {
            bins zero = {0};
            bins one = {1};
            bins neg_one = {-1};
            bins max_pos = {32'h7FFFFFFF};
            bins max_neg = {32'h80000000};
            bins normal = default;
        }
        
        cp_result: coverpoint result {
            bins zero = {0};
            bins positive = {[1:32'h7FFFFFFF]};
            bins negative = {[32'h80000000:-1]};
        }
        
        // CROSS 1: Arithmetic overflow (11 explicit bins only)
        cross_arith_overflow: cross cp_opcode, cp_operand1, cp_operand2 {
            bins add_pos_overflow = binsof(cp_opcode.add) && 
                                    binsof(cp_operand1.max_pos) && 
                                    binsof(cp_operand2.max_pos);
            bins add_neg_overflow = binsof(cp_opcode.add) && 
                                    binsof(cp_operand1.max_neg) && 
                                    binsof(cp_operand2.max_neg);
            bins add_zero_case = binsof(cp_opcode.add) && 
                                binsof(cp_operand1.zero);
            
            bins sub_pos_overflow = binsof(cp_opcode.sub) && 
                                    binsof(cp_operand1.max_pos) && 
                                    binsof(cp_operand2.max_neg);
            bins sub_neg_overflow = binsof(cp_opcode.sub) && 
                                    binsof(cp_operand1.max_neg) && 
                                    binsof(cp_operand2.max_pos);
            bins sub_zero_case = binsof(cp_opcode.sub) && 
                                binsof(cp_operand1.zero);
            
            bins mul_pos_overflow = binsof(cp_opcode.mul) && 
                                    binsof(cp_operand1.max_pos) && 
                                    binsof(cp_operand2.max_pos);
            bins mul_neg_overflow = binsof(cp_opcode.mul) && 
                                    binsof(cp_operand1.max_neg) && 
                                    binsof(cp_operand2.max_neg);
            bins mul_mixed_overflow = binsof(cp_opcode.mul) && 
                                      binsof(cp_operand1.max_pos) && 
                                      binsof(cp_operand2.max_neg);
            bins mul_by_zero = binsof(cp_opcode.mul) && 
                              (binsof(cp_operand1.zero) || binsof(cp_operand2.zero));
            bins mul_by_one = binsof(cp_opcode.mul) && 
                             (binsof(cp_operand1.one) || binsof(cp_operand2.one));
        }
        
        // CROSS 2: Division corner cases (4 explicit bins only)
        cross_div_corner: cross cp_opcode, cp_operand2 {
            bins div_by_zero = binsof(cp_opcode.div) && binsof(cp_operand2.zero);
            bins div_by_one = binsof(cp_opcode.div) && binsof(cp_operand2.one);
            bins div_by_neg_one = binsof(cp_opcode.div) && binsof(cp_operand2.neg_one);
            bins div_by_max = binsof(cp_opcode.div) && 
                             (binsof(cp_operand2.max_pos) || binsof(cp_operand2.max_neg));
        }
        
        // CROSS 3: Bitwise operations (6 explicit bins only)
        cross_bitwise: cross cp_opcode, cp_operand1, cp_operand2 {
            bins and_with_zero = binsof(cp_opcode.and_op) && 
                                (binsof(cp_operand1.zero) || binsof(cp_operand2.zero));
            bins and_with_max = binsof(cp_opcode.and_op) && 
                               binsof(cp_operand1.max_pos) && 
                               binsof(cp_operand2.max_pos);
            
            bins or_with_zero = binsof(cp_opcode.or_op) && 
                               binsof(cp_operand1.zero) && 
                               binsof(cp_operand2.zero);
            bins or_with_max = binsof(cp_opcode.or_op) && 
                              (binsof(cp_operand1.max_pos) || binsof(cp_operand2.max_pos));
            
            bins xor_with_zero = binsof(cp_opcode.xor_op) && 
                                (binsof(cp_operand1.zero) || binsof(cp_operand2.zero));
            bins xor_with_same_max = binsof(cp_opcode.xor_op) && 
                                    binsof(cp_operand1.max_pos) && 
                                    binsof(cp_operand2.max_pos);
        }
        
        // CROSS 4: Operation results (15 explicit bins only)
        cross_op_result: cross cp_opcode, cp_result {
            bins add_zero_result = binsof(cp_opcode.add) && binsof(cp_result.zero);
            bins add_pos_result = binsof(cp_opcode.add) && binsof(cp_result.positive);
            bins add_neg_result = binsof(cp_opcode.add) && binsof(cp_result.negative);
            
            bins sub_zero_result = binsof(cp_opcode.sub) && binsof(cp_result.zero);
            bins sub_pos_result = binsof(cp_opcode.sub) && binsof(cp_result.positive);
            bins sub_neg_result = binsof(cp_opcode.sub) && binsof(cp_result.negative);
            
            bins mul_zero_result = binsof(cp_opcode.mul) && binsof(cp_result.zero);
            bins mul_pos_result = binsof(cp_opcode.mul) && binsof(cp_result.positive);
            bins mul_neg_result = binsof(cp_opcode.mul) && binsof(cp_result.negative);
            
            bins div_zero_result = binsof(cp_opcode.div) && binsof(cp_result.zero);
            bins div_pos_result = binsof(cp_opcode.div) && binsof(cp_result.positive);
            bins div_neg_result = binsof(cp_opcode.div) && binsof(cp_result.negative);
            
            bins and_zero_result = binsof(cp_opcode.and_op) && binsof(cp_result.zero);
            bins or_zero_result = binsof(cp_opcode.or_op) && binsof(cp_result.zero);
            bins xor_zero_result = binsof(cp_opcode.xor_op) && binsof(cp_result.zero);
        }
        
    endgroup
    
    // Sign combinations covergroup
    covergroup cg_sign_combinations;
        option.cross_auto_bin_max = 0;  
        
        cp_op1_sign: coverpoint operand1[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cp_op2_sign: coverpoint operand2[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cp_result_sign: coverpoint result[31] {
            bins positive = {1'b0};
            bins negative = {1'b1};
        }
        
        cross_sign_result: cross cp_op1_sign, cp_op2_sign, cp_result_sign {
            bins pos_pos_pos = binsof(cp_op1_sign.positive) && 
                              binsof(cp_op2_sign.positive) && 
                              binsof(cp_result_sign.positive);
            bins pos_neg_neg = binsof(cp_op1_sign.positive) && 
                              binsof(cp_op2_sign.negative) && 
                              binsof(cp_result_sign.negative);
            bins neg_pos_neg = binsof(cp_op1_sign.negative) && 
                              binsof(cp_op2_sign.positive) && 
                              binsof(cp_result_sign.negative);
            bins neg_neg_pos = binsof(cp_op1_sign.negative) && 
                              binsof(cp_op2_sign.negative) && 
                              binsof(cp_result_sign.positive);
        }
    endgroup
    
    // Create covergroup instances
    cg_alu_functional cg_func = new();
    cg_sign_combinations cg_sign = new();
    
    // Sample coverage
    always @(opcode or operand1 or operand2 or operand3 or result) begin
        cg_func.sample();
        cg_sign.sample();
    end
    
    // BEGIN_STIMULUS
    initial begin
        // Stimulus goes here
        
        $finish;
    end
    // END_STIMULUS
    
endmodule
