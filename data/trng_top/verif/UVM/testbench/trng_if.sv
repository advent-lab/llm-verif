// author: Zaki Ilyas
// data: 03/16/2026
// Description: This is the interface for the TRNG UVM testbench.

interface trng_if ();
    logic           clk;
    logic           reset_n;
    logic           avalanche_noise;
    logic           cs;
    logic           we;
    logic [11:0]    address;
    logic [31:0]    write_data;
    logic [31:0]    read_data;
    logic           error;
    logic [7:0]     debug;
    logic           debug_update;
    logic           security_error;

    modport dut (
        input clk, reset_n, avalanche_noise, cs, we, address, write_data,
        output read_data, error, debug, debug_update, security_error
    );

endinterface