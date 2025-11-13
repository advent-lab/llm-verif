`timescale 1ns / 1ps

module nontrivial_mips_simple_tb();

    // Clock and reset
    reg aclk;
    reg aresetn;

    // Interrupt
    reg [6:0] ext_int;

    // AXI AR (Read Address) Channel
    wire [3:0] arid;
    wire [31:0] araddr;
    wire [3:0] arlen;
    wire [2:0] arsize;
    wire [1:0] arburst;
    wire [1:0] arlock;
    wire [3:0] arcache;
    wire [2:0] arprot;
    wire arvalid;
    reg arready;

    // AXI R (Read Data) Channel
    reg [3:0] rid;
    reg [31:0] rdata;
    reg [1:0] rresp;
    reg rlast;
    reg rvalid;
    wire rready;

    // AXI AW (Write Address) Channel
    wire [3:0] awid;
    wire [31:0] awaddr;
    wire [3:0] awlen;
    wire [2:0] awsize;
    wire [1:0] awburst;
    wire [1:0] awlock;
    wire [3:0] awcache;
    wire [2:0] awprot;
    wire awvalid;
    reg awready;

    // AXI W (Write Data) Channel
    wire [3:0] wid;
    wire [31:0] wdata;
    wire [3:0] wstrb;
    wire wlast;
    wire wvalid;
    reg wready;

    // AXI B (Write Response) Channel
    reg [3:0] bid;
    reg [1:0] bresp;
    reg bvalid;
    wire bready;

    // Debug signals
    wire [31:0] debug_wb_pc;
    wire [3:0] debug_wb_rf_wen;
    wire [4:0] debug_wb_rf_wnum;
    wire [31:0] debug_wb_rf_wdata;

    // DUT instantiation
    mycpu_top #(
        .BUS_WIDTH(4)
    ) dut (
        .aclk(aclk),
        .aresetn(aresetn),
        .ext_int(ext_int),
        // AR
        .arid(arid),
        .araddr(araddr),
        .arlen(arlen),
        .arsize(arsize),
        .arburst(arburst),
        .arlock(arlock),
        .arcache(arcache),
        .arprot(arprot),
        .arvalid(arvalid),
        .arready(arready),
        // R
        .rid(rid),
        .rdata(rdata),
        .rresp(rresp),
        .rlast(rlast),
        .rvalid(rvalid),
        .rready(rready),
        // AW
        .awid(awid),
        .awaddr(awaddr),
        .awlen(awlen),
        .awsize(awsize),
        .awburst(awburst),
        .awlock(awlock),
        .awcache(awcache),
        .awprot(awprot),
        .awvalid(awvalid),
        .awready(awready),
        // W
        .wid(wid),
        .wdata(wdata),
        .wstrb(wstrb),
        .wlast(wlast),
        .wvalid(wvalid),
        .wready(wready),
        // B
        .bid(bid),
        .bresp(bresp),
        .bvalid(bvalid),
        .bready(bready),
        // Debug
        .debug_wb_pc(debug_wb_pc),
        .debug_wb_rf_wen(debug_wb_rf_wen),
        .debug_wb_rf_wnum(debug_wb_rf_wnum),
        .debug_wb_rf_wdata(debug_wb_rf_wdata)
    );

    // Clock generation - 10ns period (100MHz)
    initial begin
        aclk = 0;
        forever #5 aclk = ~aclk;
    end

    // Simple memory model for AXI responses
    reg [31:0] mem [0:1023];
    integer read_count;
    integer write_count;

    // Initialize memory with simple test pattern
    initial begin
        integer i;
        for (i = 0; i < 1024; i = i + 1) begin
            mem[i] = 32'h00000000; // NOP instruction
        end
        // Put a simple instruction sequence at reset vector (0xBFC00000 maps to mem[0])
        mem[0] = 32'h3c01bfc0; // lui $1, 0xbfc0
        mem[1] = 32'h34210000; // ori $1, $1, 0x0000
        mem[2] = 32'h00000000; // nop
        mem[3] = 32'h00000000; // nop
    end

    // AXI Read Address Channel Handler
    always @(posedge aclk) begin
        if (!aresetn) begin
            arready <= 0;
            read_count <= 0;
        end else begin
            if (arvalid && !arready) begin
                arready <= 1;
            end else begin
                arready <= 0;
            end
        end
    end

    // AXI Read Data Channel Handler
    always @(posedge aclk) begin
        if (!aresetn) begin
            rvalid <= 0;
            rdata <= 0;
            rid <= 0;
            rresp <= 0;
            rlast <= 0;
        end else begin
            if (arvalid && arready) begin
                // Simple read response - return data from memory
                rid <= arid;
                rdata <= mem[araddr[11:2]]; // Word-aligned access
                rresp <= 2'b00; // OKAY
                rlast <= 1;
                rvalid <= 1;
                read_count <= read_count + 1;
            end else if (rvalid && rready) begin
                rvalid <= 0;
            end
        end
    end

    // AXI Write Address Channel Handler
    always @(posedge aclk) begin
        if (!aresetn) begin
            awready <= 0;
            write_count <= 0;
        end else begin
            if (awvalid && !awready) begin
                awready <= 1;
            end else begin
                awready <= 0;
            end
        end
    end

    // AXI Write Data Channel Handler
    always @(posedge aclk) begin
        if (!aresetn) begin
            wready <= 0;
        end else begin
            if (wvalid && !wready) begin
                wready <= 1;
                // Write to memory
                if (awvalid || awready)
                    mem[awaddr[11:2]] <= wdata;
            end else begin
                wready <= 0;
            end
        end
    end

    // AXI Write Response Channel Handler
    always @(posedge aclk) begin
        if (!aresetn) begin
            bvalid <= 0;
            bid <= 0;
            bresp <= 0;
        end else begin
            if (wvalid && wready && !bvalid) begin
                bid <= awid;
                bresp <= 2'b00; // OKAY
                bvalid <= 1;
                write_count <= write_count + 1;
            end else if (bvalid && bready) begin
                bvalid <= 0;
            end
        end
    end

    // Test stimulus
    initial begin
        // Initialize
        aresetn = 0;
        ext_int = 7'b0;

        // Wait for some time then release reset
        #100;
        aresetn = 1;

        // Run simulation for a while
        #10000;

        // Display some statistics
        $display("=================================================");
        $display("Simulation completed successfully");
        $display("Read transactions: %0d", read_count);
        $display("Write transactions: %0d", write_count);
        $display("=================================================");

        $finish;
    end

    // Timeout watchdog
    initial begin
        #50000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end

endmodule
