//`include "timescale.v"

`define VENDOR_FPGA
//`define VENDOR_XILINX
//`define VENDOR_ALTERA

module generic_dpram(
	// Generic synchronous dual-port RAM interface
	rclk, rrst, rce, oe, raddr, dout,
	wclk, wrst, wce, we, waddr, di
);

	//
	// Default address and data buses width
	//
	parameter aw = 5;  // number of bits in address-bus
	parameter dw = 16; // number of bits in data-bus

	//
	// Generic synchronous double-port RAM interface
	//
	// read port
	input           rclk;  // read clock, rising edge trigger
	input           rrst;  // read port reset, active high
	input           rce;   // read port chip enable, active high
	input           oe;	   // output enable, active high
	input  [aw-1:0] raddr; // read address
	output [dw-1:0] dout;  // data output

	// write port
	input          wclk;  // write clock, rising edge trigger
	input          wrst;  // write port reset, active high
	input          wce;   // write port chip enable, active high
	input          we;    // write enable, active high
	input [aw-1:0] waddr; // write address
	input [dw-1:0] di;    // data input

	//
	// Module body
	//

`ifdef VENDOR_FPGA
	//
	// Instantiation synthesizeable FPGA memory
	//
	// This code has been tested using LeonardoSpectrum and Synplicity.
	// The code correctly instantiates Altera EABs and Xilinx BlockRAMs.
	//
	reg [dw-1:0] mem [(1<<aw) -1:0]; // instantiate memory
	reg [aw-1:0] ra;                 // register read address

	// read operation
	always @(posedge rclk)
	  if (rce)
	    ra <= raddr;

	assign dout = mem[ra];

	// write operation
	always@(posedge wclk)
		if (we && wce)
			mem[waddr] <= di;

`else

`ifdef VENDOR_XILINX
	//
	// Instantiation of FPGA memory:
	//
	// Virtex/Spartan2 BlockRAMs
	//
	xilinx_ram_dp xilinx_ram(
		// read port
		.CLKA(rclk),
		.RSTA(rrst),
		.ENA(rce),
		.ADDRA(raddr),
		.DIA( {dw{1'b0}} ),
		.WEA(1'b0),
		.DOA(dout),

		// write port
		.CLKB(wclk),
		.RSTB(wrst),
		.ENB(wce),
		.ADDRB(waddr),
		.DIB(di),
		.WEB(we),
		.DOB()
	);

	defparam
		xilinx_ram.dwidth = dw,
		xilinx_ram.awidth = aw;

`else

`ifdef VENDOR_ALTERA
	//
	// Instantiation of FPGA memory:
	//
	// Altera FLEX/APEX EABs
	//
	altera_ram_dp altera_ram(
		// read port
		.rdclock(rclk),
		.rdclocken(rce),
		.rdaddress(raddr),
		.q(dout),

		// write port
		.wrclock(wclk),
		.wrclocken(wce),
		.wren(we),
		.wraddress(waddr),
		.data(di)
	);

	defparam
		altera_ram.dwidth = dw,
		altera_ram.awidth = aw;

`else

`ifdef VENDOR_ARTISAN

	//
	// Instantiation of ASIC memory:
	//
	// Artisan Synchronous Double-Port RAM (ra2sh)
	//
	art_hsdp #(dw, 1<<aw, aw) artisan_sdp(
		// read port
		.qa(dout),
		.clka(rclk),
		.cena(~rce),
		.wena(1'b1),
		.aa(raddr),
		.da( {dw{1'b0}} ),
		.oena(~oe),

		// write port
		.qb(),
		.clkb(wclk),
		.cenb(~wce),
		.wenb(~we),
		.ab(waddr),
		.db(di),
		.oenb(1'b1)
	);

`else

`ifdef VENDOR_AVANT

	//
	// Instantiation of ASIC memory:
	//
	// Avant! Asynchronous Two-Port RAM
	//
	avant_atp avant_atp(
		.web(~we),
		.reb(),
		.oeb(~oe),
		.rcsb(),
		.wcsb(),
		.ra(raddr),
		.wa(waddr),
		.di(di),
		.do(dout)
	);

`else

`ifdef VENDOR_VIRAGE

	//
	// Instantiation of ASIC memory:
	//
	// Virage Synchronous 2-port R/W RAM
	//
	virage_stp virage_stp(
		// read port
		.CLKA(rclk),
		.MEA(rce_a),
		.ADRA(raddr),
		.DA( {dw{1'b0}} ),
		.WEA(1'b0),
		.OEA(oe),
		.QA(dout),

		// write port
		.CLKB(wclk),
		.MEB(wce),
		.ADRB(waddr),
		.DB(di),
		.WEB(we),
		.OEB(1'b1),
		.QB()
	);

`else

	//
	// Generic dual-port synchronous RAM model
	//

	//
	// Generic RAM's registers and wires
	//
	reg	[dw-1:0]	mem [(1<<aw)-1:0]; // RAM content
	reg	[dw-1:0]	do_reg;            // RAM data output register

	//
	// Data output drivers
	//
	assign dout = (oe & rce) ? do_reg : {dw{1'bz}};

	// read operation
	always @(posedge rclk)
		if (rce)
          		do_reg <= (we && (waddr==raddr)) ? {dw{1'b x}} : mem[raddr];

	// write operation
	always @(posedge wclk)
		if (wce && we)
			mem[waddr] <= di;


	// Task prints range of memory
	// *** Remember that tasks are non reentrant, don't call this task in parallel for multiple instantiations.
	task print_ram;
	input [aw-1:0] start;
	input [aw-1:0] finish;
	integer rnum;
  	begin
    		for (rnum=start;rnum<=finish;rnum=rnum+1)
      			$display("Addr %h = %h",rnum,mem[rnum]);
  	end
	endtask

`endif // !VENDOR_VIRAGE
`endif // !VENDOR_AVANT
`endif // !VENDOR_ARTISAN
`endif // !VENDOR_ALTERA
`endif // !VENDOR_XILINX
`endif // !VENDOR_FPGA

endmodule

//
// Black-box modules
//

`ifdef VENDOR_ALTERA
	module altera_ram_dp(
		data,
		wraddress,
		rdaddress,
		wren,
		wrclock,
		wrclocken,
		rdclock,
		rdclocken,
		q) /* synthesis black_box */;

		parameter awidth = 7;
		parameter dwidth = 8;

		input [dwidth -1:0] data;
		input [awidth -1:0] wraddress;
		input [awidth -1:0] rdaddress;
		input               wren;
		input               wrclock;
		input               wrclocken;
		input               rdclock;
		input               rdclocken;
		output [dwidth -1:0] q;

		// synopsis translate_off
		// exemplar translate_off

		syn_dpram_rowr #(
			"UNUSED",
			dwidth,
			awidth,
			1 << awidth
		)
		altera_dpram_model (
			// read port
			.RdClock(rdclock),
			.RdClken(rdclocken),
			.RdAddress(rdaddress),
			.RdEn(1'b1),
			.Q(q),

			// write port
			.WrClock(wrclock),
			.WrClken(wrclocken),
			.WrAddress(wraddress),
			.WrEn(wren),
			.Data(data)
		);

		// exemplar translate_on
		// synopsis translate_on

	endmodule
`endif // VENDOR_ALTERA

`ifdef VENDOR_XILINX
	module xilinx_ram_dp (
		ADDRA,
		CLKA,
		ADDRB,
		CLKB,
		DIA,
		WEA,
		DIB,
		WEB,
		ENA,
		ENB,
		RSTA,
		RSTB,
		DOA,
		DOB) /* synthesis black_box */ ;

	parameter awidth = 7;
	parameter dwidth = 8;

	// port_a
	input               CLKA;
	input               RSTA;
	input               ENA;
	input [awidth-1:0]  ADDRA;
	input [dwidth-1:0]  DIA;
	input               WEA;
	output [dwidth-1:0] DOA;

	// port_b
	input               CLKB;
	input               RSTB;
	input               ENB;
	input [awidth-1:0]  ADDRB;
	input [dwidth-1:0]  DIB;
	input               WEB;
	output [dwidth-1:0] DOB;

	// insert simulation model


	// synopsys translate_off
	// exemplar translate_off

	C_MEM_DP_BLOCK_V1_0 #(
		awidth,
		awidth,
		1,
		1,
		"0",
		1 << awidth,
		1 << awidth,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		1,
		"",
		16,
		0,
		0,
		1,
		1,
		1,
		1,
		dwidth,
		dwidth)
	xilinx_dpram_model (
		.ADDRA(ADDRA),
		.CLKA(CLKA),
		.ADDRB(ADDRB),
		.CLKB(CLKB),
		.DIA(DIA),
		.WEA(WEA),
		.DIB(DIB),
		.WEB(WEB),
		.ENA(ENA),
		.ENB(ENB),
		.RSTA(RSTA),
		.RSTB(RSTB),
		.DOA(DOA),
		.DOB(DOB));

		// exemplar translate_on
		// synopsys translate_on

	endmodule
`endif // VENDOR_XILINX
