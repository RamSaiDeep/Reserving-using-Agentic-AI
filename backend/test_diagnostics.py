import pytest
import numpy as np
from reserving.core.triangle import Triangle
from reserving.diagnostics import (
    reporting_pattern,
    ldf_stability,
    calendar_effects,
    tail_analysis,
    outliers,
    suitability,
    trace_generator,
    compute_diagnostics
)

@pytest.fixture
def sample_triangle():
    # Load realistic test data
    with open("../data/df_masked.csv", "r") as f:
        csv_text = f.read()
    t = Triangle.from_csv(csv_text)
    return t

def test_reporting_pattern(sample_triangle):
    res = reporting_pattern.analyze(sample_triangle)
    assert "best_fit_curve" in res
    assert "fit_metrics" in res
    assert "reporting_consistency" in res
    assert "accident_year_fits" in res
    assert "significant_deviations" in res
    assert res["best_fit_curve"] in ["loglogistic", "weibull", "exponential", "None"]

def test_ldf_stability(sample_triangle):
    res = ldf_stability.analyze(sample_triangle)
    assert "cov_by_age" in res
    assert "average_cov" in res
    assert "unstable_periods" in res
    assert "cl_suitable_indicator" in res
    assert "cl_assumptions_reasonable" in res
    assert isinstance(res["average_cov"], float)

def test_calendar_effects(sample_triangle):
    res = calendar_effects.analyze(sample_triangle)
    assert "calendar_years" in res
    assert "slope" in res
    assert "r_squared" in res
    assert "trend_detected" in res
    assert "anomalies" in res
    assert isinstance(res["slope"], float)
    assert isinstance(res["trend_detected"], bool)

def test_tail_analysis(sample_triangle):
    res = tail_analysis.analyze(sample_triangle)
    assert "selected_tail" in res
    assert "high_tail" in res
    assert "scenarios" in res
    assert "sensitivity" in res
    assert "tail_uncertainty_materiality" in res
    assert res["tail_uncertainty_materiality"] in ["High", "Moderate", "Low"]

def test_outliers(sample_triangle):
    res = outliers.analyze(sample_triangle)
    assert "cell_outliers" in res
    assert "accident_year_ranking" in res
    assert isinstance(res["cell_outliers"], list)
    assert isinstance(res["accident_year_ranking"], list)

def test_suitability(sample_triangle):
    diag_results = {
        "reporting_pattern": reporting_pattern.analyze(sample_triangle),
        "ldf_stability": ldf_stability.analyze(sample_triangle),
        "calendar_effects": calendar_effects.analyze(sample_triangle),
        "tail_analysis": tail_analysis.analyze(sample_triangle),
        "outliers": outliers.analyze(sample_triangle)
    }
    res = suitability.analyze(sample_triangle, diag_results)
    assert "scores" in res
    assert "pros" in res
    assert "cons" in res
    
    scores = res["scores"]
    for method in ["CL", "MCL", "BF", "CC", "BK", "CO", "CLK", "ELR"]:
        assert method in scores
        assert 0 <= scores[method] <= 100

def test_trace_generator():
    diag_results = {
        "ldf_stability": {"average_cov": 0.15, "cl_suitable_indicator": "Unstable"},
        "calendar_effects": {"trend_detected": True},
        "tail_analysis": {"tail_uncertainty_materiality": "High"},
        "outliers": {"cell_outliers": [{"severity": "Critical"}, {"severity": "High"}]},
        "reporting_pattern": {"significant_deviations": [2005]},
        "suitability": {"scores": {"CL": 45}}
    }
    trace = trace_generator.generate_decision_trace(diag_results, "MCL")
    assert "LDF CoV exceeded stability threshold" in trace
    assert "Calendar year trend detected" in trace
    assert "High tail factor sensitivity detected" in trace
    assert "Chain Ladder suitability reduced" in trace
    assert "Mack selected because it quantifies reserve uncertainty" in trace

def test_orchestrator(sample_triangle):
    res = compute_diagnostics(sample_triangle)
    # Original keys for backward compatibility
    assert 'overall' in res
    assert 'loss_ratios_by_ay' in res
    assert 'suggested_elr' in res
    assert 'ldf_diagnostics' in res
    assert 'ay_summary' in res
    assert 'volume_trends' in res
    
    # New keys
    assert 'reporting_pattern' in res
    assert 'ldf_stability' in res
    assert 'calendar_effects' in res
    assert 'tail_analysis' in res
    assert 'outliers' in res
    assert 'suitability' in res
