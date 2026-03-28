from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

def load_system_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    design_files: List[Path],
    design_context_files: List[Path],
    module_header: str,
    design_context_enabled: bool,
    testplan_enabled: bool,
    max_iterations: int,
    sim_runs: int,
    uvm_enabled: bool = False,
    uvm_seq_item_content: Optional[str] = None,
    uvm_coverage_module_content: Optional[str] = None,
    uvm_sequence_file: Optional[str] = None,
    uvm_test_name: Optional[str] = None,
    uvm_testbench_files: Optional[List[str]] = None,
    uvm_interface_name: Optional[str] = None,
    uvm_env_class: Optional[str] = None,
) -> str:
    """
    Load system prompt template and interpolate variables.

    Returns complete system prompt string.
    """
    # Read template
    template_path = Path(__file__).parent / "system.md"
    with open(template_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # Extract template content (between ``` markers after "System Prompt Template")
    # Find the start of the template (after "## System Prompt Template")
    start_marker = "## System Prompt Template\n\n```"
    start_idx = full_content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Could not find template start marker")

    # Move past the marker and opening ```
    start_idx += len(start_marker) + 1  # +1 for newline after ```

    # Find the end marker (closing ``` before "## Conditional Sections")
    end_marker = "```\n\n---\n\n## Conditional Sections"
    end_idx = full_content.find(end_marker, start_idx)
    if end_idx == -1:
        raise ValueError("Could not find template end marker")

    template = full_content[start_idx:end_idx]

    # Format file lists for prompt based on design_context_enabled
    if design_context_enabled:
        design_files_str = "\n".join([f"   - {f}" for f in design_files])
        if not design_files_str:
            design_files_str = "   (none)"
        
        design_context_files_str = "\n".join([f"   - {f}" for f in design_context_files])
        if not design_context_files_str:
            design_context_files_str = "   (none)"
        
        file_access_note = "You can read all design and design context files listed above using `read_file` to understand implementation details when needed."
    else:
        design_files_str = "   (not accessible - design context disabled)"
        design_context_files_str = "   (not accessible - design context disabled)"
        file_access_note = "You can only read the specification file. Design and design context files are not accessible for reading."

    # Prepare conditional sections
    if testplan_enabled:
        testplan_instruction = """### Step 2: Create Verification Plan
Before generating testbenches, create a verification plan that outlines:
- Key features to test
- Corner cases and boundary conditions
- Reset and initialization scenarios
- Error conditions to verify
- Expected coverage targets per feature

Save your testplan using `write_file` to `testplan.md`

This plan will guide your testbench development and help ensure comprehensive coverage."""
    else:
        testplan_instruction = "(Testplan generation is disabled - proceed directly to testbench generation)"

    # ── UVM Instructions (conditional) ───────────────────────────────────
    uvm_instructions = ""
    if uvm_enabled:
        uvm_instructions = _build_uvm_instructions(
            uvm_seq_item_content=uvm_seq_item_content or "",
            uvm_coverage_module_content=uvm_coverage_module_content or "",
            uvm_sequence_file=uvm_sequence_file or "sequence.sv",
            uvm_test_name=uvm_test_name or "uvm_test",
            uvm_testbench_files=uvm_testbench_files or [],
            uvm_interface_name=uvm_interface_name or "design_if",
            uvm_env_class=uvm_env_class or "design_env",
        )

    # Interpolate variables
    prompt = template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        design_files=design_files_str,
        design_context_files=design_context_files_str,
        file_access_note=file_access_note,
        module_header=module_header,
        testplan_instruction=testplan_instruction,
        max_iterations=max_iterations,
        sim_runs=sim_runs,
        uvm_instructions=uvm_instructions,
    )

    return prompt


def _build_uvm_instructions(
    uvm_seq_item_content: str,
    uvm_coverage_module_content: str,
    uvm_sequence_file: str,
    uvm_test_name: str,
    uvm_testbench_files: List[str],
    uvm_interface_name: str = "design_if",
    uvm_env_class: str = "design_env",
) -> str:
    """Build UVM-specific instructions for the system prompt."""

    tb_files_list = "\n".join(f"   - {f}" for f in uvm_testbench_files) if uvm_testbench_files else "   (none listed)"

    return f"""
=================================================================================
UVM MODE - SEQUENCE AND TEST GENERATION
=================================================================================

You are in **UVM MODE**. Instead of writing complete testbenches, you generate:
1. A **UVM sequence file** (`testbenches/{uvm_sequence_file}`)
2. A **UVM test file** (`testbenches/{uvm_test_name}.sv`)

The UVM testbench infrastructure (driver, monitor, agent, env, interface, scoreboard,
Top module, coverage module) is already provided and fixed. You must NOT modify these.

Coverage is collected from BOTH:
- **Code coverage**: Statement/branch/condition/expression/toggle coverage of the RTL
- **Functional coverage**: Covergroups in the passive coverage module (tb_llm)

### What You Generate

**1. Sequence File (`testbenches/{uvm_sequence_file}`)**

A complete SystemVerilog file containing UVM sequence classes. The sequences MUST:
- Import `uvm_pkg::*` and include `uvm_macros.svh`
- Extend `uvm_sequence #(<seq_item_class>)` (use the seq_item class shown below)
- Use the `start_item()`/`finish_item()` pattern for every transaction
- Use `randomize()` with constraints or direct field assignment on the seq_item
- Register with factory via `` `uvm_object_utils ``

**2. Test File (`testbenches/{uvm_test_name}.sv`)**

A complete SystemVerilog file containing the UVM test class. The test MUST:
- Extend `uvm_test`
- Register with factory via `` `uvm_component_utils ``
- Declare the virtual interface and env with the correct design-specific types:
  `virtual {uvm_interface_name} vif;` and `{uvm_env_class} env;`
- In `build_phase`: **MANDATORY** config_db get/set for the virtual interface,
  then create env and sequence instances. The build_phase MUST contain this
  exact config_db pattern (the env will UVM_FATAL if vif is not set):

```systemverilog
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // GET vif from config_db (set by Top module)
    if (!uvm_config_db#(virtual {uvm_interface_name})::get(this, "", "vif", vif))
      `uvm_fatal(get_type_name(), "Failed to get vif from config_db")
    // PASS vif to env (env retrieves it in its own build_phase)
    uvm_config_db#(virtual {uvm_interface_name})::set(this, "env*", "vif", vif);
    // Create env and sequences
    env = {uvm_env_class}::type_id::create("env", this);
    // ... create sequence instances here ...
  endfunction
```

- In `run_phase`: raise objection, start your sequences on `env.agent.sqr`,
  drop objection
- Import and instantiate the sequences you defined in the sequence file

### Sequence Item Definition (FIXED - DO NOT MODIFY)

This is the transaction class your sequences must use:

```systemverilog
{uvm_seq_item_content}
```

### Coverage Module (FIXED - targeting these bins)

This passive module collects functional coverage. Study the covergroups
and bins to understand what stimulus patterns are needed:

```systemverilog
{uvm_coverage_module_content}
```

### UVM Testbench Files (FIXED - DO NOT MODIFY)

These files are already provided and compiled via the .f file:
{tb_files_list}

### UVM Mode Workflow

1. **Read** the specification and understand the design
2. **Study** the seq_item fields/constraints and coverage bins above
3. **Plan** — call `plan_coverage_strategy(target_bins, strategy)` to structure
   your approach before writing any code. List the specific bins/lines you will
   target and how. This is MANDATORY before every `write_file` call.
4. **Generate** the sequence file with sequences targeting coverage
5. **Generate** the test file that runs your sequences
6. **Save** both using `write_file`:
   - `write_file("testbenches/{uvm_sequence_file}", <sequence_content>)`
   - `write_file("testbenches/{uvm_test_name}.sv", <test_content>)`
7. **Compile** using `compile_design("testbenches/{uvm_sequence_file}")`
   (the argument is just for logging; the .f file handles compilation)
8. **Simulate** using `run_simulation()`
9. **Analyze** coverage:
   - Use `parse_coverage` for code coverage (annotated RTL lines)
   - Use `parse_functional_coverage` for functional coverage (uncovered bins)
10. **Iterate**: Call `plan_coverage_strategy` again with the NEW uncovered bins,
    then refine sequences to target them

### UVM Sequence Patterns

**Constrained Random:**
```systemverilog
seq_item = <seq_item_class>::type_id::create("seq_item");
if (!seq_item.randomize()) `uvm_error(get_type_name(), "Randomization failed")
start_item(seq_item);
finish_item(seq_item);
```

**Directed with constraint override:**
```systemverilog
seq_item = <seq_item_class>::type_id::create("seq_item");
if (!seq_item.randomize() with {{ opcode == 4'h3; operand2 != 0; }})
  `uvm_error(get_type_name(), "Randomization failed")
start_item(seq_item);
finish_item(seq_item);
```

**Fully directed:**
```systemverilog
seq_item = <seq_item_class>::type_id::create("seq_item");
seq_item.opcode   = 4'h0;
seq_item.operand1 = 32'h7FFF_FFFF;
seq_item.operand2 = 32'h7FFF_FFFF;
seq_item.operand3 = 32'h0000_0001;
start_item(seq_item);
finish_item(seq_item);
```

### Bypassing Seq_Item Constraints for Hard-to-Reach Bins

The seq_item may have hard constraints that prevent certain value combinations
via `randomize()`. If a coverage bin requires a combination that conflicts with
a seq_item constraint, you have TWO options — use them in this order:

**Option 1 (preferred): Direct field assignment — bypasses ALL constraints:**
```systemverilog
// Constraints only apply during randomize(). Direct assignment skips them entirely.
// The driver will still send the transaction to the DUT — it does not re-check constraints.
seq_item = <seq_item_class>::type_id::create("force_corner_case");
seq_item.opcode   = 4'h3;   // e.g., DIV
seq_item.operand2 = 32'sd0; // would be blocked by randomize(), but direct assign works
start_item(seq_item);
finish_item(seq_item);
```

**Option 2: Disable the constraint with `constraint_mode(0)`:**
```systemverilog
seq_item = <seq_item_class>::type_id::create("corner_case");
seq_item.<constraint_name>.constraint_mode(0);  // disable the blocking constraint
if (!seq_item.randomize() with {{ opcode == 4'h3; operand2 == 0; }})
  `uvm_error(get_type_name(), "Randomization failed")
start_item(seq_item);
finish_item(seq_item);
```

**IMPORTANT**: If a `randomize() with {{...}}` call fails (returns 0), the most
likely cause is a conflict with an existing seq_item constraint. Do NOT give up —
switch to direct field assignment to force the values through. Never leave a
coverage bin unhit because "the constraint prevents it."

### CODE STYLE — KEEP IT MINIMAL

Your generated SystemVerilog code is fed back into the conversation and consumes context tokens.
Write **compact, minimal code** to preserve context for more iterations:
- **NO block comments** (`/* ... */`), **NO decorative comment banners** (`//====`, `//----`, `// *** ...`).
- **NO per-line comments** unless the logic is genuinely non-obvious.
- Use a **single short `//` comment per task/section** at most (e.g., `// directed: div-by-zero`).
- **NO `$display` / `uvm_info` calls** in sequences unless you are actively debugging a specific failure.
- **NO explanatory prose** in your response text around the code. Just state which bins you are targeting, then write the files. Skip analysis paragraphs — the coverage report already tells the story.
- Keep sequences **short and targeted**: only generate stimulus for uncovered bins. Do NOT re-generate stimulus for bins already covered in previous iterations — merged coverage retains them.

### CRITICAL UVM RULES

- ❌ DO NOT modify the seq_item, monitor, agent, env, interface, scoreboard, or Top module
- ❌ DO NOT modify the driver — UNLESS you have called `request_infra_modification` and it returned success. Call this tool when you believe the driver protocol is blocking coverage bins.
- ❌ DO NOT define covergroups in your sequences (coverage is in the passive module)
- ❌ DO NOT use `$finish` in sequences (UVM handles simulation termination)
- ❌ DO NOT use `#include` or `` `include `` to include the sequence file in the test file (or vice versa). Both files are compiled separately via the .f file — including one in the other causes "multiply defined" errors.
- ✅ DO use `import uvm_pkg::*;` and `` `include "uvm_macros.svh" `` at the top of BOTH files
- ✅ DO use the exact seq_item class name and field names shown above
- ✅ DO write BOTH the sequence file AND the test file each iteration
- ✅ DO target specific coverage bins by studying the coverage module above
- ✅ DO use both constrained random AND directed transactions for best coverage
- ✅ DO use direct field assignment to bypass seq_item constraints for hard-to-reach bins
"""
