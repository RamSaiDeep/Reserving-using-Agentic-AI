import os
import pytest
import pandas as pd
from reserving.core.triangle import Triangle

@pytest.fixture(scope="session")
def test_data_dir():
    """Returns the absolute path to the tests/data directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))

@pytest.fixture(scope="session")
def sample_csv_text(test_data_dir):
    """Loads the content of df_masked.csv."""
    csv_path = os.path.join(test_data_dir, "df_masked.csv")
    with open(csv_path, "r") as f:
        return f.read()

@pytest.fixture(scope="session")
def sample_df(test_data_dir):
    """Loads the df_masked.csv into a pandas DataFrame."""
    csv_path = os.path.join(test_data_dir, "df_masked.csv")
    return pd.read_csv(csv_path)

@pytest.fixture(scope="session")
def sample_triangle(sample_csv_text):
    """Loads the Triangle object from the sample CSV text."""
    return Triangle.from_csv(sample_csv_text)
