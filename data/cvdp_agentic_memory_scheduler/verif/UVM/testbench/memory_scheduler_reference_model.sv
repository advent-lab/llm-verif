import uvm_pkg::*;
`include "uvm_macros.svh"

class memory_scheduler_ref_model extends uvm_component;
  typedef memory_scheduler_seq_item item_t;

  typedef struct {
    logic [1:0]  current_priority;
    logic [1:0]  round_robin_index;
    logic [31:0] mem_address;
    logic        mem_cmd_valid;
    logic [1:0]  mem_cmd_type;
    logic [3:0]  grant;
  } ref_state_t;

  // Incoming transactions from monitor/agent
  uvm_analysis_imp#(item_t, memory_scheduler_ref_model) in_imp;

  // Predicted/expected transactions to scoreboard
  uvm_analysis_port#(item_t) out_ap;

  ref_state_t state;

  `uvm_component_utils(memory_scheduler_ref_model)

  function new(string name = "memory_scheduler_ref_model", uvm_component parent = null);
    super.new(name, parent);
    in_imp = new("in_imp", this);
    out_ap = new("out_ap", this);
    reset_state();
  endfunction

  function void reset_state();
    state.current_priority  = 2'b11;
    state.round_robin_index = 2'b00;
    state.mem_address       = 32'd0;
    state.mem_cmd_valid     = 1'b0;
    state.mem_cmd_type      = 2'b00;
    state.grant             = 4'b0000;
  endfunction

  // Extract the 2-bit qos for requester idx from packed [7:0] bus.
  function automatic logic [1:0] get_qos(logic [7:0] qos_bus, int unsigned idx);
    case (idx)
      0: return qos_bus[1:0];
      1: return qos_bus[3:2];
      2: return qos_bus[5:4];
      3: return qos_bus[7:6];
      default: return 2'b00;
    endcase
  endfunction

  // Pick the first requester (highest index first, matching original behavior)
  // that is requesting AND matches the given priority.
  function automatic logic [3:0] pick_priority_match(
    logic [3:0] request,
    logic [7:0] qos,
    logic [1:0] prio
  );
    logic [3:0] picked;
    picked = 4'b0000;

    for (int idx = 3; idx >= 0; idx--) begin
      if ((picked == 4'b0000) && request[idx] && (get_qos(qos, idx) == prio)) begin
        picked[idx] = 1'b1;
      end
    end
    return picked;
  endfunction

  // Round-robin fallback if no priority match.
  function automatic logic [3:0] pick_round_robin(
    logic [3:0] request,
    logic [1:0] start_idx,
    output logic [1:0] next_rr
  );
    logic [3:0] picked;
    picked  = 4'b0000;
    next_rr = start_idx;

    for (int k = 0; k < 4; k++) begin
      int idx;
      idx = (start_idx + k) % 4;
      if ((picked == 4'b0000) && request[idx]) begin
        picked[idx] = 1'b1;
        next_rr = (idx + 1) % 4;
      end
    end

    return picked;
  endfunction

  // Address mux for picked requester.
  function automatic logic [31:0] get_address(item_t tr, logic [3:0] picked);
    case (1'b1)
      picked[0]: return tr.address0;
      picked[1]: return tr.address1;
      picked[2]: return tr.address2;
      picked[3]: return tr.address3;
      default:   return 32'd0;
    endcase
  endfunction

  function automatic logic [1:0] rotate_priority(logic [1:0] prio);
    if (prio == 2'b00) begin
      return 2'b11;
    end
    return prio - 2'b01;
  endfunction

  function void predict_one_cycle(item_t tr, ref item_t pred);
    logic [3:0] picked;
    logic [1:0] next_rr;
    bit         advance_arb;

    // If any inputs are X/Z, don't mutate internal state. Still emit a prediction
    // equal to the *current* state (so the scoreboard can decide how to treat it).
    if ($isunknown(tr.request) || $isunknown(tr.qos) || $isunknown(tr.mem_ack) || $isunknown(tr.reset)) begin
      `uvm_warning(get_type_name(),
        "Unknown input detected (X/Z) - holding reference-model state for this cycle")
    end
    else if (tr.reset) begin
      reset_state();
    end
    else begin
      // Advance arbitration when no command is outstanding, or when mem_ack arrives.
      advance_arb = (state.mem_cmd_valid == 1'b0) || (tr.mem_ack == 1'b1);

      if (advance_arb) begin
        picked  = pick_priority_match(tr.request, tr.qos, state.current_priority);
        next_rr = state.round_robin_index;

        if (picked == 4'b0000) begin
          picked = pick_round_robin(tr.request, state.round_robin_index, next_rr);
        end

        if (picked == 4'b0000) begin
          state.mem_cmd_valid = 1'b0;
          state.grant         = 4'b0000;
        end
        else begin
          state.mem_cmd_valid = 1'b1;
          state.mem_cmd_type  = 2'b00;
          state.grant         = picked;
          state.mem_address   = get_address(tr, picked);
        end

        // FIX: both state updates were outside the advance_arb block, causing
        // current_priority and round_robin_index to rotate on every write()
        // call regardless of whether the DUT actually performed arbitration.
        // When mem_cmd_valid=1 and mem_ack=0 the DUT holds state and does not
        // rotate — the reference model must match this behaviour exactly.
        state.current_priority  = rotate_priority(state.current_priority);
        state.round_robin_index = next_rr;
      end  // advance_arb
    end  // !reset

    // Populate *expected* outputs into pred using the seq_item's existing fields.
    pred.mem_cmd_valid = state.mem_cmd_valid;
    pred.mem_cmd_type  = state.mem_cmd_type;
    pred.grant         = state.grant;
    pred.mem_address   = state.mem_address;
  endfunction

  // UVM analysis imp callback
  function void write(item_t tr);
    item_t pred;

    if (tr == null) begin
      `uvm_warning(get_type_name(), "Received null transaction in reference model")
      return;
    end

    pred = item_t::type_id::create("pred");
    pred.copy(tr);

    predict_one_cycle(tr, pred);
    out_ap.write(pred);
  endfunction

endclass
