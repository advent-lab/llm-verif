# RAG Integration Plan - Concise Version

## Overview

**Goal**: Integrate the existing `vector_store.py` module to replace large static context injection with dynamic retrieval, reducing token usage by 70-80% while maintaining coverage quality.

**Status**: VectorStore implementation is complete and production-ready. We just need to wire it into the existing prompt pipeline.

---

## 1. What Stays in System Prompt vs. What Moves to RAG

### Always in System Prompt (~1.5K tokens)
- Task instructions (what the LLM should do)
- JSON output format requirements
- Module header/interface definition
- Testbench template structure

**Why**: These are required for every single interaction and must be consistently available.

### Move to RAG (Retrieved on-demand)
- **Full specification** (currently 10-15K tokens → 1-2K via top-5 chunks)
- **Design code** (currently 15-25K tokens → 2-3K via coverage-guided retrieval)
- **Protocol details** (retrieved when relevant to current task)
- **Test plan examples** (retrieved during test plan generation)

**Why**: Most content is irrelevant to the current task. RAG retrieves only what's needed.

---

## 2. Integration Tasks

### Task 1: Environment Initialization
**File**: `llm_verif/environment.py`

**What**: Add VectorStore initialization in the Environment class

**Why**: Need a single vector store instance available to all prompt generation functions

**How**:
- Add `enable_rag` and related config attributes (chunk_size, top_k, model_name)
- Create `_initialize_vector_store()` method that:
  - Creates VectorStore instance pointing to design directory
  - Tries to load existing index from `.ragindex/{design_name}/`
  - If no index exists, builds new one from design files (specs, RTL, etc.)
  - Saves index for future runs
- Call during `__init__()` if `--enable_rag` flag is set
- Store reference to vector_store for later use

---

### Task 2: RAG-Enhanced System Prompt
**File**: `llm_verif/prompt_templates.py`

**What**: Create new `system_prompt_rag()` function

**Why**: Initial system prompt currently injects full specification (10K+ tokens). Need to replace with relevant chunks only.

**How**:
- Query vector store with: "{module_name} specification requirements interface behavior"
- Retrieve top-5 chunks from specification documents
- Format chunks with source attribution
- Build system prompt using base template + retrieved chunks + module header
- Keep same structure as original `system_prompt()` but with RAG content

**Alternative**: Modify existing `system_prompt()` to accept optional vector_store parameter and branch based on RAG mode.

---

### Task 3: Coverage-Guided Design Retrieval
**File**: `llm_verif/prompt_templates.py`

**What**: Create `design_prompt_rag()` function

**Why**: Currently injects entire design codebase (20K+ tokens) after first testbench. Most code is irrelevant to specific coverage gaps.

**How**:
- Extract uncovered areas from CoverageResponse (uncovered functions, lines, states)
- For each coverage gap, query vector store: "implementation of {gap}"
- Retrieve top-2 chunks per gap (total ~10 chunks)
- Deduplicate chunks from same file
- Format with file paths and return as context string
- Only include if coverage < threshold (e.g., 90%)

**Key**: This is triggered by coverage feedback, not unconditionally.

---

### Task 4: Wire RAG into Conversation Flow
**File**: `llm_verif/conversation_runner.py`

**What**: Modify three prompt injection points

**Why**: Need to actually use the RAG functions we created

**How**:

**Point 1 - Initial system prompt (line ~192)**:
- Check if `environment.enable_rag` is true
- If yes, call `system_prompt_rag()` with vector_store
- If no, call original `system_prompt()` with full spec

**Point 2 - Design code injection (line ~238-242)**:
- Currently injects all design files after first successful testbench
- If RAG enabled, call `design_prompt_rag()` with coverage_response
- Only inject if relevant chunks found for coverage gaps
- If RAG disabled, keep existing behavior (inject all design files)

**Point 3 - Iteration prompts (line ~244-252)**:
- When RAG enabled, include targeted design context based on current gaps
- Call `design_prompt_rag()` for each iteration with updated coverage
- Helps LLM focus on uncovered areas

---

### Task 5: Add ConversationManager Support
**File**: `llm_verif/conversation_manager.py`

**What**: Add `append_system_context()` method

**Why**: Need way to inject RAG-retrieved design chunks as system messages during conversation

**How**:
- Accept context string as parameter
- Append as system role message to conversation history
- Update token count
- Similar to existing append methods but for system context

---

### Task 6: CLI Arguments
**File**: `llm_verif/llm_verif.py`

**What**: Add command-line arguments for RAG configuration

**Why**: Users need to enable/configure RAG behavior

**How**: Add argparse arguments for:
- `--enable_rag`: Enable RAG mode (boolean flag)
- `--rag_top_k`: Number of chunks to retrieve (default: 5)
- `--rag_chunk_size`: Chunk size in tokens (default: 256)
- `--rag_chunk_overlap`: Overlap between chunks (default: 32)
- `--rag_model`: Embedding model name (default: all-MiniLM-L6-v2)
- `--rebuild_rag_index`: Force rebuild of index (boolean flag)

---

### Task 7: Test Plan RAG Enhancement (Optional but Recommended)
**File**: `llm_verif/prompt_templates.py` and `conversation_runner.py`

**What**: Add `verification_plan_prompt_rag()` function

**Why**: LLM generates better test plans when shown examples

**How**:
- Query vector store for: "verification test plan for {design_type}"
- Retrieve top-3 example test plans
- Include in prompt as examples to follow
- Use during test plan generation phase (line ~202 in conversation_runner.py)

**Future Enhancement**: Save generated test plans back to corpus for cumulative learning.

---

### Task 8: Iterative Refinement RAG (Optional but Recommended)
**File**: `llm_verif/prompt_templates.py`

**What**: Create `iter_prompt_rag()` function

**Why**: When coverage is low, LLM needs targeted design context to understand what to test

**How**:
- Take base iteration prompt (coverage feedback)
- If coverage < 90%, extract specific gaps
- Query vector store for implementation of uncovered areas
- Append relevant design chunks to iteration prompt
- Helps LLM understand what code it needs to target

---

## 3. Testing Requirements

### Unit Tests
**File**: `tests/test_rag_integration.py`

**What**: Test each RAG component in isolation

**Tests Needed**:
- VectorStore initialization and index build/load
- `system_prompt_rag()` returns shorter, relevant prompt
- `design_prompt_rag()` retrieves chunks based on coverage gaps
- End-to-end token reduction (with vs without RAG)

**Why**: Catch regressions and validate RAG behavior

---

### Integration Testing
**What**: Run full verification flows on real designs with/without RAG

**Why**: Ensure RAG doesn't degrade coverage quality while reducing tokens

**Metrics to Track**:
- Total token usage (expect 70-80% reduction)
- Final coverage achieved (should be ≥ baseline)
- Iterations to convergence (should improve or stay same)
- Compilation success rate (should not degrade)

**How**: Create benchmark script that runs same design twice (RAG on/off) and compares results.

---

## 4. Key Design Decisions

### Decision 1: Single Index per Design
**Choice**: One vector store index per design, stored in `.ragindex/{design_name}/`

**Why**:
- Different designs have different specs/code
- Allows caching (first run builds, subsequent runs load instantly)
- Avoids mixing content from different designs

**Alternative Rejected**: Global index across all designs (would retrieve irrelevant content)

---

### Decision 2: Coverage-Triggered Design Injection
**Choice**: Only inject design code when coverage gaps exist

**Why**:
- Early iterations don't need design internals (just spec and interface)
- Coverage feedback tells us exactly what's missing
- Targeted retrieval is more effective than blanket injection

**Alternative Rejected**: Always inject design chunks (wastes tokens, adds noise)

---

### Decision 3: Hybrid Spec Approach
**Choice**: Keep 1-paragraph spec summary in system prompt, retrieve details via RAG

**Why**:
- LLM always has high-level context
- Details retrieved when needed
- Best of both worlds (context + efficiency)

**Alternative Rejected**: Full RAG with no summary (LLM might miss big picture)

---

### Decision 4: Fallback to Non-RAG
**Choice**: If RAG operations fail, gracefully degrade to original behavior

**Why**:
- Index build might fail on some systems
- Retrieval might return empty results
- Should never crash, always generate testbenches

**How**: Wrap RAG calls in try/except, log warnings, use original prompts on failure

---

## 5. Corpus Organization

### Current State
Design files scattered across:
- Specs in locations defined by dashboard.json
- Design files in design directory
- No test plan storage

### RAG Needs
Vector store points to design directory and indexes:
- All spec files (PDF, MD, TXT)
- All design files (SV, V, VH, SVH)
- Config files if present (HJSON)

### Future Enhancement
Create `testplans/` subdirectory to save generated test plans:
- Save each generated test plan to `{design_dir}/testplans/plan_iterN.txt`
- On next run, these get indexed and used as examples
- Cumulative learning across runs

---

## 6. Error Handling

### Index Build Failures
- **Cause**: Corpus directory doesn't exist, no supported files, embedding model fails
- **Handling**: Log error, disable RAG for this run, fall back to non-RAG mode

### Retrieval Failures
- **Cause**: Empty index, query fails, network issues (for model download)
- **Handling**: Return empty chunks, use original prompt functions

### Malformed Coverage Data
- **Cause**: Coverage parser returns unexpected format
- **Handling**: Extract what we can, fall back to generic queries if gaps unclear

**General Principle**: RAG should never crash the system. It's an enhancement, not a requirement.

---

## 7. Performance Considerations

### First Run
- Index build takes 30-60 seconds (depends on corpus size)
- Embeddings generated and FAISS index built
- Saved to disk for future runs

### Subsequent Runs
- Index loads in <2 seconds
- Only rebuild if `--rebuild_rag_index` flag set or corpus modified

### Query Performance
- Each retrieval: 50-100ms
- Multiple queries per iteration (spec, design, gaps)
- Total RAG overhead: 200-300ms per iteration
- Negligible compared to LLM inference time (10-30 seconds)

### GPU Acceleration
- VectorStore auto-detects GPU and uses if available
- GPU embedding generation 5-10x faster than CPU
- Falls back to CPU gracefully if no GPU

---

## 8. Dependencies

### Required Additions to pyproject.toml
- `faiss-cpu>=1.7.4` (or `faiss-gpu` if CUDA available)
- `sentence-transformers>=2.2.0`

### Optional (Already Handled)
- `PyMuPDF` - for PDF processing (optional, graceful degradation)
- `pdfplumber` - for PDF tables (optional)
- `hjson` - for HJSON files (optional)

**Installation**: `pip install -e .` after updating pyproject.toml

---

## 9. Future Enhancements (Not in Initial Integration)

### Code-Specific Embeddings
Replace general sentence-transformers model with code-specific model (CodeBERT, GraphCodeBERT) for better Verilog understanding.

### Syntax-Aware Chunking
Respect function/module boundaries instead of splitting at token counts. Requires Verilog parser.

### Incremental Index Updates
When new test plans generated, update index incrementally instead of full rebuild.

### Cross-Design Learning
Global corpus of successful testbenches that can be queried across designs.

### Feedback-Driven Re-ranking
Track which chunks led to coverage improvements and boost their scores in future retrievals.

---

## 10. Success Criteria

### Must Achieve
- [ ] Token usage reduced by ≥60% compared to baseline
- [ ] Coverage quality maintained (no >5% degradation)
- [ ] System runs with `--enable_rag` without crashes
- [ ] Index persists and loads correctly
- [ ] Retrieved chunks are relevant (manual inspection)

### Nice to Have
- [ ] Coverage quality improves slightly
- [ ] Fewer iterations to reach target coverage
- [ ] Test plan quality improves (subjective evaluation)

---

## Summary

The integration is straightforward because:
1. **VectorStore is done** - fully implemented and tested
2. **Clear integration points** - 4 main files to modify
3. **Additive changes** - not refactoring existing code
4. **Graceful fallbacks** - can always revert to non-RAG mode

The work is mostly **wiring** existing components together, not building new infrastructure.

**Estimated Effort**: 3-5 days with testing and validation.
