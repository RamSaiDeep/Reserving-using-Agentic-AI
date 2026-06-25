import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow

@pytest.mark.integration
def test_columns_classification_and_inspection(sample_csv_text):
    session_id = agent_workflow.create_session(
        csv_text=sample_csv_text,
        n_years=5
    )
    
    result = agent_workflow.ingest_csv(session_id)
    assert result is not None
    
    session = agent_workflow.SESSION_STORE[session_id]
    classification = session.get('classification')
    inspection = session.get('inspection')
    
    assert classification is not None, "Missing classification results in session."
    assert inspection is not None, "Missing inspection results in session."
    
    assert classification.data_type in ["cumulative", "incremental", "long_triangle", "wide_triangle"]
    assert classification.confidence.upper() in ["HIGH", "MEDIUM", "LOW"]
    assert isinstance(classification.is_cas_format, bool)
    
    assert isinstance(inspection.entity_check.is_multi_entity, bool)
    if inspection.entity_check.is_multi_entity:
        assert inspection.entity_check.entity_column is not None
        assert inspection.entity_check.entity_count > 0
        
    for role, col in inspection.reserving_roles.items():
        if col:
            state = inspection.accumulation_states.get(col)
            assert state in ["incremental", "cumulative", "indeterminate", None]
