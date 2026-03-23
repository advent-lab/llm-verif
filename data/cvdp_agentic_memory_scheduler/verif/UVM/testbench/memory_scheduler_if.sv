

interface memory_scheduler_if();

//input/output signals
    logic  clk;
    logic  reset;
    logic [3:0] request;
    logic [7:0] qos;
    logic [31:0] address0;
    logic [31:0] address1;
    logic [31:0] address2;
    logic [31:0] address3;
    logic [31:0] mem_address;
    logic  mem_cmd_valid;
    logic [1:0] mem_cmd_type;
    logic  mem_ack;
    logic [3:0] grant;


    modport DUT (
    input clk, reset, request, qos, address0, address1, address2, address3, mem_ack,
    output mem_address, mem_cmd_valid, mem_cmd_type, grant
    );//design modport
    
endinterface //memory_scheduler design interface
