# Verilator simulator

Concrete `Simulator` for Verilator: compiles SV with coverage flags, runs batches, and parses LCOV via `lcovparser`.

- `Verilator.compile`/`simulate`: build and run testbenches with optional constrained-random iterations.
- `merge_and_parse_*` helpers: stitch per-run coverage outputs for cross-iteration reporting.
- Uses `ArtifactPlan` to keep coverage artifacts organized under `work/`.

::: llm_verif.verilator
