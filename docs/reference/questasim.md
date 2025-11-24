# QuestaSim simulator

Concrete `Simulator` for QuestaSim/ModelSim: drives vlog/vsim flows, collects UCDB coverage, and merges XML reports.

- `QuestaSim.compile`/`simulate`: compile design + testbench, run simulations, capture coverage databases.
- Coverage utilities: `generate_coverage_report`, `generate_merged_coverage_*`, and XML parsing helpers.
- Uses the same `ArtifactPlan` layout as Verilator for consistent paths across simulators.

::: llm_verif.questasim
