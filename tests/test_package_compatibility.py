#!/usr/bin/env python3
"""
Test script to verify package compatibility after Python 3.12 updates.

This script tests:
1. Basic imports of updated packages
2. Critical functionality used in notebooks:
   - scipy (Bayesian optimization)
   - scikit-learn (Lambda-MART)
   - pandas (DataFrames)
   - numpy (array operations)
   - matplotlib (plotting)

Can be run as:
- Standalone script: python tests/test_package_compatibility.py
- pytest: pytest tests/test_package_compatibility.py --cov=ltr --cov-report=term-missing
"""

import sys
import traceback

import pytest


def test_imports():
    """Test basic imports of updated packages."""
    print("Testing package imports...")
    errors = []

    try:
        import numpy as np  # noqa: F401
        print(f"  ✓ numpy {np.__version__}")
    except Exception as e:
        errors.append(f"numpy import failed: {e}")
        print("  ✗ numpy import failed")
        raise

    try:
        import scipy  # noqa: F401
        print(f"  ✓ scipy {scipy.__version__}")
    except Exception as e:
        errors.append(f"scipy import failed: {e}")
        print("  ✗ scipy import failed")
        raise

    try:
        import sklearn  # noqa: F401
        print(f"  ✓ scikit-learn {sklearn.__version__}")
    except Exception as e:
        errors.append(f"scikit-learn import failed: {e}")
        print("  ✗ scikit-learn import failed")
        raise

    try:
        import pandas as pd  # noqa: F401
        print(f"  ✓ pandas {pd.__version__}")
    except Exception as e:
        errors.append(f"pandas import failed: {e}")
        print("  ✗ pandas import failed")
        raise

    try:
        import matplotlib  # noqa: F401
        print(f"  ✓ matplotlib {matplotlib.__version__}")
    except Exception as e:
        errors.append(f"matplotlib import failed: {e}")
        print("  ✗ matplotlib import failed")
        raise

    if errors:
        pytest.fail(f"Import errors: {errors}")

def test_numpy_operations():
    """Test numpy operations used in codebase."""
    print("\nTesting numpy operations...")
    errors = []

    try:
        import numpy as np

        # Test basic array creation (used in judgments_to_nparray)
        features = np.array([[1, 2, 3], [4, 5, 6]])
        predictors = np.array([[1, 1], [2, 1]])

        # Test array indexing (used throughout notebooks)
        assert features.shape == (2, 3)
        assert predictors.shape == (2, 2)

        # Test array operations (used in pairwise_transform)
        diff = features[0, :] - features[1, :]
        assert diff.shape == (3,)

        print("  ✓ numpy array operations")
    except Exception as e:
        errors.append(f"numpy operations failed: {e}")
        print(f"  ✗ numpy operations failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Numpy operation errors: {errors}")

def test_scipy_operations():
    """Test scipy operations used in Bayesian optimization notebooks."""
    print("\nTesting scipy operations...")
    errors = []

    try:
        from scipy.stats import norm

        # Test norm distribution (used in bayesian-optimization notebooks)
        mu, sigma = 0, 1
        x = norm.ppf(0.95, mu, sigma)  # Percent point function
        pdf_val = norm.pdf(0, mu, sigma)  # Probability density function

        assert isinstance(x, float)
        assert isinstance(pdf_val, float)
        assert pdf_val > 0

        print("  ✓ scipy.stats.norm operations")
    except Exception as e:
        errors.append(f"scipy operations failed: {e}")
        print(f"  ✗ scipy operations failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Scipy operation errors: {errors}")

def test_sklearn_operations():
    """Test scikit-learn operations used in Lambda-MART notebooks."""
    print("\nTesting scikit-learn operations...")
    errors = []

    try:
        import numpy as np
        from sklearn import svm
        from sklearn.preprocessing import StandardScaler
        from sklearn.tree import DecisionTreeRegressor

        # Test StandardScaler (used in svmrank notebooks)
        x_data = np.array([[1, 2], [3, 4], [5, 6]])
        scaler = StandardScaler()
        scaler.fit(x_data)
        x_scaled = scaler.transform(x_data)

        assert x_scaled.shape == x_data.shape

        # Test DecisionTreeRegressor (used in lambda-mart notebooks)
        y = np.array([1, 2, 3])
        tree = DecisionTreeRegressor(max_leaf_nodes=8)
        tree.fit(x_data, y)
        predictions = tree.predict(x_data)

        assert len(predictions) == len(y)

        # Test LinearSVC (used in svmrank notebooks)
        y_binary = np.array([0, 1, 0])
        model = svm.LinearSVC(max_iter=1000)
        model.fit(x_data, y_binary)

        assert hasattr(model, 'coef_')

        print("  ✓ scikit-learn operations")
    except Exception as e:
        errors.append(f"scikit-learn operations failed: {e}")
        print(f"  ✗ scikit-learn operations failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Scikit-learn operation errors: {errors}")

def test_pandas_operations():
    """Test pandas DataFrame operations used in notebooks."""
    print("\nTesting pandas operations...")
    errors = []

    try:
        import pandas as pd

        # Test DataFrame creation (used in judgments_to_dataframe)
        data = {
            'uid': ['1_a', '2_b', '3_c'],
            'qid': [1, 1, 2],
            'grade': [1, 2, 1],
            'features': [[1, 2], [3, 4], [5, 6]]
        }
        df = pd.DataFrame(data)

        assert len(df) == 3
        assert 'qid' in df.columns

        # Test DataFrame operations (used in lambda-mart notebooks)
        df['last_prediction'] = 0.0
        grouped = df.groupby('qid')['grade'].sum()

        assert len(grouped) == 2

        # Test DataFrame copy (used in lambda-mart notebooks)
        df_copy = df.copy()
        assert len(df_copy) == len(df)

        # Test DataFrame operations with lists (used in lambda-mart notebooks)
        features_list = df['features'].tolist()
        assert len(features_list) == 3

        print("  ✓ pandas DataFrame operations")
    except Exception as e:
        errors.append(f"pandas operations failed: {e}")
        print(f"  ✗ pandas operations failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Pandas operation errors: {errors}")

def test_matplotlib_operations():
    """Test matplotlib operations used in notebooks."""
    print("\nTesting matplotlib operations...")
    errors = []

    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np

        # Test basic plotting (used in notebooks)
        x = np.linspace(0, 10, 100)
        y = np.sin(x)

        fig, ax = plt.subplots()
        ax.plot(x, y)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')

        # Close figure to avoid warnings
        plt.close(fig)

        print("  ✓ matplotlib plotting operations")
    except Exception as e:
        errors.append(f"matplotlib operations failed: {e}")
        print(f"  ✗ matplotlib operations failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Matplotlib operation errors: {errors}")

def test_integration():
    """Test integration of packages together (as used in notebooks)."""
    print("\nTesting package integration...")
    errors = []

    try:
        import numpy as np
        import pandas as pd
        from sklearn.preprocessing import StandardScaler

        # Simulate judgments_to_nparray workflow
        features_list = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        predictors_list = [[1, 1], [2, 1], [1, 2]]

        features = np.array(features_list)
        predictors = np.array(predictors_list)

        # Apply StandardScaler (as in svmrank notebooks)
        scaler = StandardScaler()
        scaler.fit(features)
        features_scaled = scaler.transform(features)

        # Convert to DataFrame (as in lambda-mart notebooks)
        df = pd.DataFrame({
            'qid': predictors[:, 1],
            'grade': predictors[:, 0],
            'features': features_list
        })

        assert len(df) == 3
        assert features_scaled.shape == features.shape

        print("  ✓ Package integration test")
    except Exception as e:
        errors.append(f"Integration test failed: {e}")
        print(f"  ✗ Integration test failed: {e}")
        traceback.print_exc()
        raise

    if errors:
        pytest.fail(f"Integration test errors: {errors}")

def main():
    """Run all compatibility tests (standalone mode)."""
    print("=" * 60)
    print("Package Compatibility Test Suite")
    print("Testing Python 3.12 compatibility after package updates")
    print("=" * 60)
    print("\nNote: For coverage reporting, run with pytest:")
    print("  pytest tests/test_package_compatibility.py --cov=ltr --cov-report=term-missing")
    print("=" * 60 + "\n")

    # Run pytest programmatically
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])
    return exit_code

if __name__ == '__main__':
    sys.exit(main())

