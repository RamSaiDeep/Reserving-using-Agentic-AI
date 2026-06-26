import pandas as pd
from io import StringIO
import json
import uuid
import time
import concurrent.futures
from openai import OpenAI
import openai
import os
from models.triangle import Triangle
from models.methods import METHODS
from models.classifier import DataClassifier
from models.inspector import DataInspector
from models.compliance import ComplianceEngine

# Global Session Store
SESSION_STORE = {}

def create_session(csv_text: str, n_years: int, valuation_year: int = None, api_key: str = None, base_url: str = None, model_name: str = None, business_context: str = None) -> str:
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        'csv_text': csv_text,
        'n_years': n_years,
        'valuation_year': valuation_year,
        'api_key': api_key,
        'base_url': base_url,
        'model_name': model_name,
        'business_context': business_context or '',
        'df': None,
        'triangle': None,
        'ldfs': None,
        'summary': None,
        'recommendation': None,
        'results': None,
        'compliance_engine': ComplianceEngine(),
        'methods_executed': set()
    }
    return session_id

# ==========================================
# TOOL FUNCTIONS
# ==========================================

def ingest_csv(session_id: str) -> str:
    """Tool for Agent 1: Converts the raw CSV data into a Pandas DataFrame, classifies it, and maps reserving roles."""
    session = SESSION_STORE.get(session_id)
    if not session: return "Error: Invalid session ID."
    
    try:
        csv_text = session['csv_text']
        df = pd.read_csv(StringIO(csv_text))
        session['df'] = df
        session['original_columns'] = list(df.columns)
        
        # 1. Run DataClassifier
        classifier = DataClassifier()
        classification = classifier.classify_from_bytes(csv_text.encode('utf-8'), "upload.csv")
        session['classification'] = classification
        
        # 2. Run DataInspector
        inspector = DataInspector(df=df, file_path="upload.csv", data_type=classification.data_type)
        inspection = inspector.inspect()
        session['inspection'] = inspection
        
        # Mapped roles from inspector
        roles = inspection.reserving_roles
        roles_desc = []
        for role_key, col in roles.items():
            if col:
                # Add accumulation state if available
                state = inspection.accumulation_states.get(col)
                state_str = f" ({state})" if state else ""
                roles_desc.append(f"{role_key} -> '{col}'{state_str}")
        roles_str = ", ".join(roles_desc) if roles_desc else "None"
        
        entity_msg = ""
        if inspection.entity_check.is_multi_entity:
            entity_msg = f" Note: Detected {inspection.entity_check.entity_count} entities under '{inspection.entity_check.entity_column}'."
            
        # Run Ingestion Compliance Checks
        session['compliance_engine'].run_ingestion_checks(df, inspection)
            
        return (f"Successfully parsed CSV ({len(df)} rows, {len(df.columns)} cols). "
            f"Classified as '{classification.data_type}' (Confidence: {classification.confidence})."
            f"{entity_msg} Mapped reserving roles: {roles_str}.")
    except Exception as e:
        return f"Failed to parse CSV: {str(e)}"

def perform_data_quality_checks(session_id: str) -> str:
    """Tool for Data Quality Agent: Performs initial data quality checks using pandas."""
    session = SESSION_STORE.get(session_id)
    if not session or session['df'] is None: return "Error: DataFrame not found. Run ingest_csv first."
    
    try:
        df = session['df']
        missing_values = df.isnull().sum()
        missing_report = ", ".join([f"{col}: {val}" for col, val in missing_values.items() if val > 0])
        total_missing = missing_values.sum()
        
        row_count = len(df)
        duplicates = df.duplicated().sum()
        
        report = f"Analyzed {row_count} rows. "
        if total_missing > 0:
            report += f"Found {total_missing} missing values ({missing_report}). "
        else:
            report += "No missing values found. "
            
        if duplicates > 0:
            report += f"Found {duplicates} duplicate rows."
            
        return report
    except Exception as e:
        return f"Failed to perform data quality checks: {str(e)}"

def build_loss_triangle(session_id: str) -> str:
    """Tool for Agent 2: Converts the Pandas DataFrame into an actuarial Loss Triangle."""
    session = SESSION_STORE.get(session_id)
    if not session or session['df'] is None: return "Error: DataFrame not found. Run ingest_csv first."
    
    try:
        val_year = session.get('valuation_year')
        inspection = session.get('inspection')
        roles = inspection.reserving_roles if inspection else {}
        t = Triangle(valuation_year=val_year, roles=roles)
        df = session['df']
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Filter by selected entities if applicable
        selected_entities = session.get('selected_entities')
        if selected_entities and inspection and inspection.entity_check.is_multi_entity:
            ent_col = inspection.entity_check.entity_column
            col_match = next((c for c in df.columns if c.lower() == ent_col.lower()), None)
            if col_match:
                df = df[df[col_match].astype(str).isin(selected_entities)]
                
        header = list(df.columns)
        t._format = t._detect_format(header)
        if t._format == 'long':
            t._parse_long(df)
        else:
            t._parse_wide(df)
        t._build_matrix()
            
        session['triangle'] = t
        summary = t.get_summary()
        summary['original_columns'] = session.get('original_columns', [])
        
        # Extract unique entities from the original dataframe
        entities = []
        if inspection and inspection.entity_check.is_multi_entity:
            ent_col = inspection.entity_check.entity_column
            col_match = next((c for c in session['df'].columns if c.lower() == ent_col.lower()), None)
            if col_match:
                entities = sorted(session['df'][col_match].dropna().unique().astype(str).tolist())
        summary['entities'] = entities
        summary['selected_entities'] = session.get('selected_entities')
        
        classification = session.get('classification')
        if classification:
            summary['classification'] = {
                'data_type': classification.data_type,
                'confidence': classification.confidence,
                'is_cas_format': classification.is_cas_format
            }
        if inspection:
            summary['inspection'] = {
                'is_multi_entity': inspection.entity_check.is_multi_entity,
                'entity_column': inspection.entity_check.entity_column,
                'entity_count': inspection.entity_check.entity_count,
                'reserving_roles': inspection.reserving_roles,
                'accumulation_states': inspection.accumulation_states
            }
        session['summary'] = summary
        
        # Run Summary Compliance Checks
        session['compliance_engine'].run_summary_checks(df, t)
        
        return f"Successfully built {t._format} format Triangle."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to build triangle: {str(e)}"

def calculate_ldfs(session_id: str) -> str:
    """Tool for Agent 3: Calculates Loss Development Factors (LDFs) using the user's requested n_years."""
    session = SESSION_STORE.get(session_id)
    if not session or session['triangle'] is None: return "Error: Triangle not found."
    
    try:
        t = session['triangle']
        ldfs = t.compute_ldfs()
        session['ldfs'] = ldfs
        
        inc_ldfs = t.compute_incurred_ldfs()
        session['incurred_ldfs'] = inc_ldfs
        
        return f"Successfully calculated LDFs (Volume Weighted and n-year averages). Tail factor is {ldfs[-1]['volumeWeighted']}."
    except Exception as e:
        return f"Failed to calculate LDFs: {str(e)}"

def analyze_exposures_and_premiums(session_id: str) -> str:
    """Tool for Agent 5: Analyzes the premium and exposure volume data from the triangle."""
    session = SESSION_STORE.get(session_id)
    if not session or session['triangle'] is None: return "Error: Triangle not found."
    
    try:
        t = session['triangle']
        prems = t.premiums
        exps = t.exposures
        
        if not prems and not exps:
            return "No premium or exposure data found in this dataset."
            
        avg_prem = sum(prems.values()) / len(prems) if prems else 0
        return f"Premium data found across {len(prems)} accident years. Average premium: {avg_prem:.2f}. Exposures count: {len(exps)}."
    except Exception as e:
        return f"Failed to analyze premiums: {str(e)}"



def compute_recommender_matrix(business_context: str, has_premium: bool, n_years: int = None) -> tuple[str, str]:
    scores = {
        "Chain Ladder (Development Method) [Code: CL / MCL]": 0,
        "Bornhuetter-Ferguson (BF) [Code: BF]": 0,
        "Cape Cod (Stanard-Buhlmann) [Code: CC]": 0,
        "Benktander [Code: BK]": 0,
        "Clark Stochastic [Code: CLK]": 0,
        "Expected Loss Ratio [Code: ELR]": 0
    }
    
    ctx = {}
    try:
        if business_context:
            ctx = json.loads(business_context)
    except:
        pass

    tail = ctx.get('tail', 'Not Known')
    vol = ctx.get('volatility', 'Not Known')
    env = ctx.get('environment', 'Not Known')
    distort = ctx.get('distortions', 'Not Known')

    if tail == "Short-tail": scores["Chain Ladder (Development Method) [Code: CL / MCL]"] += 2
    elif tail == "Long-tail":
        for m in ["Bornhuetter-Ferguson (BF) [Code: BF]", "Cape Cod (Stanard-Buhlmann) [Code: CC]", "Benktander [Code: BK]", "Expected Loss Ratio [Code: ELR]"]: scores[m] += 2
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] -= 2

    if vol == "Stable": scores["Chain Ladder (Development Method) [Code: CL / MCL]"] += 2
    elif vol == "Volatile":
        scores["Cape Cod (Stanard-Buhlmann) [Code: CC]"] += 2
        scores["Bornhuetter-Ferguson (BF) [Code: BF]"] += 2
        scores["Expected Loss Ratio [Code: ELR]"] += 3
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] -= 3

    if env == "Changing":
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] -= 4
        scores["Bornhuetter-Ferguson (BF) [Code: BF]"] += 1
    elif env == "Stable":
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] += 1

    if distort == "Present":
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] -= 3
        scores["Cape Cod (Stanard-Buhlmann) [Code: CC]"] += 1
        scores["Expected Loss Ratio [Code: ELR]"] += 2
    elif distort == "None":
        scores["Chain Ladder (Development Method) [Code: CL / MCL]"] += 1

    if n_years is not None:
        if n_years >= 7:
            scores["Chain Ladder (Development Method) [Code: CL / MCL]"] += 2
        elif n_years < 7:
            for m in ["Bornhuetter-Ferguson (BF) [Code: BF]", "Cape Cod (Stanard-Buhlmann) [Code: CC]", "Benktander [Code: BK]", "Expected Loss Ratio [Code: ELR]"]: scores[m] += 2
            scores["Chain Ladder (Development Method) [Code: CL / MCL]"] -= 2

    if not has_premium:
        scores["Bornhuetter-Ferguson (BF) [Code: BF]"] = -999
        scores["Cape Cod (Stanard-Buhlmann) [Code: CC]"] = -999
        scores["Benktander [Code: BK]"] = -999
        scores["Expected Loss Ratio [Code: ELR]"] = -999

    best_model = max(scores, key=scores.get)
    
    reasons = []
    if n_years is not None: reasons.append(f"the data has {n_years} historical years")
    if tail != "Not Known": reasons.append(f"the line is {tail}")
    if vol != "Not Known": reasons.append(f"the data is {vol}")
    if env != "Not Known": reasons.append(f"the environment is {env}")
    if distort != "Not Known": reasons.append(f"distortions are {distort}")
    
    if not has_premium and best_model not in ["Bornhuetter-Ferguson (BF) [Code: BF]", "Cape Cod (Stanard-Buhlmann) [Code: CC]", "Benktander [Code: BK]"]:
        reasons.append("premium data is unavailable")

    reason_str = "based on your responses" if not reasons else "because " + " and ".join(reasons)
    
    valid_models = {k: v for k, v in scores.items() if v > -900}
    sorted_models = sorted(valid_models.items(), key=lambda item: item[1], reverse=True)
    
    return sorted_models, reason_str


# ==========================================
# UNIVERSAL OPENAI CLIENT AGENT RUNNER
# ==========================================

# Expose run_agent at the module level for monkeypatching support
run_agent = utils_run_agent
# Reference copy for checking if monkeypatched
_original_run_agent = run_agent


# ==========================================
# AGENT ORCHESTRATION LAYER (Delegates to Multi-Agent Supervisor)
# ==========================================

_supervisor = SupervisorAgent()

def execute_sequential_pipeline_part1(session_id: str, rate_changes: list = None):
    """Delegates to SupervisorAgent to execute and stream pipeline part 1."""
    session = SESSION_STORE[session_id]
    yield from _supervisor.execute_sequential_pipeline_part1(session_id, session, rate_changes)

def execute_sequential_pipeline_part2(session_id: str, conditions: dict = None):
    """Delegates to SupervisorAgent to execute and stream pipeline part 2."""
    session = SESSION_STORE[session_id]
    yield from _supervisor.execute_sequential_pipeline_part2(session_id, session, conditions)

def run_reserve_recommendation_agent(session_id: str, results_summary: list) -> dict:
    """Delegates to SupervisorAgent to compile results, compare methods, and run recommendation."""
    session = SESSION_STORE.get(session_id)
    if not session:
        return {
            "recommended_method": "None",
            "confidence": "Low",
            "reasoning": ["Session expired or not found."]
        }
    return _supervisor.generate_recommendation_and_report(session_id, session, results_summary)

def run_parallel_chat(session_id: str, message: str, history: list) -> str:
    """Delegates to SupervisorAgent to process chatbot queries."""
    session = SESSION_STORE.get(session_id)
    if not session: return "Error: Session expired."
    return _supervisor.run_parallel_chat(session_id, session, message, history)
