`timescale 1ns/1ps

module tb_alu_core;
  parameter DATA_WIDTH = 32;
  reg [3:0] opcode;
  reg signed [DATA_WIDTH-1:0] operand1;
  reg signed [DATA_WIDTH-1:0] operand2;
  reg signed [DATA_WIDTH-1:0] operand3;
  wire signed [DATA_WIDTH-1:0] result;

  alu_core #(DATA_WIDTH) dut (
    .opcode(opcode),
    .operand1(operand1),
    .operand2(operand2),
    .operand3(operand3),
    .result(result)
  );

  initial begin
    opcode = 4'h0; operand1 = 10; operand2 = 5; operand3 = 2; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h0; operand1 = -1; operand2 = 1; operand3 = 0; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = 20; operand2 = 10; operand3 = 5; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = 0; operand2 = 0; operand3 = 0; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 2; operand2 = 3; operand3 = 4; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = -2; operand2 = -3; operand3 = 1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 100; operand2 = 5; operand3 = 2; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 50; operand2 = 2; operand3 = 5; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h4; operand1 = 16'hFFFF; operand2 = 16'h0FFF; operand3 = 16'h00FF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h4; operand1 = 1; operand2 = 3; operand3 = 7; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h5; operand1 = 16'hAAAA; operand2 = 16'h5555; operand3 = 16'hFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h5; operand1 = 1; operand2 = 4; operand3 = 8; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h6; operand1 = 16'hF0F0; operand2 = 16'h0F0F; operand3 = 16'hAAAA; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h6; operand1 = 2; operand2 = 1; operand3 = 3; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h0; operand1 = 100; operand2 = -50; operand3 = 25; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = -10; operand2 = -5; operand3 = 3; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 10; operand2 = 10; operand3 = 0; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = -100; operand2 = -5; operand3 = -2; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h4; operand1 = 32'hFFFFFFFF; operand2 = 32'h00000001; operand3 = 32'h00000002; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h5; operand1 = 32'hFFFFFFFF; operand2 = 32'h80000000; operand3 = 32'h7FFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);

    opcode = 4'h0; operand1 = 32'h7FFFFFFF; operand2 = 32'h7FFFFFFF; operand3 = 32'h7FFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = 32'h80000000; operand2 = 32'hFFFFFFFF; operand3 = 32'hFFFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 32'h00000000; operand2 = 32'h80000000; operand3 = 32'h00000000; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 100; operand2 = 1; operand3 = 0; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = -128; operand2 = -1; operand3 = -1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h4; operand1 = 32'hFFFFFFFF; operand2 = 32'hFFFFFFFF; operand3 = 32'hFFFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h5; operand1 = 32'h00000000; operand2 = 32'hFFFFFFFF; operand3 = 32'h00000001; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h6; operand1 = 32'h00000000; operand2 = 32'h00000000; operand3 = 32'h00000000; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 32'h7FFFFFFF; operand2 = 1; operand3 = 2; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = -1; operand2 = 32'h7FFFFFFF; operand3 = -1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h6; operand1 = 32'hF0F0F0F0; operand2 = 32'h0F0F0F0F; operand3 = 32'hFFFF0000; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h5; operand1 = 32'hAAAA5555; operand2 = 32'h0000FFFF; operand3 = 32'hFFFF0000; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h4; operand1 = 0; operand2 = 0; operand3 = 32'hFFFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 32'hFFFF0000; operand2 = -1; operand3 = -1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = 32'h7FFFFFFF; operand2 = -1; operand3 = 32'h7FFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h0; operand1 = 32'h80000000; operand2 = 32'h80000000; operand3 = 32'h80000000; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h1; operand1 = 32'h00000001; operand2 = 32'h00000001; operand3 = 32'h7FFFFFFF; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 32'h00000001; operand2 = 32'h00000001; operand3 = 1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 32'hFFFFFFFE; operand2 = 32'hFFFFFFFF; operand3 = 32'h2; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 1; operand2 = -1; operand3 = -1; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);

    repeat(30) begin
      opcode = $urandom_range(0,7);
      operand1 = $urandom;
      operand2 = $urandom;
      operand3 = $urandom;
      #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    end

    opcode = 4'h7; operand1 = 0; operand2 = 0; operand3 = 0; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h7; operand1 = -1; operand2 = -2; operand3 = -3; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h3; operand1 = 32'h00010000; operand2 = 32'h00000010; operand3 = 32'h00000001; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h2; operand1 = 32'h00000003; operand2 = 32'h00000003; operand3 = 32'h00000003; #1 $display("OP=%0h A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);

    opcode = 4'h0; operand1 = 12; operand2 = 10; operand3 = 3; #1 $display("OP=%0h -> setting 0, A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'hF; operand1 = 10; operand2 = 20; operand3 = 5; #1 $display("OP=%0h -> setting F, A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h8; operand1 = 30; operand2 = 40; operand3 = 50; #1 $display("OP=%0h -> setting 8, A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);
    opcode = 4'h0; operand1 = 15; operand2 = 15; operand3 = 15; #1 $display("OP=%0h -> setting 0, A=%0d B=%0d C=%0d OUT=%0d", opcode, operand1, operand2, operand3, result);

    $finish;
  end
endmodule