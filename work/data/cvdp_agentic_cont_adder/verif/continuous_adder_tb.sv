`timescale 1ns/1ps

module tb_continuous_adder;

reg clk;
reg rst_n;
reg valid_in;
reg [31:0] data_in;
reg accumulate_enable;
reg flush;
wire [31:0] sum_out;
wire sum_valid;

continuous_adder #(
    .DATA_WIDTH(32),
    .ENABLE_THRESHOLD(1),
    .THRESHOLD(32'h00000010),
    .REGISTER_OUTPUT(1)
) dut (
    .clk(clk),
    .rst_n(rst_n),
    .valid_in(valid_in),
    .data_in(data_in),
    .accumulate_enable(accumulate_enable),
    .flush(flush),
    .sum_out(sum_out),
    .sum_valid(sum_valid)
);

always #5 clk = ~clk;

reg [31:0] expected_sum;
reg [31:0] expected_sum_delay;

initial begin
    clk = 0;
    rst_n = 0;
    valid_in = 0;
    data_in = 0;
    accumulate_enable = 0;
    flush = 0;
    expected_sum = 0;
    repeat(2) @(posedge clk);
    rst_n = 1;
    repeat(2) @(posedge clk);

    valid_in = 1; accumulate_enable = 1; data_in = 4; @(posedge clk);
    data_in = 8; @(posedge clk);
    data_in = 5; @(posedge clk);
    data_in = 7; @(posedge clk);
    valid_in = 0; accumulate_enable = 0; data_in = 0; @(posedge clk);
    flush = 1; @(posedge clk); flush = 0; @(posedge clk);
    $display("Time=%0t flush done, sum_out=%h sum_valid=%b", $time, sum_out, sum_valid);

    valid_in = 1; accumulate_enable = 1; data_in = 8; @(posedge clk);
    data_in = 10; @(posedge clk);
    data_in = 1; @(posedge clk);
    data_in = 5; @(posedge clk);
    data_in = 5; @(posedge clk);
    valid_in = 0; accumulate_enable = 0; data_in = 0; @(posedge clk);
    $display("Time=%0t second block done, sum_out=%h sum_valid=%b", $time, sum_out, sum_valid);

    //integer i;
    for (int i = 0; i < 10; i = i + 1) begin
        data_in = $random;
        valid_in = 1; accumulate_enable = 1; @(posedge clk);
    end
    valid_in = 0; data_in = 0; accumulate_enable = 0; @(posedge clk);
    flush = 1; @(posedge clk); flush = 0; @(posedge clk);
    $display("Time=%0t random block flush, sum_out=%h sum_valid=%b", $time, sum_out, sum_valid);

    $finish;
end

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        expected_sum <= 0;
    end else begin
        if (flush) begin
            expected_sum <= 0;
        end else if (valid_in && accumulate_enable) begin
            expected_sum <= expected_sum + data_in;
        end
    end
end

always @(posedge clk) begin
    // Capture expected_sum in a delay register to match the pipeline latency
    expected_sum_delay <= expected_sum;
    if (sum_valid) begin
        if (sum_out !== expected_sum_delay) begin
            $display("Mismatch at %0t: expected=%h got=%h", $time, expected_sum_delay, sum_out);
        end else begin
            $display("Match at %0t: sum=%h", $time, sum_out);
        end
    end
end

endmodule