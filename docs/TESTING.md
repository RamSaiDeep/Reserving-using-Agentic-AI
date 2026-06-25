# Testing Guide

This document describes the test suite structure, execution methods, and guidelines for the Reserving Engine backend.

---

## 1. Test Suite Architecture

The test suite is organized into distinct categories under `backend/tests/` to facilitate separation of concerns, targeted verification runs, and easier maintenance:

```text
backend/tests/
├── conftest.py             # Shared pytest fixtures (datasets, triangles)
├── data/                   # Shared test datasets
│   └── df_masked.csv       # Standard insurance claims dataset
├── unit/                   # Unit tests (math engines, standalone components)
│   ├── test_development_engine.py
│   ├── test_diagnostics.py
│   ├── test_methods.py
│   └── test_triangle.py
├── integration/            # Integration tests (agent orchestration, APIs)
│   ├── test_integration_step1.py
│   └── test_multi_agent.py
├── regression/             # Regression tests (remediation identities, clamping controls)
│   ├── test_capabilities.py
│   ├── test_negative_ibnr_validation.py
│   └── test_remediation.py
└── performance/            # Performance and benchmark tests
    ├── test_benchmark_dev_engine.py
    └── test_performance.py
```

---

## 2. Test Categories & Purposes

### Unit Tests (`pytest -m unit`)
* **Purpose**: Test the logic of individual components, functions, and mathematical formulas in isolation.
* **Scope**: Reserving methods classes (`reserving.methods`), the development engine (`reserving.core.development_engine`), diagnostics modules, and the `Triangle` parsing logic.

### Integration Tests (`pytest -m integration`)
* **Purpose**: Test interaction between multiple components or workflows, including multi-agent systems.
* **Scope**: Columns classification & inspection step, agent orchestration (Diagnostics, Comparison, Recommender, Reporter) using mocked external services to guarantee reliability and speed.

### Regression Tests (`pytest -m regression`)
* **Purpose**: Enforce actuarial identities, output contracts, and negative IBNR clamping behavior.
* **Scope**: Output validation (reported = paid + case, reserve = ultimate - paid, etc.), mature years CDF threshold calibration, and negative IBNR clamping control.

### Performance Tests (`pytest -m performance`)
* **Purpose**: Profile and benchmark execution times of core engines and pipelines.
* **Scope**: timing checks on sequential execution steps and benchmarking custom ATA/CDF calculations against notebook looping equivalents.

---

## 3. Running the Tests

To run the tests, navigate to the project root and use `pytest`.

### Run all tests
```powershell
python -m pytest -v
```

### Run a specific category (using markers)
* **Unit tests only**:
  ```powershell
  python -m pytest -m unit -v
  ```
* **Integration tests only**:
  ```powershell
  python -m pytest -m integration -v
  ```
* **Regression tests only**:
  ```powershell
  python -m pytest -m regression -v
  ```
* **Performance tests only**:
  ```powershell
  python -m pytest -m performance -s -v
  ```
  *(Note: `-s` is recommended for performance tests to output benchmark printouts to the console).*

### Run a specific file or directory
```powershell
python -m pytest backend/tests/unit/test_triangle.py -v
```

---

## 4. Writing New Tests

* **Shared Fixtures**: Always check [conftest.py](file:///c:/Reserving-using-Agentic-AI/backend/tests/conftest.py) before writing test-specific data loaders. Re-use `sample_triangle`, `sample_csv_text`, or `sample_df`.
* **Category Markers**: Ensure you add the appropriate marker to any new test function (e.g., `@pytest.mark.unit` or `@pytest.mark.regression`).
* **Deterministic mock checks**: Mock network or slow LLM requests using simple lambda functions or unit test mocks to keep tests fast and deterministic.

---

## 5. Expected CI Workflow

In the CI/CD pipeline:
1. Standard tests (`unit`, `integration`, and `regression`) must run and pass on every pull request.
2. `performance` tests should run on master merges or as nightly cron builds, logging execution duration trends over time.
3. Warnings must not block builds unless they are errors, but standard deprecation warnings should be monitored and cleaned periodically.
