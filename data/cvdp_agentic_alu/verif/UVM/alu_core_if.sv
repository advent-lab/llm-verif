

interface alu_core_if();

//input/output signals
    logic [3:0] opcode;
    logic [32)(inputlogic[3:0]opcode,inputlogicsigned[DATA_WIDTH-1:0]operand1,inputlogicsigned[DATA_WIDTH-1:0]operand2,inputlogicsigned[DATA_WIDTH-1:0]operand3,outputlogicsigned[DATA_WIDTH-1:0]result-1:0] operand1;
    logic [32)(inputlogic[3:0]opcode,inputlogicsigned[DATA_WIDTH-1:0]operand1,inputlogicsigned[DATA_WIDTH-1:0]operand2,inputlogicsigned[DATA_WIDTH-1:0]operand3,outputlogicsigned[DATA_WIDTH-1:0]result-1:0] operand2;
    logic [32)(inputlogic[3:0]opcode,inputlogicsigned[DATA_WIDTH-1:0]operand1,inputlogicsigned[DATA_WIDTH-1:0]operand2,inputlogicsigned[DATA_WIDTH-1:0]operand3,outputlogicsigned[DATA_WIDTH-1:0]result-1:0] operand3;
    logic [32)(inputlogic[3:0]opcode,inputlogicsigned[DATA_WIDTH-1:0]operand1,inputlogicsigned[DATA_WIDTH-1:0]operand2,inputlogicsigned[DATA_WIDTH-1:0]operand3,outputlogicsigned[DATA_WIDTH-1:0]result-1:0] result;
    logic  clk;


    modport DUT (
    input opcode, operand1, operand2, operand3, clk,
    output result
    );//design modport
    
endinterface //alu_core design interface
