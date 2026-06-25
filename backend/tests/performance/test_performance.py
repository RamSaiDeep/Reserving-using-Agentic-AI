import sys
import os
import time
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow

@pytest.mark.performance
def test_pipeline_execution_timing(sample_csv_text):
    t0 = time.time()
    session_id = agent_workflow.create_session(
        csv_text=sample_csv_text,
        n_years=5,
        business_context='{"tail": "Not Known", "volatility": "Not Known", "environment": "Not Known", "distortions": "Not Known"}'
    )
    t_session = time.time() - t0
    
    t0 = time.time()
    agent_workflow.ingest_csv(session_id)
    t_ingest = time.time() - t0
    
    t0 = time.time()
    agent_workflow.perform_data_quality_checks(session_id)
    t_dq = time.time() - t0
    
    t0 = time.time()
    agent_workflow.build_loss_triangle(session_id)
    t_triangle = time.time() - t0
    
    t0 = time.time()
    agent_workflow.calculate_ldfs(session_id)
    t_ldfs = time.time() - t0
    
    t0 = time.time()
    list(agent_workflow.execute_sequential_pipeline_part2(session_id))
    t_part2 = time.time() - t0
    
    print(f"\n--- Pipeline Performance Metrics ---")
    print(f"Session Creation: {t_session:.4f}s")
    print(f"ingest_csv: {t_ingest:.4f}s")
    print(f"perform_data_quality_checks: {t_dq:.4f}s")
    print(f"build_loss_triangle: {t_triangle:.4f}s")
    print(f"calculate_ldfs: {t_ldfs:.4f}s")
    print(f"execute_sequential_pipeline_part2: {t_part2:.4f}s")
    
    # Assert sanity check limits (e.g. whole pipeline execution under 15 seconds)
    total_time = t_session + t_ingest + t_dq + t_triangle + t_ldfs + t_part2
    assert total_time < 15.0, f"Total execution time was too slow: {total_time:.2f}s"
