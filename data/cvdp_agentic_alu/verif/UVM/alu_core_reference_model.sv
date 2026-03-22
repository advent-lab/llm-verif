import uvm_pkg::*;
`include "uvm_macros.svh"

class alu_core_ref_model extends uvm_component;

  // Consume seq_items from monitor/agent
  uvm_analysis_imp #(alu_core_seq_item, alu_core_ref_model) in_imp;

  // Publish predicted seq_items to scoreboard expected path
  uvm_analysis_port #(alu_core_seq_item) out_ap;

  `uvm_component_utils(alu_core_ref_model)

  function new(string name = "alu_core_ref_model", uvm_component parent = null);
    super.new(name, parent);
    in_imp = new("in_imp", this);
    out_ap = new("out_ap", this);
  endfunction

  // Called when a txn arrives on in_imp
  function void write(alu_core_seq_item tr);
    alu_core_seq_item pred;

    if (tr == null) begin
      `uvm_warning(get_type_name(), "Received null transaction in reference model")
      return;
    end

    // IMPORTANT: create a fresh object so we don't mutate the original
    pred = alu_core_seq_item::type_id::create("pred", this);
    pred.copy(tr);

    // Compute expected result into pred.result
    predict(pred);

    // Send to scoreboard expected path
    out_ap.write(pred);
  endfunction

  function void predict(ref alu_core_seq_item tr);
    unique case (tr.opcode)
      4'h0: tr.result = tr.operand1 + tr.operand2 + tr.operand3;
      4'h1: tr.result = tr.operand1 - tr.operand2 - tr.operand3;
      4'h2: tr.result = tr.operand1 * tr.operand2 * tr.operand3;

      4'h3: begin
        // Division-by-zero handling: choose a convention.
        // Option 1: return 0 (common)
        // Option 2: keep previous / don't care
        // Option 3: flag error (requires adding fields to seq_item)
        if ((tr.operand2 == 0) || (tr.operand3 == 0))
          tr.result = '0;
        else
          tr.result = tr.operand1 / tr.operand2 / tr.operand3;
      end

      4'h4: tr.result = tr.operand1 & tr.operand2 & tr.operand3;
      4'h5: tr.result = tr.operand1 | tr.operand2 | tr.operand3;
      4'h6: tr.result = tr.operand1 ^ tr.operand2 ^ tr.operand3;

      default: tr.result = '0;
    endcase
  endfunction

endclass
