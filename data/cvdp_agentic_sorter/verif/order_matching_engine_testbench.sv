`timescale 1ns/1ps
module order_matching_engine_testbench;

  //-------------------------------------------------------------------------
  // Parameter declarations
  //-------------------------------------------------------------------------
  parameter PRICE_WIDTH = 8;
  localparam NUM_ELEMS = 8;

  //-------------------------------------------------------------------------
  // DUT signal declarations
  //-------------------------------------------------------------------------
  reg                         clk;
  reg                         rst;
  reg                         start;
  reg [8*PRICE_WIDTH-1:0]     bid_orders;
  reg [8*PRICE_WIDTH-1:0]     ask_orders;
  wire                        match_valid;
  wire [PRICE_WIDTH-1:0]      matched_price;
  wire                        done;
  wire                        latency_error;

  int iter;

  //-------------------------------------------------------------------------
  // Instantiate the DUT
  //-------------------------------------------------------------------------
  order_matching_engine #(.PRICE_WIDTH(PRICE_WIDTH))
    dut (
      .clk(clk),
      .rst(rst),
      .start(start),
      .bid_orders(bid_orders),
      .ask_orders(ask_orders),
      .match_valid(match_valid),
      .matched_price(matched_price),
      .done(done),
      .latency_error(latency_error)
    );

  //-------------------------------------------------------------------------
  // Clock generation: 10 ns period
  //-------------------------------------------------------------------------
  initial begin
    clk = 0;
    forever #5 clk = ~clk;
  end

  //-------------------------------------------------------------------------
  // Waveform generation
  //-------------------------------------------------------------------------
  initial begin
    $dumpfile("order_matching_engine.vcd");
    $dumpvars(0, dut);
  end

  //-------------------------------------------------------------------------
  // Reset task: apply reset for a few cycles
  //-------------------------------------------------------------------------
  task apply_reset;
  begin
    @(posedge clk);
    rst = 1;
    @(posedge clk);
    rst = 0;
  end
  endtask

  //-------------------------------------------------------------------------
  // Function: pack_orders8
  // Packs 8 individual PRICE_WIDTH-bit orders into a flat vector.
  //-------------------------------------------------------------------------
  function automatic [8*PRICE_WIDTH-1:0] pack_orders8(
    input logic [PRICE_WIDTH-1:0] o0,
    input logic [PRICE_WIDTH-1:0] o1,
    input logic [PRICE_WIDTH-1:0] o2,
    input logic [PRICE_WIDTH-1:0] o3,
    input logic [PRICE_WIDTH-1:0] o4,
    input logic [PRICE_WIDTH-1:0] o5,
    input logic [PRICE_WIDTH-1:0] o6,
    input logic [PRICE_WIDTH-1:0] o7
  );
    pack_orders8 = {o7, o6, o5, o4, o3, o2, o1, o0};
  endfunction

  //-------------------------------------------------------------------------
  // Task: run_test
  // Only applies stimulus; prints input and output signals.
  //-------------------------------------------------------------------------
  task run_test(
    input [8*PRICE_WIDTH-1:0] bid_flat,
    input [8*PRICE_WIDTH-1:0] ask_flat
  );
    int latency_count;
  begin
    // Initialize inputs.
    rst        = 0;
    start      = 0;
    bid_orders = 0;
    ask_orders = 0;

    // Apply reset and drive inputs.
    apply_reset();

    bid_orders = bid_flat;
    ask_orders = ask_flat;

    // Print input stimulus.
    $display("Time %0t: Applying stimulus:", $time);
    $display("  bid_orders = %h", bid_orders);
    $display("  ask_orders = %h", ask_orders);

    // Issue the start pulse.
    @(posedge clk);
    start <= 1;
    @(posedge clk);
    start <= 0;

    // Wait until done is asserted, with a timeout of 50 cycles.
    latency_count = 0;
    while (done !== 1 && latency_count < 50) begin
      @(posedge clk);
      latency_count++;
    end

    if (done !== 1)
      $display("Warning: 'done' signal not asserted within 50 clock cycles.");

    // Print output signals.
    $display("Time %0t: DUT outputs:", $time);
    $display("  match_valid   = %b", match_valid);
    $display("  matched_price = %h", matched_price);
    $display("  done          = %b", done);
    $display("  latency_error = %b", latency_error);
    $display("  Latency counted = %0d clock cycles", latency_count);

    // Wait a few cycles before the next test.
    repeat(2) @(posedge clk);
  end
  endtask

  //-------------------------------------------------------------------------
  // Main test stimulus block.
  //-------------------------------------------------------------------------
  initial begin

    // Stimulus 1: Matching Scenario
    // Bid orders: [40,80,20,70,60,30,10,50]
    // Ask orders: [35,15,45,55,25,65,75,78]
    run_test(
      pack_orders8(40, 80, 20, 70, 60, 30, 10, 50),
      pack_orders8(35, 15, 45, 55, 25, 65, 75, 78)
    );

    // Stimulus 2: No Match Scenario
    // Bid orders: [10,20,30,40,50,60,70,75]
    // Ask orders: [80,90,95,85,88,82,91,87]
    run_test(
      pack_orders8(10, 20, 30, 40, 50, 60, 70, 75),
      pack_orders8(80, 90, 95, 85, 88, 82, 91, 87)
    );

    // Stimulus 3: Extreme Values
    // Bid orders: [0,0,0,0,0,0,0, MAX]
    // Ask orders: [MAX,MAX,MAX,MAX,MAX,MAX,MAX,MAX]
    run_test(
      pack_orders8(0, 0, 0, 0, 0, 0, 0, {PRICE_WIDTH{1'b1}}),
      pack_orders8({PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}},
                   {PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}}, {PRICE_WIDTH{1'b1}})
    );

    // Stimulus: 20 Random Test Cases
    for (iter = 0; iter < 20; iter = iter + 1) begin
      reg [PRICE_WIDTH-1:0] sb0, sb1, sb2, sb3, sb4, sb5, sb6, sb7;
      reg [PRICE_WIDTH-1:0] sa0, sa1, sa2, sa3, sa4, sa5, sa6, sa7;

      sb0 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb1 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb2 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb3 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb4 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb5 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb6 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sb7 = $urandom_range(0, {PRICE_WIDTH{1'b1}});

      sa0 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa1 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa2 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa3 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa4 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa5 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa6 = $urandom_range(0, {PRICE_WIDTH{1'b1}});
      sa7 = $urandom_range(0, {PRICE_WIDTH{1'b1}});

      run_test(
        pack_orders8(sb0, sb1, sb2, sb3, sb4, sb5, sb6, sb7),
        pack_orders8(sa0, sa1, sa2, sa3, sa4, sa5, sa6, sa7)
      );
    end

    $finish;
  end

endmodule