`timescale 1ns/1ps

module memory_scheduler_tb;

    logic         clk;
    logic         reset;
    logic [3:0]   request;
    logic [7:0]   qos;
    logic [31:0]  address0;
    logic [31:0]  address1;
    logic [31:0]  address2;
    logic [31:0]  address3;
    wire  [31:0]  mem_address;
    wire          mem_cmd_valid;
    wire  [1:0]   mem_cmd_type;
    logic         mem_ack;
    wire  [3:0]   grant;

    // DUT instantiation
    memory_scheduler dut (
        .clk(clk),
        .reset(reset),
        .request(request),
        .qos(qos),
        .address0(address0),
        .address1(address1),
        .address2(address2),
        .address3(address3),
        .mem_address(mem_address),
        .mem_cmd_valid(mem_cmd_valid),
        .mem_cmd_type(mem_cmd_type),
        .mem_ack(mem_ack),
        .grant(grant)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        // Initialize
        reset = 1;
        request = 4'b0000;
        qos = 8'h00;
        address0 = 32'h1000;
        address1 = 32'h2000;
        address2 = 32'h3000;
        address3 = 32'h4000;
        mem_ack = 0;

        #20;
        reset = 0;
        #20;

        // Test request from port 0 with high QoS
        @(posedge clk);
        request = 4'b0001;
        qos = 8'h03;  // QoS[1:0] = 3 (highest for port 0)

        #20;
        @(posedge clk);
        mem_ack = 1;
        @(posedge clk);
        mem_ack = 0;

        // Multiple requests with different QoS
        @(posedge clk);
        request = 4'b1111;  // All ports requesting
        qos = 8'b11_10_01_00;  // Different QoS levels

        #30;
        @(posedge clk);
        mem_ack = 1;
        @(posedge clk);
        mem_ack = 0;

        // Single request from port 2
        @(posedge clk);
        request = 4'b0100;
        qos = 8'b00_10_00_00;

        #20;
        @(posedge clk);
        mem_ack = 1;
        @(posedge clk);
        mem_ack = 0;

        // Random requests
        repeat(10) begin
            @(posedge clk);
            request = $random & 4'hF;
            qos = $random;
            address0 = $random;
            address1 = $random;
            address2 = $random;
            address3 = $random;

            #10;
            if (mem_cmd_valid) begin
                @(posedge clk);
                mem_ack = 1;
                @(posedge clk);
                mem_ack = 0;
            end
        end

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t reset=%b request=%b qos=%h grant=%b mem_valid=%b mem_addr=%h mem_ack=%b",
                 $time, reset, request, qos, grant, mem_cmd_valid, mem_address, mem_ack);
    end

endmodule
