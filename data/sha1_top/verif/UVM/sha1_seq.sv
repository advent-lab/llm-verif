`ifndef SHA1_SEQ_SV
`define SHA1_SEQ_SV

import uvm_pkg::*;
`include "uvm_macros.svh"

// =============================================================================
// sha1_base_sequence
//   Provides shared helper tasks used by all derived sequences.
//   Mirrors the Verilog/SV reference testbench task structure exactly:
//     write_word  — one write transaction
//     read_word   — one read transaction, returns read_data
//     wait_ready  — polls ADDR_STATUS in a loop until ready or valid is set
//     write_block — 16 consecutive write_word calls
// =============================================================================
class sha1_base_sequence extends uvm_sequence #(sha1_seq_item);

  `uvm_object_utils(sha1_base_sequence)

  function new(string name = "sha1_base_sequence");
    super.new(name);
  endfunction

  virtual task body();
    // Base sequence does nothing — override in derived classes
  endtask

  // ---------------------------------------------------------------------------
  // write_word — single register write
  // ---------------------------------------------------------------------------
  task write_word(input logic [7:0] addr, input logic [31:0] data);
    sha1_seq_item item;
    item            = sha1_seq_item::type_id::create("write_word");
    item.cs         = 1;
    item.we         = 1;
    item.reset_n    = 1;
    item.address    = addr;
    item.write_data = data;
    start_item(item);
    finish_item(item);
  endtask

  // ---------------------------------------------------------------------------
  // read_word — single register read, returns value in read_data
  // ---------------------------------------------------------------------------
  task read_word(input logic [7:0] addr, output logic [31:0] data);
    sha1_seq_item item;
    item            = sha1_seq_item::type_id::create("read_word");
    item.cs         = 1;
    item.we         = 0;
    item.reset_n    = 1;
    item.address    = addr;
    item.write_data = 32'h0;
    start_item(item);
    finish_item(item);
    // read_data is populated by the driver after the DUT has sampled
    data = item.read_data;
  endtask

  // ---------------------------------------------------------------------------
  // write_block — write all 16 block registers
  // ---------------------------------------------------------------------------
  task write_block(input logic [511:0] block);
    write_word(8'h10, block[511:480]);
    write_word(8'h11, block[479:448]);
    write_word(8'h12, block[447:416]);
    write_word(8'h13, block[415:384]);
    write_word(8'h14, block[383:352]);
    write_word(8'h15, block[351:320]);
    write_word(8'h16, block[319:288]);
    write_word(8'h17, block[287:256]);
    write_word(8'h18, block[255:224]);
    write_word(8'h19, block[223:192]);
    write_word(8'h1a, block[191:160]);
    write_word(8'h1b, block[159:128]);
    write_word(8'h1c, block[127:96]);
    write_word(8'h1d, block[95:64]);
    write_word(8'h1e, block[63:32]);
    write_word(8'h1f, block[31:0]);
  endtask

  // ---------------------------------------------------------------------------
  // wait_ready
  //   Polls ADDR_STATUS in a loop until read_data is non-zero.
  //   Matches the Verilog testbench wait_ready task exactly:
  //     - read_data initialised to 0
  //     - loop: read 0x09, exit when either ready(bit0) or valid(bit1) is set
  //   One extra idle write_word (NOP) is issued before the loop to give
  //   the DUT one clock cycle to deassert ready after an init/next command,
  //   matching the #(CLK_PERIOD) the Verilog testbench inserts before polling.
  // ---------------------------------------------------------------------------
  task wait_ready();
    logic [31:0] status;
    // One idle cycle — allows ready to deassert after init/next command
    // before we start polling, matching #(CLK_PERIOD) in Verilog TB
    read_word(8'h09, status);
    // Poll until ready (bit0) or valid (bit1) is asserted
    status = 32'h0;
    while (status == 32'h0) begin
      read_word(8'h09, status);
    end
  endtask

  // ---------------------------------------------------------------------------
  // read_digest — read all 5 digest words, return as 160-bit value
  // ---------------------------------------------------------------------------
  task read_digest(output logic [159:0] digest);
    logic [31:0] word;
    read_word(8'h20, word); digest[159:128] = word;
    read_word(8'h21, word); digest[127:96]  = word;
    read_word(8'h22, word); digest[95:64]   = word;
    read_word(8'h23, word); digest[63:32]   = word;
    read_word(8'h24, word); digest[31:0]    = word;
  endtask

endclass : sha1_base_sequence


// =============================================================================
// sha1_directed_sequence
//   Directed scenario mirroring the single_block_test and double_block_test
//   tasks from the reference testbench, plus additional directed cases.
// =============================================================================
class sha1_directed_sequence extends sha1_base_sequence;

  `uvm_object_utils(sha1_directed_sequence)

  function new(string name = "sha1_directed_sequence");
    super.new(name);
  endfunction

  virtual task body();
    logic [31:0]  rdata;
    logic [159:0] digest;

    // ------------------------------------------------------------------
    // 1. Read identification registers
    // ------------------------------------------------------------------
    read_word(8'h00, rdata);
    read_word(8'h01, rdata);
    read_word(8'h02, rdata);

    // ------------------------------------------------------------------
    // 2. Single block test — "abc" SHA-1 known answer
    //    Expected: a9993e364706816aba3e25717850c26c9cd0d89d
    // ------------------------------------------------------------------
    write_block(512'h6162638000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000018);
    write_word(8'h08, 32'h1);   // INIT
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("Single block digest: %040h", digest), UVM_NONE)

    // ------------------------------------------------------------------
    // 3. Double block test — first block
    //    Expected first:  f4286818c37b27ae0408f581846771484a566572
    //    Expected second: 84983e441c3bd26ebaae4aa1f95129e5e54670f1
    // ------------------------------------------------------------------
    write_block(512'h6162636462636465636465666465666765666768666768696768696A68696A6B696A6B6C6A6B6C6D6B6C6D6E6C6D6E6F6D6E6F706E6F70718000000000000000);
    write_word(8'h08, 32'h1);   // INIT
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("Double block first digest:  %040h", digest), UVM_NONE)

    // Second block
    write_block(512'h000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001C0);
    write_word(8'h08, 32'h2);   // NEXT
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("Double block final digest:  %040h", digest), UVM_NONE)

    // ------------------------------------------------------------------
    // 4. Status register read
    // ------------------------------------------------------------------
    read_word(8'h09, rdata);

    // ------------------------------------------------------------------
    // 5. Invalid address — should assert error flag
    // ------------------------------------------------------------------
    read_word(8'h25, rdata);

    // ------------------------------------------------------------------
    // 6. Control register read-back
    // ------------------------------------------------------------------
    read_word(8'h08, rdata);

    // ------------------------------------------------------------------
    // 7. All-zero block with INIT
    // ------------------------------------------------------------------
    write_block(512'h0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000);
    write_word(8'h08, 32'h1);   // INIT
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("All-zero block digest: %040h", digest), UVM_NONE)

    // ------------------------------------------------------------------
    // 8. All-ones block with NEXT
    // ------------------------------------------------------------------
    write_block(512'hFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF);
    write_word(8'h08, 32'h2);   // NEXT
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("All-ones NEXT digest:  %040h", digest), UVM_NONE)

    // ------------------------------------------------------------------
    // 9. State register write then SET command
    // ------------------------------------------------------------------
    write_word(8'h30, 32'h67452301);
    write_word(8'h31, 32'hEFCDAB89);
    write_word(8'h32, 32'h98BADCFE);
    write_word(8'h33, 32'h10325476);
    write_word(8'h34, 32'hC3D2E1F0);
    write_word(8'h08, 32'h4);   // SET

    // ------------------------------------------------------------------
    // 10. Write-while-busy — issue INIT then immediately write block1
    //     The block write should be silently dropped by the RTL
    // ------------------------------------------------------------------
    write_block(512'h0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000);
    write_word(8'h08, 32'h1);   // INIT — core goes busy
    write_word(8'h11, 32'hDEADBEEF); // write during processing — dropped
    wait_ready();
    read_digest(digest);
    `uvm_info("DIRECTED", $sformatf("Write-while-busy digest: %040h", digest), UVM_NONE)

  endtask

endclass : sha1_directed_sequence


// =============================================================================
// sha1_random_sequence
//   Random bus transactions — excludes control register writes to avoid
//   issuing unpredictable init/next/set commands that would interfere
//   with wait_ready polling.
// =============================================================================
class sha1_random_sequence extends sha1_base_sequence;

  `uvm_object_utils(sha1_random_sequence)

  function new(string name = "sha1_random_sequence");
    super.new(name);
  endfunction

  virtual task body();
    sha1_seq_item item;
    repeat (2500) begin
      item = sha1_seq_item::type_id::create("item");
      assert(item.randomize() with {
        // Exclude control register writes — no random commands
        !(we == 1 && address == 8'h08);
      }) else
        `uvm_fatal("RAND", "sha1_random_sequence: randomize() failed")
      start_item(item);
      finish_item(item);
    end
  endtask

endclass : sha1_random_sequence

`endif // SHA1_SEQ_SV
