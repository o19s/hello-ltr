# Notebook Testing Recommendations

## Executive Summary

This document evaluates notebook testing tools and strategies for the hello-ltr project, providing prioritized recommendations with benefit/cost analysis.

**Current State**: We have a custom notebook testing solution (`tests/notebooks/runner.py`) that handles port patching, cell transformation, and real-time streaming. Recent enhancements have added debug mode, dependency validation, and variable inspection capabilities.

**Key Problems**:
- ✅ **Partially Addressed**: Test environment differences (empty training sets, missing query IDs) - dependency validation helps catch these early
- ✅ **Addressed**: Need for cell patching at test time without modifying notebooks - implemented
- ✅ **Addressed**: Difficulty debugging what data was available when cells fail - debug mode (`NOTEBOOK_DEBUG_MODE`) provides variable state inspection

**High-Level Recommendation**: Continue enhancing our existing custom solution rather than adopting external tools. Our custom runner already provides capabilities that standard tools lack (port patching, cell transformation, dependency validation, debug mode). Focus on creating test fixtures for reliable test data and extracting reusable logic to library code.

## Current State Analysis

### Existing Custom Notebook Runner

Our custom solution (`tests/notebooks/runner.py`) provides:

**Features Implemented**:
- **Port Patching**: Automatically redirects connections to test ports (18983, 19200, 19201) instead of production ports
- **Cell Transformation**: Patches notebook cells at test time to handle test environment issues
- **Real-time Streaming**: Errors visible immediately during execution
- **Fail-fast Mode**: Can stop execution on first error (via `NOTEBOOK_FAIL_FAST` env var)
- **Progress Indicators**: Cell-by-cell execution logging with time estimates
- **Error Context**: Captures cell index, source code, and traceback for each error
- **Debug Mode**: Variable state inspection on errors (via `NOTEBOOK_DEBUG_MODE` env var) - ✅ **Implemented**
- **Dependency Validation**: Validates cell dependencies and critical operations before execution - ✅ **Implemented**
- **Validation Fail-fast**: Stops execution on validation errors by default (via `NOTEBOOK_VALIDATION_FAIL_FAST` env var) - ✅ **Implemented**
- **Variable Inspection**: Captures and displays variable states at error points when debug mode is enabled - ✅ **Implemented**

**Architecture**:
- Uses `nbconvert.preprocessors.ExecutePreprocessor` as base
- Custom `PatchedExecutePreprocessor` extends base with progress logging
- `_patch_notebook_cells_for_testing()` function transforms cells before execution
- Integrates with pytest via `notebook_runner` fixture

### Problems Encountered

1. **Test Environment Differences**
   - Notebooks work fine when run manually but fail in test environments
   - Empty training sets when documents don't exist in test index
   - Missing query IDs (e.g., hardcoded query ID 5 doesn't exist in test data)
   - Different data availability between manual runs and CI

2. **Cell Patching at Test Time**
   - Need to inject validation checks without modifying notebooks
   - Port patching must happen before any client initialization
   - Test-specific transformations (e.g., replacing `.loc[5, :]` with `.iloc[0]`)

3. **Debugging Difficulties** ✅ **Partially Addressed**
   - ~~Hard to see what data was available when a cell failed~~ → **Fixed**: Debug mode (`NOTEBOOK_DEBUG_MODE`) captures variable states
   - ~~No visibility into variable states at failure point~~ → **Fixed**: Variable inspection implemented (`inspect_notebook_variables`)
   - Error messages don't indicate what was expected vs. what was available → **Improved**: Debug mode shows variable states, but could be enhanced further

## Tool Evaluation

Based on engineering-focused comparison of Python notebook testing tools:

### testbook ⭐ (Most "Software-Engineer-Friendly")

**What it does**: Loads a notebook like a Python module, lets you run cells selectively and assert on variables.

**Strengths**:
- True unit-style testing with mocks, patches, and assertions
- Keeps tests outside notebooks
- Fine-grained control over individual cells
- Can test extracted functions independently

**Weaknesses**:
- More verbose setup
- Designed for testing extracted logic, not full notebook execution
- Doesn't solve our need for full notebook execution testing

**Fit for our needs**: ❌ Not suitable for full notebook execution. Could be useful for testing extracted logic if we move functions to library code.

### pytest-notebook

**What it does**: Treats `.ipynb` files as pytest test cases, executes notebooks and fails on exceptions.

**Strengths**:
- Dead-simple pytest integration
- Minimal configuration
- Easy CI adoption
- Supports preprocessors for cell transformation

**Weaknesses**:
- Very limited control over individual cells
- No direct access to variables
- Less flexible than our custom solution
- Would require significant refactoring to match our port patching needs

**Fit for our needs**: ⚠️ Partial fit. Could potentially replace parts of our solution, but we'd lose custom features and need to rebuild port patching infrastructure.

### nbval

**What it does**: Executes notebooks and compares outputs against a stored baseline.

**Strengths**:
- Excellent for reproducibility
- Strong regression protection
- Tight pytest integration

**Weaknesses**:
- Output diffs are noisy
- Requires careful output normalization
- Painful for stochastic notebooks
- Not relevant for our use case (we don't need output comparison)

**Fit for our needs**: ❌ Not relevant. We need execution testing, not output validation.

### NBtest

**What it does**: Allows test cells embedded in notebooks, inspired by unittest semantics.

**Strengths**:
- Very intuitive for scientists
- Tests live next to the code they validate
- Great for teaching & exploratory work

**Weaknesses**:
- Tests are harder to extract into CI
- Less common in production pipelines
- Encourages logic staying in notebooks

**Fit for our needs**: ❌ Not CI-friendly. Doesn't solve our problems.

### papermill / nbclient

**What it does**: Parameterized execution and low-level execution engine.

**Strengths**:
- Automation and pipelines
- Fast, flexible execution

**Weaknesses**:
- No testing primitives by itself
- No assertions or validation
- We already have execution capability

**Fit for our needs**: ⚠️ Already covered. We use `nbconvert` which provides similar execution capabilities.

## Recommendations with Priorities

### Medium Priority (1-2 months)

#### 3. Create Test Fixtures for Common Data Scenarios

**Problem**: Test environment differences cause failures (empty training sets, missing query IDs). Need reliable test data.

**Solution**:
- Create pytest fixtures providing mock training sets, query IDs, and feature loggers
- Provide fixtures for common scenarios (empty sets, single query, multiple queries, etc.)
- Allow notebooks to use fixtures when available in test environment

**Implementation**:
- Create `tests/fixtures/notebook_data.py` with pytest fixtures
- Provide fixtures like `mock_training_set`, `mock_query_ids`, `mock_feature_logger`
- Update notebook runner to inject fixtures as available variables
- Document how notebooks can use fixtures (optional, for test environments)

**Benefit**:
- More reliable tests (consistent test data)
- Easier to test edge cases (empty sets, single items, etc.)
- Reduced test environment differences
- Estimated time saved: 15-30 minutes per test debugging session

**Cost**:
- Implementation time: 12-16 hours
- Maintenance burden: Medium (fixtures need to be maintained)
- Risk: Medium (need to ensure fixtures don't mask real issues)

**ROI**: Medium - Improves test reliability but requires ongoing maintenance.

**Dependencies**: None - can be implemented independently.

#### 4. Extract Reusable Logic to Library Code

**Problem**: Notebooks contain reusable logic (e.g., `pairwise_transform`, `samples_from_training_data`) that's hard to test and maintain.

**Solution**:
- Move reusable functions to `ltr/` modules (e.g., `ltr/transforms.py`, `ltr/training.py`)
- Test extracted functions with pytest/testbook
- Update notebooks to import from library code
- Notebooks become simpler (orchestration/visualization only)

**Implementation**:
- Identify reusable functions in notebooks (e.g., `pairwise_transform`, `samples_from_training_data`, `compute_lambdas`)
- Extract to appropriate `ltr/` modules with proper documentation
- Write unit tests for extracted functions
- Update notebooks to import from library code
- Consider using testbook for testing extracted notebook functions

**Benefit**:
- Reusable code (can be used across notebooks and tests)
- Better testability (unit tests for logic, not full notebook execution)
- Notebooks become simpler (focus on orchestration/visualization)
- Easier maintenance (logic changes in one place)
- Estimated time saved: 30-60 minutes per refactoring session

**Cost**:
- Implementation time: 40-60 hours (significant refactoring effort)
- Maintenance burden: Low (once extracted, easier to maintain)
- Risk: Medium-High (need to ensure notebooks still work after extraction)

**ROI**: High - Long-term improvement in code quality and maintainability, but significant upfront cost.

**Dependencies**: None - can be done incrementally, one function at a time.

### Low Priority (3-6 months)

#### 5. Consider pytest-notebook Integration

**Problem**: Maintaining custom solution requires ongoing effort. Standard tools might reduce maintenance burden.

**Solution**:
- Evaluate if pytest-notebook's preprocessor API could replace parts of our custom solution
- Assess if we can use pytest-notebook while maintaining our custom features
- Consider hybrid approach (pytest-notebook for execution, custom preprocessors for patching)

**Implementation**:
- Research pytest-notebook's preprocessor API capabilities
- Create proof-of-concept showing port patching with pytest-notebook
- Evaluate if we can maintain all custom features with pytest-notebook
- If viable, plan migration strategy

**Benefit**:
- Standard tooling (less custom code to maintain)
- Community support and documentation
- Potential for better integration with pytest ecosystem

**Cost**:
- Implementation time: 20-40 hours (evaluation + potential migration)
- Maintenance burden: Unknown (depends on pytest-notebook's maintenance)
- Risk: High (may lose custom features, significant refactoring)

**ROI**: Low-Medium - Potential long-term benefit but high risk and cost.

**Dependencies**: Should evaluate after completing medium-priority items to understand full scope of custom features.

#### 6. Hybrid Pattern for New Notebooks

**Problem**: Long-term maintainability. Notebooks mixing logic and orchestration are harder to test and maintain.

**Solution**:
- New notebooks focus on orchestration/visualization
- Logic lives in library code with tests
- Follow pattern: Notebook = UI layer, Library code = logic & tests

**Implementation**:
- Document hybrid pattern in project guidelines
- Apply pattern to new notebooks going forward
- Existing notebooks can stay as-is (educational artifacts)
- Gradually refactor existing notebooks if they need significant changes

**Benefit**:
- Better long-term maintainability
- Easier testing (test logic, not notebooks)
- Clearer separation of concerns
- Estimated time saved: 20-40 minutes per new notebook

**Cost**:
- Implementation time: Low (only affects new notebooks, documentation effort)
- Maintenance burden: Low (pattern is self-enforcing)
- Risk: Low (only affects new development)

**ROI**: Medium - Long-term improvement in code quality, minimal upfront cost.

**Dependencies**: None - can be adopted immediately for new notebooks.

## Benefit/Cost Analysis Summary

| Recommendation | Priority | Benefit | Cost | ROI | Risk | Status |
|---------------|----------|---------|------|-----|------|--------|
| Create test fixtures | Medium | Medium (more reliable tests) | Medium (12-16 hours) | Medium | Medium | Not started |
| Extract reusable logic | Medium | High (better maintainability) | High (40-60 hours) | High | Medium-High | Not started |
| Consider pytest-notebook | Low | Low-Medium (standard tooling) | High (20-40 hours) | Low-Medium | High | Not started |
| Hybrid pattern for new notebooks | Low | Medium (long-term quality) | Low (documentation) | Medium | Low | Not started |

## Implementation Roadmap

### Phase 1: Short-term Enhancements (Completed)

**Completed Features**:
- ✅ **Debug Mode**: Variable state inspection on errors (`NOTEBOOK_DEBUG_MODE`)
- ✅ **Dependency Validation**: Cell dependency checking and operation validation (`NotebookDependencyValidator`)
- ✅ **Validation Fail-fast**: Stop execution on validation errors by default (`NOTEBOOK_VALIDATION_FAIL_FAST`)
- ✅ **Variable Inspection**: Capture and display variable states at error points (`inspect_notebook_variables`)

These enhancements address the immediate pain points mentioned in the "Short-term" recommendations, providing better error handling and debugging capabilities.

### Phase 2: Medium Priority (Months 1-2)

**Month 1**:
- Implement recommendation #3: Create test fixtures
  - Design fixture API for notebook data
  - Create `tests/fixtures/notebook_data.py`
  - Integrate fixtures with notebook runner
  - Document fixture usage

**Month 2**:
- Begin recommendation #4: Extract reusable logic
  - Identify top 3-5 reusable functions
  - Extract first function to library code
  - Write unit tests
  - Update notebooks to use extracted function
  - Repeat for remaining functions

**Deliverables**:
- Test fixtures for common data scenarios
- First batch of extracted functions with tests
- Updated notebooks using extracted functions

### Phase 3: Low Priority (Months 3-6)

**Months 3-4**:
- Evaluate recommendation #5: pytest-notebook integration
  - Research pytest-notebook capabilities
  - Create proof-of-concept
  - Make decision on migration

**Months 5-6**:
- Implement recommendation #6: Hybrid pattern
  - Document hybrid pattern guidelines
  - Apply to any new notebooks
  - Continue extracting reusable logic (ongoing)

**Deliverables**:
- Decision on pytest-notebook (adopt or reject)
  - Hybrid pattern documentation
  - Additional extracted functions

## Decision Matrix

| Tool/Approach | Fits Our Needs? | Implementation Effort | Maintenance Burden | Recommendation |
|--------------|----------------|----------------------|-------------------|----------------|
| **Current Custom Solution** | ✅ Yes | ✅ Already implemented | Medium | ✅ **Keep and enhance** |
| **testbook** | ❌ No (full notebook execution) | Low (if used for extracted logic) | Low | ⚠️ Consider for extracted logic only |
| **pytest-notebook** | ⚠️ Partial | High (migration effort) | Low-Medium | ⚠️ Evaluate later, not urgent |
| **nbval** | ❌ No (output comparison) | N/A | N/A | ❌ Not relevant |
| **NBtest** | ❌ No (CI-unfriendly) | N/A | N/A | ❌ Not suitable |
| **papermill/nbclient** | ⚠️ Already covered | N/A | N/A | ✅ Already using nbconvert |
| **Enhanced Custom Solution** | ✅ Yes | Low-Medium | Medium | ✅ **Recommended** |
| **Hybrid Pattern** | ✅ Yes | Low (documentation) | Low | ✅ **Recommended for new notebooks** |

## Conclusion

**Recommended Path Forward**:

1. **✅ Short-term (Completed)**: Enhanced our existing custom solution with better error handling and debugging capabilities:
   - Debug mode for variable state inspection (`NOTEBOOK_DEBUG_MODE`)
   - Dependency validation to catch issues early (`NotebookDependencyValidator`)
   - Validation fail-fast to prevent cascading failures (`NOTEBOOK_VALIDATION_FAIL_FAST`)
   - Variable inspection on errors for better debugging

2. **Medium-term (Months 1-2)**: Create test fixtures for reliable test data and begin extracting reusable logic to library code. This improves test reliability and code maintainability.

3. **Long-term (Months 3-6)**: Evaluate pytest-notebook integration (low priority) and adopt hybrid pattern for new notebooks. This ensures long-term maintainability without disrupting existing workflows.

**Rationale**:

- Our custom solution already provides capabilities that standard tools lack (port patching, cell transformation)
- Standard tools (testbook, pytest-notebook) don't fully address our needs for full notebook execution testing
- ✅ **Completed**: Enhanced our existing solution with debug mode, dependency validation, and variable inspection
- Extracting reusable logic improves testability without requiring tool changes
- Hybrid pattern for new notebooks ensures long-term maintainability

**Key Success Metrics**:
- Reduced debugging time (target: 50% reduction)
- Fewer cascading failures (target: eliminate cascading failures)
- Improved test reliability (target: 90%+ pass rate)
- Better code maintainability (target: 50% of reusable logic extracted)

This approach balances immediate improvements with long-term maintainability while leveraging our existing investment in custom tooling.

