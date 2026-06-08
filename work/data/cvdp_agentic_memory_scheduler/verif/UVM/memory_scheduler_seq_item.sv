
import uvm_pkg::*;
`include "uvm_macros.svh"

// Sequence item for memory_scheduler module
class memory_scheduler_seq_item extends uvm_sequence_item;

  // Clock and Reset: always present, not randomized
  bit clk;
  bit reset;

  // Input signals (rand): these are driven to the DUT
  rand bit [3:0]  request;      // 1 bit per requester
  rand bit [7:0]  qos;          // 2 bits per requester (qos[1:0]=req0, [3:2]=req1, etc.)
  rand bit [31:0] address0;
  rand bit [31:0] address1;
  rand bit [31:0] address2;
  rand bit [31:0] address3;
  rand bit        mem_ack;      // handshake from memory interface

  // Output signals (not rand): observed from DUT
  bit [31:0] mem_address;
  bit        mem_cmd_valid;
  bit [1:0]  mem_cmd_type;
  bit [3:0]  grant;

  // UVM automation macros for field registration
  `uvm_object_utils_begin(memory_scheduler_seq_item)
    `uvm_field_int(clk,           UVM_ALL_ON)
    `uvm_field_int(reset,         UVM_ALL_ON)
    `uvm_field_int(request,       UVM_ALL_ON)
    `uvm_field_int(qos,           UVM_ALL_ON)
    `uvm_field_int(address0,      UVM_ALL_ON)
    `uvm_field_int(address1,      UVM_ALL_ON)
    `uvm_field_int(address2,      UVM_ALL_ON)
    `uvm_field_int(address3,      UVM_ALL_ON)
    `uvm_field_int(mem_ack,       UVM_ALL_ON)
    `uvm_field_int(mem_address,   UVM_ALL_ON)
    `uvm_field_int(mem_cmd_valid, UVM_ALL_ON)
    `uvm_field_int(mem_cmd_type,  UVM_ALL_ON)
    `uvm_field_int(grant,         UVM_ALL_ON)
  `uvm_object_utils_end

  // Constructor
  function new(string name = "memory_scheduler_seq_item");
    super.new(name);
  endfunction

  // Constraints

  // At least one request can be active, or all can be idle (for idle scenario)
  constraint c_request_valid {
    request inside {[0:15]}; // 4 bits, 0 to 15
  }

  // QoS: Each 2-bit field must be in 0..3
  constraint c_qos_range {
    (qos[1:0]  >= 0) && (qos[1:0]  <= 3);
    (qos[3:2]  >= 0) && (qos[3:2]  <= 3);
    (qos[5:4]  >= 0) && (qos[5:4]  <= 3);
    (qos[7:6]  >= 0) && (qos[7:6]  <= 3);
  }

  // Address constraints: full 32-bit range allowed
  constraint c_address0_range { address0 inside {[32'h0000_0000:32'hFFFF_FFFF]}; }
  constraint c_address1_range { address1 inside {[32'h0000_0000:32'hFFFF_FFFF]}; }
  constraint c_address2_range { address2 inside {[32'h0000_0000:32'hFFFF_FFFF]}; }
  constraint c_address3_range { address3 inside {[32'h0000_0000:32'hFFFF_FFFF]}; }

  // mem_ack: only 0 or 1
  constraint c_mem_ack_val { mem_ack == 0 || mem_ack == 1; }

  // Functional scenario: If only one request is active, its address must be in range
  constraint c_single_request_addr_valid {
    (request == 4'b0001) -> (address0 inside {[32'h0000_0000:32'hFFFF_FFFF]});
    (request == 4'b0010) -> (address1 inside {[32'h0000_0000:32'hFFFF_FFFF]});
    (request == 4'b0100) -> (address2 inside {[32'h0000_0000:32'hFFFF_FFFF]});
    (request == 4'b1000) -> (address3 inside {[32'h0000_0000:32'hFFFF_FFFF]});
  }

  // Prevent all addresses from being identical when more than one requester is
  // actually active. FIX: original used (request > 1) which compares the numeric
  // value of the request vector, not the number of active bits. This caused solver
  // failures for single-bit patterns like 4'b0010 (=2), 4'b0100 (=4), 4'b1000 (=8)
  // because all three have numeric value > 1 despite only one requester being active.
  // $countones() correctly counts set bits so the constraint only applies when two
  // or more requesters are genuinely active simultaneously.
  constraint c_addr_unique_if_multi_req {
    ($countones(request) > 1) -> (
      (address0 != address1) ||
      (address0 != address2) ||
      (address0 != address3) ||
      (address1 != address2) ||
      (address1 != address3) ||
      (address2 != address3)
    );
  }

  constraint c_no_xz {
    foreach (request[i])  request[i]  inside {0,1};
    foreach (qos[i])      qos[i]      inside {0,1};

    foreach (address0[i]) address0[i] inside {0,1};
    foreach (address1[i]) address1[i] inside {0,1};
    foreach (address2[i]) address2[i] inside {0,1};
    foreach (address3[i]) address3[i] inside {0,1};

    mem_ack inside {0,1};
  }

endclass
