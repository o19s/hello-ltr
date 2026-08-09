# Remaining Dependency Updates Available

**Date:** December 31, 2025  
**Status:** Phase 1 Complete ✅ | Phase 2 & 3 Pending

---

## Summary

Based on `uv pip list --outdated`, there are **many** dependencies with updates available. This document categorizes them by priority and risk level.

---

## 🔴 High Priority - Security or Critical Updates

### 1. **defusedxml** (Security Library)
- **Current:** `0.5.0`
- **Latest:** `0.7.1`
- **Type:** Security library for safe XML parsing
- **Risk:** 🟡 Medium - Security library, should be updated
- **Breaking Changes:** Possible (major version jump)
- **Recommendation:** ✅ **UPDATE** - Review release notes for breaking changes

### 2. **MarkupSafe** (Security)
- **Current:** `2.0.1`
- **Latest:** `3.0.3`
- **Type:** Security library for safe string handling
- **Risk:** 🟡 Medium - Security library, major version bump
- **Breaking Changes:** Likely (2.x → 3.x)
- **Recommendation:** ⚠️ **REVIEW** - Check Jinja2 compatibility (Jinja2==3.0.3 may require MarkupSafe 2.x)

### 3. **decorator** (Utility)
- **Current:** `4.3.2`
- **Latest:** `5.2.1`
- **Type:** Utility library
- **Risk:** 🟡 Medium - Major version bump
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check if used directly or transitively

---

## 🟠 Low Priority - Major Version Bumps (Require Testing)

### 17. **numpy** (Major Update)
- **Current:** `1.26.4` (constrained `>=1.24.0,<2.0.0`)
- **Latest:** `2.4.0`
- **Type:** Numerical computing (CRITICAL)
- **Risk:** 🔴 **HIGH** - Major version bump (1.x → 2.x)
- **Breaking Changes:** **YES** - Major breaking changes
- **Note:** Currently constrained to `<2.0.0` in pyproject.toml
- **Recommendation:** ⚠️ **DEFER** - Requires comprehensive testing, may break code

### 18. **scikit-learn** (Major Update)
- **Current:** `1.3.2` (constrained `>=1.3.2`)
- **Latest:** `1.8.0`
- **Type:** Machine learning (CRITICAL)
- **Risk:** 🟡 Medium - Major minor version update
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check release notes, test thoroughly

### 19. **elasticsearch** (Major Update)
- **Current:** `7.16.2` (pinned)
- **Latest:** `9.2.1`
- **Type:** Search engine client (CRITICAL)
- **Risk:** 🔴 **HIGH** - Major version bump (7.x → 9.x)
- **Breaking Changes:** **YES** - Major API changes
- **Note:** Currently pinned for compatibility
- **Recommendation:** ⚠️ **DEFER** - Requires significant code changes

### 20. **opensearch-py** (Major Update)
- **Current:** `2.2.0` (pinned)
- **Latest:** `3.1.0`
- **Type:** Search engine client (CRITICAL)
- **Risk:** 🔴 **HIGH** - Major version bump (2.x → 3.x)
- **Breaking Changes:** **YES** - Major API changes
- **Note:** Currently pinned for compatibility
- **Recommendation:** ⚠️ **DEFER** - Requires significant code changes

### 21. **ipython** (Major Update)
- **Current:** `8.21.0` (constrained `>=8.12.0`)
- **Latest:** `9.8.0`
- **Type:** Interactive Python shell
- **Risk:** 🟡 Medium - Major version bump
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check if notebooks require IPython 8.x

### 22. **plotly** (Major Update)
- **Current:** `5.5.0` (pinned)
- **Latest:** `6.5.0`
- **Type:** Plotting library
- **Risk:** 🟡 Medium - Major version bump
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check if notebooks use plotly

### 23. **plotnine** (Major Update)
- **Current:** `0.12.2` (pinned)
- **Latest:** `0.15.2`
- **Type:** Plotting library
- **Risk:** 🟡 Medium - Major minor version update
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check if notebooks use plotnine

### 24. **mizani** (Major Update)
- **Current:** `0.9.2` (pinned)
- **Latest:** `0.14.3`
- **Type:** Plotting utilities (used by plotnine)
- **Risk:** 🟡 Medium - Major minor version update
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Update with plotnine

### 25. **pyzmq** (Major Update)
- **Current:** `25.1.1` (pinned)
- **Latest:** `27.1.0`
- **Type:** ZeroMQ bindings (used by Jupyter)
- **Risk:** 🟡 Medium - Major version bump
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check Jupyter compatibility

### 26. **terminado** (Major Update)
- **Current:** `0.13.1` (pinned)
- **Latest:** `0.18.1`
- **Type:** Terminal emulator (used by Jupyter)
- **Risk:** 🟡 Medium - Major minor version update
- **Breaking Changes:** Possible
- **Recommendation:** ⚠️ **REVIEW** - Check Jupyter compatibility (Phase 2)

### 27. **urllib3** (Major Update)
- **Current:** `1.26.18` (pinned)
- **Latest:** `2.6.2`
- **Type:** HTTP library (CRITICAL)
- **Risk:** 🔴 **HIGH** - Major version bump (1.x → 2.x)
- **Breaking Changes:** **YES** - Major breaking changes
- **Note:** Currently pinned to 1.x for elasticsearch 7.16.2 compatibility
- **Recommendation:** ⚠️ **DEFER** - Update with elasticsearch/opensearch-py

### 28. **xgboost** (Major Update)
- **Current:** `1.7.6` (pinned)
- **Latest:** `3.1.2`
- **Type:** Machine learning library (CRITICAL)
- **Risk:** 🔴 **HIGH** - Major version bump (1.x → 3.x)
- **Breaking Changes:** **YES** - Major API changes
- **Note:** Currently pinned
- **Recommendation:** ⚠️ **DEFER** - Requires comprehensive testing

*Note: Several major version updates have been completed. Phase 1 updates (31 dependencies) were successfully completed and tested on December 21, 2025.*

---

## 📋 Jupyter Ecosystem Updates

These are part of the Jupyter ecosystem and should be updated together:

- ⚠️ **jupyter-client**: `8.6.3` → `8.7.0` - **DEFERRED** (8.7.0 requires Python >=3.10, project supports >=3.9)
- ⚠️ **jupyter-events**: `0.6.3` → `0.12.0` ⚠️ Review (Phase 2)
- ⚠️ **jupyter-server**: `2.7.0` → `2.17.0` ⚠️ Review (Phase 2)

*Note: notebook and tornado updates have been completed as part of Phase 1 (December 21, 2025). jupyterlab is not currently in the outdated list.*

---

## 🎯 Recommended Update Strategy

### Phase 1: Safe Updates (Low Risk) ✅ **COMPLETE**

**Note:** All Phase 1 updates have been completed (December 21, 2025). A total of 31 dependencies were successfully updated and tested with no breaking changes detected.

**Deferred:**
- ⚠️ **DEFERRED** jupyter-client: `8.6.3` → `8.7.0` (8.7.0 requires Python >=3.10, project supports >=3.9)

### Phase 2: Review Required (Medium Risk)
Review release notes and test:
1. ⚠️ defusedxml: `0.5.0` → `0.7.1` (security library)
2. ⚠️ MarkupSafe: `2.0.1` → `3.0.3` (check Jinja2 compatibility)
3. ⚠️ decorator: `4.3.2` → `5.2.1` (check usage)
4. ⚠️ scikit-learn: `1.3.2` → `1.8.0` (check release notes)
5. ⚠️ terminado: `0.13.1` → `0.18.1` (check Jupyter compatibility)
6. ⚠️ ipython: `8.21.0` → `9.8.0` (check notebook compatibility)

### Phase 3: Major Updates (High Risk - Defer)
Require significant testing and possible code changes:
1. 🔴 numpy: `1.26.4` → `2.4.0` (currently constrained to <2.0.0)
2. 🔴 elasticsearch: `7.16.2` → `9.2.1` (major API changes)
3. 🔴 opensearch-py: `2.2.0` → `3.1.0` (major API changes)
4. 🔴 urllib3: `1.26.18` → `2.6.2` (update with elasticsearch/opensearch-py)
5. 🔴 xgboost: `1.7.6` → `3.1.2` (major API changes)
6. 🔴 plotly: `5.5.0` → `6.5.0` (check notebook usage)
7. 🔴 plotnine: `0.12.2` → `0.15.2` (check notebook usage)
8. 🔴 mizani: `0.9.2` → `0.14.3` (update with plotnine)
9. 🔴 pyzmq: `25.1.1` → `27.1.0` (check Jupyter compatibility)

---

## 🟢 Safe Patch/Minor Updates (Low Risk)

These are safe patch or minor version updates that can be applied with minimal risk:

- ✅ **coverage**: `7.13.0` → `7.13.1` (patch)
- ✅ **cython**: `3.2.2` → `3.2.3` (patch)
- ✅ **debugpy**: `1.8.18` → `1.8.19` (patch)
- ✅ **filelock**: `3.20.0` → `3.20.1` (patch)
- ✅ **jedi**: `0.19.1` → `0.19.2` (patch)
- ✅ **mistune**: `3.1.4` → `3.2.0` (minor)
- ✅ **nbclient**: `0.10.2` → `0.10.4` (patch)
- ✅ **nodeenv**: `1.9.1` → `1.10.0` (minor)
- ✅ **pip**: `24.3.1` → `25.3` (major, but pip updates are generally safe)
- ✅ **pre-commit**: `4.5.0` → `4.5.1` (patch)
- ✅ **psutil**: `7.1.3` → `7.2.1` (minor)
- ✅ **pyparsing**: `3.3.0` → `3.3.1` (patch)
- ✅ **ruff**: `0.14.9` → `0.14.10` (patch)
- ✅ **send2trash**: `1.8.3` → `2.0.0` (major, but likely safe)
- ✅ **soupsieve**: `2.8` → `2.8.1` (patch)
- ✅ **testpath**: `0.5.0` → `0.6.0` (minor)
- ✅ **threadpoolctl**: `3.1.0` → `3.6.0` (minor)
- ✅ **tinycss2**: `1.4.0` → `1.5.1` (minor)
- ✅ **tqdm**: `4.62.3` → `4.67.1` (minor)
- ✅ **traitlets**: `5.9.0` → `5.14.3` (minor)
- ✅ **types-requests**: `2.31.0.6` → `2.32.4.20250913` (minor)
- ✅ **tzdata**: `2025.2` → `2025.3` (timezone data update)
- ✅ **wcwidth**: `0.2.5` → `0.2.14` (minor)

**Recommendation:** These can be updated as part of a future Phase 1 batch update.

---

## Summary Statistics

- **Total outdated packages:** ~40+
- **Phase 1 (Safe updates):** ✅ **31 packages updated** (1 deferred: jupyter-client 8.7.0 requires Python >=3.10) - Completed December 21, 2025
- **Phase 1b (Additional safe updates):** ⏳ **22 packages** available for batch update
- **Phase 2 (Review required):** ⏳ **6 packages** pending review
- **Phase 3 (Major updates):** ⏳ **9 packages** deferred

---

## Update Progress

### ✅ Phase 1: COMPLETE (December 21, 2025)
- **Updated:** 31 dependencies (1 deferred: jupyter-client 8.7.0 requires Python >=3.10)
- **Tests Passing:** 84+ tests (all critical paths verified)
- **Breaking Changes:** 0
- **Status:** ✅ Successfully completed and tested

**Details:** Phase 1 included security-critical updates (certifi, urllib3), additional security & utility updates (attrs, bleach, chardet, idna, pytz), and 24 safe patch/minor updates. All updates were tested with 84+ tests passing and no breaking changes detected.

### ⏳ Phase 2: PENDING
Medium-risk dependencies requiring review and testing:
1. ⚠️ defusedxml: `0.5.0` → `0.7.1` (security library)
2. ⚠️ MarkupSafe: `2.0.1` → `3.0.3` (check Jinja2 compatibility)
3. ⚠️ decorator: `4.3.2` → `5.2.1` (check usage)
4. ⚠️ scikit-learn: `1.3.2` → `1.8.0` (check release notes)
5. ⚠️ terminado: `0.13.1` → `0.18.1` (check Jupyter compatibility)
6. ⚠️ ipython: `8.21.0` → `9.8.0` (check notebook compatibility)

### ⏳ Phase 3: DEFERRED
Major updates requiring significant testing and code changes:
1. 🔴 numpy: `1.26.4` → `2.4.0` (currently constrained to <2.0.0)
2. 🔴 elasticsearch: `7.16.2` → `9.2.1` (major API changes)
3. 🔴 opensearch-py: `2.2.0` → `3.1.0` (major API changes)
4. 🔴 urllib3: `1.26.18` → `2.6.2` (update with elasticsearch/opensearch-py)
5. 🔴 xgboost: `1.7.6` → `3.1.2` (major API changes)
6. 🔴 plotly: `5.5.0` → `6.5.0` (check notebook usage)
7. 🔴 plotnine: `0.12.2` → `0.15.2` (check notebook usage)
8. 🔴 mizani: `0.9.2` → `0.14.3` (update with plotnine)
9. 🔴 pyzmq: `25.1.1` → `27.1.0` (check Jupyter compatibility)

---

## Next Steps

1. ✅ **Phase 1:** ✅ **COMPLETE** - All safe packages updated (December 21, 2025) - 31 dependencies updated successfully
2. ⏳ **Phase 1b:** Consider batch update of 22 additional safe patch/minor updates
3. ⏳ **Phase 2:** Review and test medium-risk packages (next priority)
4. ⏳ **Phase 3:** Plan major updates as separate projects (future work)

---

## Related Documents

- `pyproject.toml` - Current dependency versions and constraints
- `CHANGELOG.md` - Project changelog (may include dependency update notes)

