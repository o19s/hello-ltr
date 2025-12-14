#!/usr/bin/env python3
"""
Test notebook-specific code patterns to ensure compatibility.

This tests the exact patterns used in:
- Bayesian optimization notebooks (scipy usage)
- Lambda-MART notebooks (scikit-learn + pandas)
- DataFrame notebooks (pandas operations)
"""

import sys
import traceback


def run_pattern_test(test_name, test_func, success_msg=None):
    """
    Run a pattern test with standardized error handling.

    This helper function eliminates duplication in pattern test functions by
    providing consistent error handling, logging, and error collection.

    Args:
        test_name: Display name for the test (e.g., "Bayesian optimization patterns")
        test_func: Function to execute that contains the actual test logic
        success_msg: Optional specific success message. If None, uses test_name.

    Returns:
        list: List of error messages (empty if test passed)
    """
    print(f"\nTesting {test_name}...")
    errors = []
    try:
        test_func()
        display_msg = success_msg if success_msg else test_name
        print(f"  ✓ {display_msg}")
    except Exception as e:
        error_msg = f"{test_name} failed: {e}"
        errors.append(error_msg)
        print(f"  ✗ {error_msg}")
        traceback.print_exc()
    return errors


def test_bayesian_optimization_patterns():
    """Test patterns from bayesian-optimization notebooks."""

    def _test():
        """Test scipy.stats.norm operations used in Bayesian optimization."""
        import numpy as np
        from scipy.stats import norm

        # Pattern from bayesian-optimization.ipynb
        # Used for acquisition function calculations
        mu, sigma = 0, 1
        x = np.linspace(-3, 3, 100)
        pdf = norm.pdf(x, mu, sigma)
        cdf = norm.cdf(x, mu, sigma)
        ppf = norm.ppf(0.95, mu, sigma)

        assert len(pdf) == 100
        assert len(cdf) == 100
        assert isinstance(ppf, (float, np.floating))

    return run_pattern_test(
        "Bayesian optimization patterns",
        _test,
        success_msg="scipy.stats.norm operations (PDF, CDF, PPF)",
    )


def test_lambda_mart_patterns():
    """Test patterns from lambda-mart-in-python notebooks."""

    def _test():
        """Test Lambda-MART DataFrame and DecisionTree patterns."""
        import pandas as pd
        from sklearn.tree import DecisionTreeRegressor

        # Pattern from lambda-mart-in-python.ipynb
        # Create DataFrame similar to judgments DataFrame
        judgments = pd.DataFrame(
            {
                "qid": [1, 1, 1, 2, 2],
                "grade": [3, 2, 1, 2, 1],
                "features": [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
            }
        )

        # Pattern: Copy DataFrame and add prediction column
        lambdas_per_query = judgments.copy()
        lambdas_per_query["last_prediction"] = 0.0
        lambdas_per_query["lambda"] = [0.5, 0.3, 0.1, 0.4, 0.2]

        # Pattern: Extract features as list
        features = lambdas_per_query["features"].tolist()

        # Pattern: Train DecisionTreeRegressor
        tree = DecisionTreeRegressor(max_leaf_nodes=8)
        tree.fit(features, lambdas_per_query["lambda"])

        # Pattern: Group by and aggregate (used in tree_paths calculation)
        grouped_sum = lambdas_per_query.groupby("qid")["lambda"].sum()
        grouped_mean = lambdas_per_query.groupby("qid")["grade"].mean()

        assert len(features) == 5
        assert len(grouped_sum) == 2
        assert len(grouped_mean) == 2

    return run_pattern_test(
        "Lambda-MART patterns",
        _test,
        success_msg="Lambda-MART DataFrame and DecisionTree patterns",
    )


def test_svmrank_patterns():
    """Test patterns from svmrank notebooks."""

    def _test():
        """Test SVM-Rank StandardScaler and LinearSVC patterns."""
        import numpy as np
        from sklearn import svm
        from sklearn.preprocessing import StandardScaler

        # Pattern from svmrank.ipynb - judgments_to_nparray
        features_list = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        predictors_list = [[3, 1], [2, 1], [1, 1]]

        features = np.array(features_list)
        predictors = np.array(predictors_list)

        # Pattern: StandardScaler
        scaler = StandardScaler()
        scaler.fit(features)
        features_scaled = np.asarray(scaler.transform(features))

        # Pattern: Pairwise transform (simplified)
        GRADE = 0
        QID = 1
        transformed_features = []
        transformed_predictors = []

        for i in range(len(features)):
            for j in range(len(features)):
                if (
                    predictors[i][GRADE] != predictors[j][GRADE]
                    and predictors[i][QID] == predictors[j][QID]
                ):
                    transformed_predictors.append(
                        [predictors[i][GRADE] - predictors[j][GRADE]]
                    )
                    transformed_features.append(features[i, :] - features[j, :])

        transformed_features = np.array(transformed_features)
        transformed_predictors = np.array(transformed_predictors)

        # Pattern: LinearSVC
        if len(transformed_predictors) > 0:
            model = svm.LinearSVC(max_iter=1000)
            model.fit(transformed_features, transformed_predictors.ravel())
            assert hasattr(model, "coef_")

        assert features_scaled.shape == features.shape

    return run_pattern_test(
        "SVM-Rank patterns",
        _test,
        success_msg="SVM-Rank StandardScaler and LinearSVC patterns",
    )


def test_dataframe_patterns():
    """Test patterns from Dataframes notebooks."""

    def _test():
        """Test DataFrame creation and groupby patterns."""
        import pandas as pd

        # Pattern from Dataframes.ipynb - judgments_to_dataframe
        judgments_data = [
            {
                "uid": "1_a",
                "qid": 1,
                "keywords": "test",
                "docId": "a",
                "grade": 3,
                "features": [1, 2, 3],
            },
            {
                "uid": "1_b",
                "qid": 1,
                "keywords": "test",
                "docId": "b",
                "grade": 2,
                "features": [4, 5, 6],
            },
            {
                "uid": "2_a",
                "qid": 2,
                "keywords": "query",
                "docId": "a",
                "grade": 1,
                "features": [7, 8, 9],
            },
        ]

        df = pd.DataFrame(judgments_data)

        # Pattern: DataFrame operations
        assert "qid" in df.columns
        assert "grade" in df.columns
        assert "features" in df.columns

        # Pattern: Group by operations
        grade_counts = df.groupby("qid")["grade"].count()
        grade_sums = df.groupby("qid")["grade"].sum()

        assert len(grade_counts) == 2
        assert len(grade_sums) == 2

        # Pattern: DataFrame copy
        df_copy = df.copy()
        df_copy["new_col"] = 0

        assert len(df_copy) == len(df)
        assert "new_col" in df_copy.columns

    return run_pattern_test(
        "DataFrame patterns",
        _test,
        success_msg="DataFrame creation and groupby patterns",
    )


def test_judgments_module_patterns():
    """Test patterns from ltr/judgments.py module."""

    def _test():
        """Test judgments module patterns including numpy array conversion."""
        import numpy as np
        import pandas as pd

        # Simulate judgments_to_nparray pattern
        class MockJudgment:
            """Mock judgment object for testing notebook patterns.

            Simulates the structure of judgment objects used in notebooks
            for testing array and DataFrame conversion patterns.
            """

            def __init__(self, grade, qid, features):
                """Initialize mock judgment with grade, query ID, and features.

                Args:
                    grade: Relevance grade (int)
                    qid: Query ID (int)
                    features: Feature vector (list)
                """
                self.grade = grade
                self.qid = qid
                self.features = features

        judgments = [
            MockJudgment(3, 1, [1, 2, 3]),
            MockJudgment(2, 1, [4, 5, 6]),
            MockJudgment(1, 2, [7, 8, 9]),
        ]

        # Pattern from judgments_to_nparray
        predictors = []
        features = []
        for judg in judgments:
            predictors.append([judg.grade, judg.qid])
            features.append(judg.features)

        features = np.array(features)
        predictors = np.array(predictors)

        assert features.shape == (3, 3)
        assert predictors.shape == (3, 2)

        # Pattern from judgments_to_dataframe
        ret = []
        for j in judgments:
            ret.append(
                {
                    "uid": str(j.qid) + "_" + "doc",
                    "qid": j.qid,
                    "keywords": "test",
                    "docId": "doc",
                    "grade": j.grade,
                    "features": j.features,
                }
            )

        df = pd.DataFrame(ret)
        assert len(df) == 3
        assert "features" in df.columns

    return run_pattern_test(
        "judgments.py patterns",
        _test,
        success_msg="judgments.py array and DataFrame conversion patterns",
    )


def main():
    """Run all notebook pattern tests."""
    print("=" * 60)
    print("Notebook Pattern Compatibility Test Suite")
    print("Testing exact patterns from critical notebooks")
    print("=" * 60)

    all_errors = []

    # Run all pattern tests
    all_errors.extend(test_bayesian_optimization_patterns())
    all_errors.extend(test_lambda_mart_patterns())
    all_errors.extend(test_svmrank_patterns())
    all_errors.extend(test_dataframe_patterns())
    all_errors.extend(test_judgments_module_patterns())

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"❌ TESTS FAILED: {len(all_errors)} error(s) found")
        print("\nErrors:")
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. {error}")
        return 1
    else:
        print("✅ ALL PATTERN TESTS PASSED")
        print("\nAll notebook code patterns work correctly with updated packages.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
