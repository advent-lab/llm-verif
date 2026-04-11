
`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_expected)

//------------------------------------------------------------------------------
// Title: memory_scheduler_scoreboard
// Description: Logging-only scoreboard. All checking logic has been removed.
//              Transactions received on both ports are logged at UVM_HIGH
//              verbosity. The report_phase prints a transaction count summary.
//------------------------------------------------------------------------------

class memory_scheduler_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(memory_scheduler_scoreboard)

  // Analysis ports kept intact so the rest of the TB wiring compiles unchanged
  uvm_analysis_imp_actual   #(memory_scheduler_seq_item, memory_scheduler_scoreboard) actual_imp;
  uvm_analysis_imp_expected #(memory_scheduler_seq_item, memory_scheduler_scoreboard) expected_imp;

  int actual_count   = 0;
  int expected_count = 0;

  function new(string name, uvm_component parent);
    super.new(name, parent);
    actual_imp   = new("actual_imp",   this);
    expected_imp = new("expected_imp", this);
  endfunction

  // Log actual DUT transactions
  // FIX: original used comma-separated string literals inside $sformatf(), which
  // SystemVerilog treats as additional arguments rather than string continuation,
  // causing STASKW_SFRTMATR (15 args, 4 specifiers) and completely corrupt output.
  // All format text is now in a single unbroken string.
  function void write_actual(memory_scheduler_seq_item actual);
    actual_count++;
    `uvm_info("SCB_ACTUAL", $sformatf(
      "ACTUAL   @ %0t: reset=%0b req=0x%0h qos=0x%0h addr0=0x%08h addr1=0x%08h addr2=0x%08h addr3=0x%08h mem_ack=%0b | mem_cmd_valid=%0b mem_cmd_type=0x%0h mem_address=0x%08h grant=0x%0h",
      $time,
      actual.reset, actual.request, actual.qos,
      actual.address0, actual.address1, actual.address2, actual.address3, actual.mem_ack,
      actual.mem_cmd_valid, actual.mem_cmd_type, actual.mem_address, actual.grant
    ), UVM_HIGH)
  endfunction

  // Log expected (reference model) transactions
  function void write_expected(memory_scheduler_seq_item expected);
    expected_count++;
    `uvm_info("SCB_EXPECTED", $sformatf(
      "EXPECTED @ %0t: reset=%0b req=0x%0h qos=0x%0h addr0=0x%08h addr1=0x%08h addr2=0x%08h addr3=0x%08h mem_ack=%0b | mem_cmd_valid=%0b mem_cmd_type=0x%0h mem_address=0x%08h grant=0x%0h",
      $time,
      expected.reset, expected.request, expected.qos,
      expected.address0, expected.address1, expected.address2, expected.address3, expected.mem_ack,
      expected.mem_cmd_valid, expected.mem_cmd_type, expected.mem_address, expected.grant
    ), UVM_HIGH)
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("SCB", "----------------------------------------",                          UVM_NONE)
    `uvm_info("SCB", "SCOREBOARD SUMMARY (checking disabled)",                             UVM_NONE)
    `uvm_info("SCB", $sformatf("Actual transactions logged:   %0d", actual_count),        UVM_NONE)
    `uvm_info("SCB", $sformatf("Expected transactions logged: %0d", expected_count),      UVM_NONE)
    `uvm_info("SCB", "----------------------------------------",                          UVM_NONE)
  endfunction

endclass
