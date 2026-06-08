module alu_core #(
    parameter DATA_WIDTH = 32
)(
    input  logic [3:0]                         opcode,
    input  logic signed [DATA_WIDTH-1:0]       operand1,
    input  logic signed [DATA_WIDTH-1:0]       operand2,
    input  logic signed [DATA_WIDTH-1:0]       operand3,
    output logic signed [DATA_WIDTH-1:0]       result
);

function automatic signed [DATA_WIDTH-1:0] do_add(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_add = a + b + c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_sub(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_sub = a - b - c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_mul(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_mul = a * b * c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_div(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_div = a / b / c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_and(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_and = a & b & c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_or(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_or = a | b | c;
endfunction

function automatic signed [DATA_WIDTH-1:0] do_xor(
    input signed [DATA_WIDTH-1:0] a,
    input signed [DATA_WIDTH-1:0] b,
    input signed [DATA_WIDTH-1:0] c
);
    do_xor = a ^ b ^ c;
endfunction

always_comb begin
    result = 0;
    case (opcode)
        4'h0: result = do_add(operand1, operand2, operand3);
        4'h1: result = do_sub(operand1, operand2, operand3);
        4'h2: result = do_mul(operand1, operand2, operand3);
        4'h3: result = do_div(operand1, operand2, operand3);
        4'h4: result = do_and(operand1, operand2, operand3);
        4'h5: result = do_or(operand1, operand2, operand3);
        4'h6: result = do_xor(operand1, operand2, operand3);
        default: result = 0;
    endcase
end

endmodule