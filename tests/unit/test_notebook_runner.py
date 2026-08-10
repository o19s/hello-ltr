"""
Unit tests for notebook runner functionality, including debug mode.

Tests the PatchedExecutePreprocessor and debug mode features.
"""

import os
from unittest.mock import MagicMock, patch

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from tests.notebooks.runner import (
    PatchedExecutePreprocessor,
    _patch_notebook_cells_for_testing,
    diverse_judgment_sample,
    inspect_notebook_variables,
    run_notebook,
    safe_kcv_folds,
)


class TestDebugMode:
    """Tests for debug mode functionality."""

    def test_debug_mode_disabled_by_default(self):
        """Test that debug mode is disabled by default."""
        # Clear environment variable to ensure default
        with patch.dict(os.environ, {}, clear=True):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is False

    def test_debug_mode_enabled_via_env_var(self):
        """Test that debug mode can be enabled via NOTEBOOK_DEBUG_MODE environment variable."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "1"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "yes"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

    def test_debug_mode_disabled_via_env_var(self):
        """Test that debug mode can be explicitly disabled."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "false"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is False

    def test_debug_mode_parameter_override(self):
        """Test that debug_mode parameter overrides environment variable."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            preprocessor = PatchedExecutePreprocessor(debug_mode=False)
            assert preprocessor.debug_mode is False

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "false"}, clear=False):
            preprocessor = PatchedExecutePreprocessor(debug_mode=True)
            assert preprocessor.debug_mode is True

    def test_kernel_manager_stored_when_debug_mode_enabled(self):
        """Test that kernel manager is stored when debug mode is enabled."""
        preprocessor = PatchedExecutePreprocessor(debug_mode=True)
        mock_km = MagicMock()
        mock_nb = nbformat.v4.new_notebook()
        mock_nb.cells = [nbformat.v4.new_code_cell("print('test')")]

        # Stub the parent implementation. This test covers only the bookkeeping
        # done by our override; letting the real ExecutePreprocessor.preprocess
        # run would drive nbclient's event loop against a MagicMock kernel
        # client, which never returns a matching reply and hangs forever.
        with patch.object(
            ExecutePreprocessor, "preprocess", return_value=(mock_nb, {})
        ):
            preprocessor.preprocess(mock_nb, resources={}, km=mock_km)

        assert preprocessor.kernel_manager is mock_km

    def test_inspect_notebook_variables_no_kernel_manager(self):
        """Test that inspect_notebook_variables handles missing kernel manager gracefully."""
        result = inspect_notebook_variables(None)
        assert "error" in result
        assert "No kernel manager available" in result["error"]

    def test_inspect_notebook_variables_no_client(self):
        """Test that inspect_notebook_variables handles kernel manager without client."""
        mock_km = MagicMock()
        mock_km.client = None

        result = inspect_notebook_variables(mock_km)
        assert "error" in result
        assert "doesn't have a client available" in result["error"]

    def test_inspect_notebook_variables_execution_error(self):
        """Test that inspect_notebook_variables handles execution errors gracefully."""
        mock_km = MagicMock()
        mock_client = MagicMock()
        mock_km.client = mock_client

        # Simulate execution error
        mock_client.execute.side_effect = Exception("Kernel error")

        result = inspect_notebook_variables(mock_km)
        assert "error" in result
        assert "Exception while inspecting variables" in result["error"]


class TestDebugModeIntegration:
    """Integration tests for debug mode with actual notebook execution."""

    def test_debug_mode_captures_variables_on_error(self, tmp_path):
        """Test that debug mode captures variable states when a cell fails."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell(
                "# Set up some variables\nftr_logger = type('obj', (object,), {'logged': [1, 2, 3]})()\ntraining_set = [1, 2, 3]"
            ),
            nbformat.v4.new_code_cell(
                "# This will fail\nraise ValueError('Test error')"
            ),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        # Run with debug mode enabled
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            # Capture stderr to check for debug output
            import sys
            from io import StringIO

            old_stderr = sys.stderr
            sys.stderr = captured_stderr = StringIO()

            try:
                # Run notebook (will fail, but we want to see debug output).
                # fail_fast must be False: it sets allow_errors=False, which makes
                # nbclient raise CellExecutionError from the parent preprocess_cell
                # before the debug-capture block below it ever runs. With fail_fast
                # off, the error lands in the cell outputs and gets reported.
                _, errors, _ = run_notebook(
                    str(notebook_path), timeout=30, fail_fast=False
                )

                # Check that we got an error
                assert len(errors) > 0

                # Check that debug output was captured
                stderr_output = captured_stderr.getvalue()
                # Note: Variable inspection might fail if kernel manager doesn't support it,
                # but we should at least see the attempt
                assert (
                    "DEBUG MODE" in stderr_output
                    or "Variable States" in stderr_output
                    or "Could not inspect variables" in stderr_output
                )
            finally:
                sys.stderr = old_stderr

    def test_debug_mode_not_called_when_disabled(self, tmp_path, monkeypatch):
        """Test that variable inspection is not called when debug mode is disabled."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell("raise ValueError('Test error')"),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        # Mock inspect_notebook_variables to verify it's not called
        with patch("tests.notebooks.runner.inspect_notebook_variables") as mock_inspect:
            # Ensure debug mode is disabled
            monkeypatch.delenv("NOTEBOOK_DEBUG_MODE", raising=False)

            # Run notebook (fail_fast=False so the error is collected rather than
            # raised out of nbclient before the debug branch is reached)
            run_notebook(str(notebook_path), timeout=30, fail_fast=False)

            # Verify inspect_notebook_variables was not called
            mock_inspect.assert_not_called()

    def test_debug_mode_called_when_enabled(self, tmp_path, monkeypatch):
        """Test that variable inspection is called when debug mode is enabled."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell("raise ValueError('Test error')"),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        # Mock inspect_notebook_variables to verify it's called
        with patch("tests.notebooks.runner.inspect_notebook_variables") as mock_inspect:
            mock_inspect.return_value = {"test_var": {"exists": False}}

            # Enable debug mode
            monkeypatch.setenv("NOTEBOOK_DEBUG_MODE", "true")

            # Run notebook (fail_fast=False so the error is collected rather than
            # raised out of nbclient before the debug branch is reached)
            run_notebook(str(notebook_path), timeout=30, fail_fast=False)

            # Verify inspect_notebook_variables was called
            # Note: It might be called multiple times if there are multiple errors
            assert mock_inspect.called


class TestPatchedExecutePreprocessor:
    """Tests for PatchedExecutePreprocessor class."""

    def test_preprocessor_initialization(self):
        """Test that preprocessor initializes correctly."""
        preprocessor = PatchedExecutePreprocessor()
        assert preprocessor.cell_count == 0
        assert preprocessor.total_cells == 0
        assert preprocessor.fail_fast is False
        assert preprocessor.debug_mode is False
        assert preprocessor.kernel_manager is None

    def test_preprocessor_stores_kernel_manager(self):
        """Test that preprocessor stores kernel manager reference."""
        preprocessor = PatchedExecutePreprocessor(debug_mode=True)
        mock_km = MagicMock()
        mock_nb = nbformat.v4.new_notebook()
        mock_nb.cells = [nbformat.v4.new_code_cell("print('test')")]

        # See test_kernel_manager_stored_when_debug_mode_enabled: the parent
        # implementation is stubbed so this stays a unit test and cannot hang.
        with patch.object(
            ExecutePreprocessor, "preprocess", return_value=(mock_nb, {})
        ):
            preprocessor.preprocess(mock_nb, resources={}, km=mock_km)

        assert preprocessor.kernel_manager is mock_km


class TestDependencyValidatorWiring:
    """Tests that the dependency validator is wired up with a usable notebook path.

    Regression coverage for the false positive where every OpenSearch notebook
    failed with "requires index 'tmdb' but it has not been created yet" even
    though the index had been created and populated. run_notebook() passes the
    notebook path as a top-level "notebook_path" resources key, but preprocess()
    read it from resources["metadata"] first using if/elif. Since "metadata" is
    always present, the top-level branch was unreachable and the path stayed
    None, so no client was built, no operation was ever recorded, and every
    dependent cell tripped the prerequisite check.
    """

    def _preprocess_with(self, resources):
        preprocessor = PatchedExecutePreprocessor(enable_dependency_validation=True)
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_code_cell("print('test')")]
        with patch.object(ExecutePreprocessor, "preprocess", return_value=(nb, {})):
            preprocessor.preprocess(nb, resources=resources)
        return preprocessor

    def test_notebook_path_read_from_top_level_key(self):
        """The path run_notebook() actually passes must reach the validator."""
        path = "./notebooks/opensearch/tmdb/term-stat-query.ipynb"
        preprocessor = self._preprocess_with(
            {"metadata": {"path": "./notebooks/opensearch/tmdb"}, "notebook_path": path}
        )
        assert preprocessor.dependency_validator.notebook_path == path

    def test_notebook_path_read_from_metadata(self):
        """The metadata form keeps working for callers that use it."""
        path = "./notebooks/solr/tmdb/svmrank.ipynb"
        preprocessor = self._preprocess_with({"metadata": {"notebook_path": path}})
        assert preprocessor.dependency_validator.notebook_path == path

    def test_missing_path_is_tolerated(self):
        """No path anywhere should not raise; validation just degrades."""
        preprocessor = self._preprocess_with({"metadata": {"path": "."}})
        assert preprocessor.dependency_validator.notebook_path is None


class TestDependencyValidatorWithoutClient:
    """Tests the no-client path records operations instead of silently dropping them.

    Passing an operation while failing everything that depends on it is never
    the useful combination, so when the operation cannot be confirmed against a
    live engine we trust the cell source and record it anyway.
    """

    def _validator(self):
        from tests.notebooks.runner import NotebookDependencyValidator

        validator = NotebookDependencyValidator(notebook_path=None)
        assert validator.client_instance is None
        return validator

    def test_rebuild_recorded_without_client(self):
        validator = self._validator()
        assert validator.validate_operation_succeeded("rebuild", "tmdb", 0) == (
            True,
            None,
        )
        met, err = validator.check_prerequisites(
            [{"dependency": "index", "target": "tmdb"}], 1
        )
        assert met, err

    def test_create_index_recorded_without_client(self):
        validator = self._validator()
        validator.validate_operation_succeeded("create_index", "blog", 0)
        assert "blog" in validator.completed_operations["indices"]

    def test_featureset_records_its_index_too(self):
        """A feature set implies its index exists."""
        validator = self._validator()
        validator.validate_operation_succeeded("create_featureset", "tmdb:tsq", 0)
        assert "tmdb:tsq" in validator.completed_operations["feature_sets"]
        assert "tmdb" in validator.completed_operations["indices"]

    def test_unmet_dependency_still_reported(self):
        """The check must still catch a genuinely missing index."""
        validator = self._validator()
        met, err = validator.check_prerequisites(
            [{"dependency": "index", "target": "never_created"}], 1
        )
        assert not met
        assert err is not None
        assert "never_created" in err


class TestSafeKcvFolds:
    """Tests the cross-validation fold clamp.

    Regression coverage for the hang in "netfix movies-random-forests" and the
    other kcv-using notebooks. The harness shrinks the training set to
    NOTEBOOK_MAX_QUERIES queries and used to force kcv to 1, which RankLib
    cannot train on: the empty fold throws ArrayIndexOutOfBoundsException inside
    a thread-pool worker that is never shut down, so the JVM hangs instead of
    exiting and the notebook burns the entire RankLib timeout with no useful
    error. Confirmed against RankLib directly -- -kcv 1 hangs, -kcv 2 finishes
    in about a second.
    """

    def test_one_fold_is_raised_to_two(self):
        """A fold count of 1 is always invalid, whatever was requested."""
        assert safe_kcv_folds(1, 2) == 2

    def test_folds_capped_at_query_count(self):
        """More folds than queries leaves empty folds, which is what hangs."""
        assert safe_kcv_folds(5, 2) == 2

    def test_folds_preserved_when_training_set_is_big_enough(self):
        assert safe_kcv_folds(5, 10) == 5

    def test_too_few_queries_disables_cross_validation(self):
        """Below 2 queries no valid split exists, so kcv must be dropped."""
        assert safe_kcv_folds(2, 1) is None
        assert safe_kcv_folds(2, 0) is None

    def test_result_is_never_the_value_that_hangs(self):
        """Whatever the inputs, never emit a fold count RankLib chokes on."""
        for requested in range(0, 12):
            for queries in range(0, 12):
                folds = safe_kcv_folds(requested, queries)
                if folds is None:
                    continue
                assert folds >= 2, (requested, queries, folds)
                assert folds <= queries, (requested, queries, folds)


class _FakeJudgment:
    """Minimal stand-in for ltr.judgments.Judgment - only .grade is read."""

    def __init__(self, grade, doc_id):
        self.grade = grade
        self.doc_id = doc_id

    def __repr__(self):
        return f"J(grade={self.grade}, doc={self.doc_id})"


def _judgments(grades):
    """Build judgments with the given grades, in file order."""
    return [_FakeJudgment(grade, f"doc{i}") for i, grade in enumerate(grades)]


class TestDiverseJudgmentSample:
    """Tests the grade-aware judgment trim.

    Regression coverage for the empty training sets in svmrank and
    ai-powered-search-ch-10. The harness trimmed each query to its first N
    judgments, which is grade-blind. Judgment files are written
    most-relevant-first, so the head of a query is often all one grade, and a
    pairwise learner given one grade produces zero training pairs - an empty
    training set rather than a small one. In title_judgments_binary.txt, which
    both notebooks use, 37 of 65 queries had this problem, including the two
    the harness actually keeps.
    """

    def test_picks_two_grades_from_relevant_first_file(self):
        """The reported case: leading judgments all share a grade."""
        judgments = _judgments([1, 1, 1, 0, 0, 0])

        sample = diverse_judgment_sample(judgments, 2)

        assert len(sample) == 2
        assert {j.grade for j in sample} == {1, 0}, (
            "A pairwise learner needs two grades to form a single pair"
        )

    def test_old_positional_behaviour_would_have_failed(self):
        """Pin the contrast: the previous slice yields one grade on this input."""
        judgments = _judgments([1, 1, 1, 0, 0, 0])

        assert {j.grade for j in judgments[:2]} == {1}
        assert len({j.grade for j in diverse_judgment_sample(judgments, 2)}) == 2

    def test_preserves_file_order(self):
        """Selection reorders nothing; RankLib and the notebooks read in order."""
        judgments = _judgments([1, 1, 1, 0, 0, 0])

        sample = diverse_judgment_sample(judgments, 3)

        assert [j.doc_id for j in sample] == sorted(j.doc_id for j in sample), (
            "Sample must stay in the order the judgments appeared in the file"
        )

    def test_spreads_across_more_than_two_grades(self):
        """A graded file should contribute as many grades as the budget allows."""
        judgments = _judgments([4, 4, 3, 3, 2, 2, 1, 1, 0, 0])

        sample = diverse_judgment_sample(judgments, 4)

        assert len(sample) == 4
        assert len({j.grade for j in sample}) == 4

    def test_already_diverse_head_is_unchanged(self):
        """Where positional trimming already worked, keep the same judgments."""
        judgments = _judgments([4, 3, 2, 1])

        sample = diverse_judgment_sample(judgments, 2)

        assert [j.doc_id for j in sample] == ["doc0", "doc1"]

    def test_single_grade_query_returns_requested_count(self):
        """A query with one grade cannot be saved; it must still be trimmed."""
        judgments = _judgments([1, 1, 1, 1])

        sample = diverse_judgment_sample(judgments, 2)

        assert len(sample) == 2
        assert {j.grade for j in sample} == {1}

    def test_short_query_returned_untouched(self):
        """Nothing to trim: return the same list, not a copy or a reordering."""
        judgments = _judgments([1, 0])

        assert diverse_judgment_sample(judgments, 2) is judgments
        assert diverse_judgment_sample(judgments, 5) is judgments

    def test_empty_query(self):
        """Degenerate input must not raise."""
        assert diverse_judgment_sample([], 2) == []

    def test_max_count_zero(self):
        """A zero budget yields nothing rather than looping."""
        assert diverse_judgment_sample(_judgments([1, 0, 1]), 0) == []

    def test_never_exceeds_budget_or_invents_judgments(self):
        """Across many shapes, the sample stays a valid subset of the input."""
        shapes = [
            [1, 1, 1, 0],
            [0, 0, 0, 0, 1],
            [4, 3, 2, 1, 0],
            [2, 2, 2, 2, 2, 2],
            [1, 0, 1, 0, 1, 0],
        ]
        for grades in shapes:
            judgments = _judgments(grades)
            for budget in range(1, len(grades) + 2):
                sample = diverse_judgment_sample(judgments, budget)
                assert len(sample) <= max(budget, 0), (grades, budget)
                assert len(sample) == len({id(j) for j in sample}), (
                    f"Duplicate judgment in sample for {grades} at budget {budget}"
                )
                assert all(j in judgments for j in sample), (grades, budget)

    def test_prefers_grade_spread_over_grade_frequency(self):
        """A grade with one judgment must not be crowded out by a common one."""
        judgments = _judgments([1, 1, 1, 1, 1, 1, 1, 0])

        sample = diverse_judgment_sample(judgments, 2)

        assert {j.grade for j in sample} == {1, 0}


class TestHardcodedQidPatch:
    """Tests the rewrite of hardcoded query-ID guards.

    Regression coverage for "netfix movies(Solr)". Notebooks single out a query
    to inspect with `if qid == 40:` inside a groupby over the training set, but
    the harness keeps only the first NOTEBOOK_MAX_QUERIES queries. A qid outside
    that window is never reached, the guarded body never runs, and the variable
    it defines fails several cells later with a NameError naming the variable
    rather than the cause.
    """

    def _patch(self, source):
        """Run a single code cell through the notebook patcher."""
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source=source)])
        _patch_notebook_cells_for_testing(nb)
        return nb.cells[0]["source"]

    def test_rewrites_out_of_range_qid(self):
        """The reported case: qid 40 with a 2-query budget."""
        source = (
            "for qid, g in groupby(training_set, key=lambda j: j.qid):\n"
            "    if qid == 40:  # Star Wars\n"
            "        model = eval_model(g)\n"
            "        break\n"
        )

        patched = self._patch(source)

        assert "if True:" in patched
        assert "qid == 40" not in patched.replace("was 'qid == 40'", "")
        assert "model = eval_model(g)" in patched, "The body must be preserved"

    def test_records_the_original_qid(self):
        """The rewrite must stay legible in a saved notebook."""
        patched = self._patch("    if qid == 40:  # Star Wars\n        pass\n")

        assert "[TEST MODE]" in patched
        assert "was 'qid == 40'" in patched

    def test_preserves_indentation(self):
        """A wrong indent would be a SyntaxError, not a test failure."""
        patched = self._patch("        if qid == 7:\n            pass\n")

        assert patched.startswith("        if True:")

    def test_preserves_trailing_comment(self):
        """The notebook's own annotation is worth keeping."""
        patched = self._patch("    if qid == 40:  # Star Wars\n        pass\n")

        assert "# Star Wars" in patched

    def test_leaves_inline_body_alone(self):
        """`if qid == 40: work()` would have its body commented out."""
        source = "if qid == 40: model = f()\n"

        assert self._patch(source) == source

    def test_leaves_non_literal_comparison_alone(self):
        """Only literal qids are known to be outside the budget."""
        source = "if qid == target_qid:\n    pass\n"

        assert self._patch(source) == source

    def test_leaves_unrelated_conditions_alone(self):
        """The patch must not touch conditions that merely mention a qid."""
        source = "if qid > 40:\n    pass\n"

        assert self._patch(source) == source

    def test_patched_source_stays_valid_python(self):
        """Compile the result rather than trusting the string."""
        source = (
            "for qid, g in groupby(training_set, key=lambda j: j.qid):\n"
            "    if qid == 40:  # Star Wars\n"
            "        model = eval_model(g)\n"
            "        break\n"
        )

        compile(self._patch(source), "<patched>", "exec")

    def test_in_range_qid_still_matches_first_group(self):
        """qid 1 already worked; rewriting it must not change what runs.

        The Elasticsearch and OpenSearch netfix notebooks use qid 1, which is
        the first group either way, so the rewrite is a no-op in effect.
        """
        source = (
            "for qid, g in groupby(training_set, key=lambda j: j.qid):\n"
            "    if qid == 1:  # Rambo\n"
            "        model = eval_model(g)\n"
            "        break\n"
        )
        namespace = {
            "training_set": None,
            "groupby": lambda seq, key: [(1, "first"), (2, "second")],
            "eval_model": lambda g: f"model-for-{g}",
        }

        exec(compile(self._patch(source), "<patched>", "exec"), namespace)

        assert namespace["model"] == "model-for-first"
