

interface rgb_color_space_hsv_if();

//input/output signals
    logic  clk;
    logic  rst;
    logic  we;
    logic [7:0] waddr;
    logic [24:0] wdata;
    logic  valid_in;
    logic [7:0] r_component;
    logic [7:0] g_component;
    logic [7:0] b_component;
    logic [11:0] h_component;
    logic [12:0] s_component;
    logic [11:0] v_component;
    logic  valid_out;


    modport DUT (
    input clk, rst, we, waddr, wdata, valid_in, r_component, g_component, b_component,
    output h_component, s_component, v_component, valid_out
    );//design modport
    
endinterface //rgb_color_space_hsv design interface
