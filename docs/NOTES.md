# Development Notes

Hardcoded elements and environment-specific configurations that may need adjustment.

---

## HPC-Specific Configuration

**Module loading in Verilator adapter** ([verilator_adapter.py:58-73](../src/simulators/verilator_adapter.py#L58-L73))
- Hardcoded `module load gcc-10.3.0-gcc-11.2.0` and `module load ccache-4.8.2-gcc-11.2.0`
- Required for ASU SOL HPC environment where Verilator needs specific GCC and ccache
- Commands run through bash with module loading: `source /etc/profile.d/modules.sh && module load ...`
- **Status:** ✅ Now robust with graceful degradation
  - Detects if module system exists before attempting to load
  - Provides warnings if modules fail to load
  - Falls back to system compilers on non-HPC environments
- **Future improvement:** Make module names configurable via environment variables

## Verilator Integration

**Status:** ✅ Tested and verified (2026-01-19)

**Workflow:**
1. Load modules: `gcc-10.3.0-gcc-11.2.0` and `ccache-4.8.2-gcc-11.2.0`
2. Compile: `verilator --binary --coverage-line -Wno-fatal --Mdir obj_dir <tb> <design>`
3. Simulate: `./obj_dir/V<module_name> +verilator+coverage+file+coverage.dat`
4. Convert: `verilator_coverage -write-info coverage.info coverage.dat`
5. Parse: LCOV format with line coverage (DA:line,hits)

**Key findings:**
- Binary naming: Verilator prepends "V" to top module name (tb_divider → Vtb_divider)
- Coverage accumulates across multiple runs to single .dat file
- Both GCC and ccache modules are REQUIRED for compilation
- Without ccache: make fails with "ccache: Command not found"

**Robustness improvements (2026-01-19):**
- ✅ Flexible testbench filtering (tb_*, *_tb.*, testbench*)
- ✅ Binary validation after compilation
- ✅ Smart binary discovery if expected name not found
- ✅ Coverage file size validation
- ✅ Enhanced error messages with %Error: extraction
- ✅ Tool existence verification (verilator_coverage)
- ✅ Comprehensive logging throughout workflow

**See:** [INTEGRATION_IMPROVEMENTS.md](INTEGRATION_IMPROVEMENTS.md) for details

---

## Logging Configuration

**Agent Interaction Logging** ([src/graphs/react.py:135-214](../src/graphs/react.py#L135-L214))

The agent interaction logs (API requests, responses, tool calls) are logged at **INFO level** to provide
visibility into the agent's decision-making process without requiring DEBUG level logging.

**Key logged information**:
- API REQUEST headers with iteration, attempt, coverage, and counter metrics
- Message type and content being sent to the LLM
- AGENT RESPONSE headers with the same metrics
- Tool calls requested by the agent
- Reasoning text from the agent (if present)

**Log format**:
```
INFO:root:================================================================================
INFO:root:API REQUEST [API Call #1 | Iter 1 | Attempt 1 | Coverage 0.0% | Failures: 0 | No Progress: 0]
INFO:root:================================================================================
INFO:root:[MESSAGE TYPE] HumanMessage
INFO:root:[CONTENT]
Begin verification. Start by reading the specification.

INFO:root:================================================================================

INFO:root:================================================================================
INFO:root:AGENT RESPONSE [API Call #1 | Iter 1 | Attempt 1 | Coverage 0.0% | Failures: 0 | No Progress: 0]
INFO:root:================================================================================
INFO:root:[TOOL CALLS] 1 tool(s) requested:

  1. read_file
INFO:root:     path: /path/to/spec.md
INFO:root:================================================================================
```

**OpenAI/LangChain Verbose Logging**:
At DEBUG level, the OpenAI and LangChain libraries log extensive details including the entire conversation
history on each API request. This cannot be easily suppressed. **Recommendation**: Use `LOG_LEVEL=INFO`
to see agent interactions without the verbose library internals.
