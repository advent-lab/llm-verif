# TODO

Use this file to track future work items and follow-ups that should not block the current change.

## Conventions
- Keep entries short, actionable, and scoped.
- Prefer linking to the relevant code/docs location or a design name in data/.
- Remove items once completed.

## Items

### Increase LangGraph Recursion Limit
The default recursion limit of 100 can be hit during long verification runs. Add configuration to increase this limit.

**Location**: When creating the graph in [src/graphs/react.py](../src/graphs/react.py) 

**Implementation**:
```python
graph.compile(recursion_limit=200)  # or make it configurable via .env
```

**Priority**: Low - Only needed for very long runs. Current workaround: reduce MAX_ITERATIONS.

### Path Traversal Validation
Add directory traversal protection to all file operation tools, similar to the validation in `write_file()`.

**Affected tools:**
- `read_file()` in [src/tools/filesystem.py](../src/tools/filesystem.py)
- `list_directory()` in [src/tools/filesystem.py](../src/tools/filesystem.py)
- `compile_design()` in [src/tools/simulation.py](../src/tools/simulation.py)
- `parse_coverage()` in [src/tools/analysis.py](../src/tools/analysis.py)

**Implementation approach:**
Use Python's `Path.is_relative_to()` to verify that resolved file paths stay within their intended boundaries (work_dir for work artifacts, design_dir for design files, etc.). This prevents attacks using `../` sequences to access files outside the intended directories.

**Example validation (from write_file):**
```python
full_path = (work_dir / path).resolve()
if not full_path.is_relative_to(work_dir.resolve()):
    return {"success": False, "error": "Security violation: Path escapes work directory"}
```

**Priority:** Medium - Important for production deployment when agents handle untrusted inputs or run in shared environments.

