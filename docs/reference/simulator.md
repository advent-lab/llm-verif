# Simulator base

Abstract simulator interface shared by concrete implementations.

- `Simulator`: base class defining compile/run hooks, coverage parsing, artifact planning, and coverage merge contracts.
- `CoverageResponse`/`DU`: data structures for simulator results.
- Utilities for module name extraction and `$finish` detection that Verilator/QuestaSim rely on.

::: llm_verif.simulator
