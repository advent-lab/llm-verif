
import uvm_pkg::*;
`include "uvm_macros.svh"

// Sequence item for rgb_color_space_hsv module
class rgb_color_space_hsv_seq_item extends uvm_sequence_item;

  // Clock and reset signals (not randomized)
  bit clk;
  bit rst;

  // Input signals (randomized)
  rand bit we;
  rand bit [7:0]  waddr;
  rand bit [24:0] wdata;
  rand bit valid_in;
  rand bit [7:0]  r_component;
  rand bit [7:0]  g_component;
  rand bit [7:0]  b_component;

  // Output signals (not randomized)
  bit [11:0] h_component;
  bit [12:0] s_component;
  bit [11:0] v_component;
  bit        valid_out;

  // UVM automation macros for field registration
  `uvm_object_utils_begin(rgb_color_space_hsv_seq_item)
    `uvm_field_int(clk,         UVM_ALL_ON)
    `uvm_field_int(rst,         UVM_ALL_ON)
    `uvm_field_int(we,          UVM_ALL_ON)
    `uvm_field_int(waddr,       UVM_ALL_ON)
    `uvm_field_int(wdata,       UVM_ALL_ON)
    `uvm_field_int(valid_in,    UVM_ALL_ON)
    `uvm_field_int(r_component, UVM_ALL_ON)
    `uvm_field_int(g_component, UVM_ALL_ON)
    `uvm_field_int(b_component, UVM_ALL_ON)
    `uvm_field_int(h_component, UVM_ALL_ON)
    `uvm_field_int(s_component, UVM_ALL_ON)
    `uvm_field_int(v_component, UVM_ALL_ON)
    `uvm_field_int(valid_out,   UVM_ALL_ON)
  `uvm_object_utils_end

  // Constructor
  function new(string name = "rgb_color_space_hsv_seq_item");
    super.new(name);
  endfunction

  // Constraints

  // 1. waddr is valid only when we is asserted
  constraint c_waddr_when_we {
    (we == 1) -> (waddr inside {[0:255]});
    (we == 0) -> (waddr == '0);
  }

  // 2. wdata is valid only when we is asserted
  constraint c_wdata_when_we {
    (we == 1) -> (wdata inside {[0:25'h1FFFFFF]});
    (we == 0) -> (wdata == '0);
  }

  // 3. Only one mode active at a time: either memory initialization or conversion
  constraint c_mode_exclusive {
    !(we == 1 && valid_in == 1); // Cannot assert both at the same time
  }

  // 4. When valid_in is asserted, RGB values are valid
  constraint c_rgb_when_valid_in {
    (valid_in == 1) -> (r_component inside {[0:255]});
    (valid_in == 1) -> (g_component inside {[0:255]});
    (valid_in == 1) -> (b_component inside {[0:255]});
    (valid_in == 0) -> (r_component == '0);
    (valid_in == 0) -> (g_component == '0);
    (valid_in == 0) -> (b_component == '0);
  }

  // 5. When neither we nor valid_in is asserted, all inputs except clk/rst are zero (idle)
  constraint c_idle_state {
    (we == 0 && valid_in == 0) -> (
      waddr == '0 &&
      wdata == '0 &&
      r_component == '0 &&
      g_component == '0 &&
      b_component == '0
    );
  }

  // 6. Prevent back-to-back input: valid_in can only be asserted when previous transaction is done (handled in sequencer/driver, but here for completeness)
  // (No direct constraint here, but can be enforced in sequence/sequencer)

  // 7. Reset can be asserted at any time (no constraint on rst)

endclass
