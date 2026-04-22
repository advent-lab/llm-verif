import uvm_pkg::*;
`include "uvm_macros.svh"

// Sequence base class for memory_scheduler
class memory_scheduler_base_sequence extends uvm_sequence #(memory_scheduler_seq_item);
  `uvm_object_utils(memory_scheduler_base_sequence)

  function new(string name = "memory_scheduler_base_sequence");
    super.new(name);
  endfunction

  // Basic functional sequence: single transaction with legal values
  virtual task body();
    memory_scheduler_seq_item seq_item;
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    // Assign a basic legal transaction (single requester active, all QoS = 0)
    assert(seq_item.randomize() with {
      request    == 4'b0001;
      qos        == 8'b00000000;
      address0   == 32'hA5A5A5A5;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item);
    finish_item(seq_item);
  endtask
endclass

// Full functional and directed sequence for memory_scheduler
class memory_scheduler_full_sequence extends memory_scheduler_base_sequence;
  `uvm_object_utils(memory_scheduler_full_sequence)

  function new(string name = "memory_scheduler_full_sequence");
    super.new(name);
  endfunction

  virtual task body();
    memory_scheduler_seq_item seq_item;
    int i;

    // 1. Directed-value tests from testcase.txt (compliant only)
    // FUNC_SINGLE_REQ
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0001;
      qos        == 8'b00000000;
      address0   == 32'hA5A5A5A5;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_MULTI_REQ_DIFF_QOS
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1101;
      qos        == 8'b11010001;
      address0   == 32'h11111111;
      address1   == 32'h22222222;
      address2   == 32'h33333333;
      address3   == 32'h44444444;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_MULTI_REQ_NO_QOS_MATCH
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1010;
      qos        == 8'b00010010;
      address0   == 32'hAAAA0000;
      address1   == 32'hBBBB1111;
      address2   == 32'hCCCC2222;
      address3   == 32'hDDDD3333;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_ALL_REQ_IDLE
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0000;
      qos        == 8'b00000000;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_ALL_REQ_SAME_QOS
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1111;
      qos        == 8'b10101010;
      address0   == 32'h0000AAAA;
      address1   == 32'h0000BBBB;
      address2   == 32'h0000CCCC;
      address3   == 32'h0000DDDD;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_REQ_CHANGE_EACH_CYCLE
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0101;
      qos        == 8'b01100110;
      address0   == 32'hDEADBEEF;
      address1   == 32'h00000000;
      address2   == 32'hFEEDC0DE;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_ACK_HANDSHAKE
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0010;
      qos        == 8'b00000010;
      address0   == 32'h00000000;
      address1   == 32'h12345678;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 1;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_RESET_ASSERT
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      reset      == 1;
      request    == 4'b1111;
      qos        == 8'b11110000;
      address0   == 32'hFFFFFFFF;
      address1   == 32'hEEEEEEEE;
      address2   == 32'hDDDDDDDD;
      address3   == 32'hCCCCCCCC;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_QOS_MAX
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1000;
      qos        == 8'b11000000;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h7FFFFFFF;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_QOS_MIN
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0001;
      qos        == 8'b00000000;
      address0   == 32'h80000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_ADDRESS_MAX
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0100;
      qos        == 8'b00001100;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'hFFFFFFFF;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_ADDRESS_MIN
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0010;
      qos        == 8'b00000010;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_ALL_REQ_ACTIVE
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1111;
      qos        == 8'b00111001;
      address0   == 32'h11110000;
      address1   == 32'h22220000;
      address2   == 32'h33330000;
      address3   == 32'h44440000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // BOUND_ALL_REQ_INACTIVE
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0000;
      qos        == 8'b11111111;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_ROUND_ROBIN_WRAP
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0101;
      qos        == 8'b00000000;
      address0   == 32'h11112222;
      address1   == 32'h00000000;
      address2   == 32'h33334444;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // FUNC_PRIORITY_WRAP
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1000;
      qos        == 8'b11000000;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'hFFFFFFFF;
      mem_ack    == 1;
    });
    start_item(seq_item); finish_item(seq_item);

    // 2. Boundary value tests (min/max/mid)
    // Min values
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0001;
      qos        == 8'b00000000;
      address0   == 32'h00000000;
      address1   == 32'h00000000;
      address2   == 32'h00000000;
      address3   == 32'h00000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // Max values
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b1000;
      qos        == 8'b11111111;
      address0   == 32'hFFFFFFFF;
      address1   == 32'hFFFFFFFF;
      address2   == 32'hFFFFFFFF;
      address3   == 32'hFFFFFFFF;
      mem_ack    == 1;
    });
    start_item(seq_item); finish_item(seq_item);

    // Mid values
    seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
    assert(seq_item.randomize() with {
      request    == 4'b0110;
      qos        == 8'b01010101;
      address0   == 32'h7FFFFFFF;
      address1   == 32'h40000000;
      address2   == 32'h20000000;
      address3   == 32'h10000000;
      mem_ack    == 0;
    });
    start_item(seq_item); finish_item(seq_item);

    // 3. Randomized test transactions for coverage
    repeat (2500) begin
      seq_item = memory_scheduler_seq_item::type_id::create("seq_item");
      // Randomize all input fields according to constraints
      assert(seq_item.randomize());
      start_item(seq_item);
      finish_item(seq_item);
    end

  endtask
endclass
