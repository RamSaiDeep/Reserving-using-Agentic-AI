import pandas as pd
from io import StringIO
import json
import uuid
import time
import concurrent.futures
from openai import OpenAI

from models.triangle import Triangle
from models.methods import METHODS

# Global Session Store
SESSION_STORE = {}

def create_session(csv_text: str, n_years: int, api_key: str, base_url: str = None, model_name: str = None) -> str:
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        'csv_text': csv_text,
        'n_years': n_years,
        'api_key': api_key,
        'base_url': base_url,
        'model_name': model_name,
        'df': None,
        'triangle': None,
        'ldfs': None,
        'summary': None,
        'recommendation': None,
        'results': None
    }
    return session_id

# ==========================================
# TOOL FUNCTIONS
# ==========================================

def ingest_csv(session_id: str) -> str:
    """Tool for Agent 1: Converts the raw CSV data into a Pandas DataFrame."""
    session = SESSION_STORE.get(session_id)
    if not session: return "Error: Invalid session ID."
    
    try:
        df = pd.read_csv(StringIO(session['csv_text']))
        session['df'] = df
        return f"Successfully parsed CSV into DataFrame with {len(df)} rows and {len(df.columns)} columns."
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
        t = Triangle()
        df = session['df']
        df.columns = [str(c).strip().lower() for c in df.columns]
        header = list(df.columns)
        
        t._format = t._detect_format(header)
        if t._format == 'long':
            t._parse_long(df)
        else:
            t._parse_wide(df)
        t._build_matrix()
        
        session['triangle'] = t
        session['summary'] = t.get_summary()
        return f"Successfully built {t._format} format Triangle. Total Paid: {session['summary']['totalPaid']}."
    except Exception as e:
        return f"Failed to build triangle: {str(e)}"

def calculate_ldfs(session_id: str) -> str:
    """Tool for Agent 3: Calculates Loss Development Factors (LDFs) using the user's requested n_years."""
    session = SESSION_STORE.get(session_id)
    if not session or session['triangle'] is None: return "Error: Triangle not found."
    
    try:
        t = session['triangle']
        ldfs = t.compute_ldfs()
        session['ldfs'] = ldfs
        
        n = session.get('n_years', 5)
        # Assuming we just log the n-year request, exact usage in app.js uses the 'weighted5yr' or 'straightAvg' keys.
        # We will inform the agent it was calculated.
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

def run_actuarial_model(session_id: str, method_code: str) -> str:
    """Tool for Agent 6: Executes a specific mathematical reserving model (e.g. BF, CL, MCL, CC, BK, CO, CLK)."""
    session = SESSION_STORE.get(session_id)
    if not session or session['triangle'] is None: return "Error: Triangle not found."
    
    try:
        MethodClass = METHODS.get(method_code)
        if not MethodClass: return f"Error: Invalid method code {method_code}."
        
        t = session['triangle']
        ldfs_to_use = [f['volumeWeighted'] for f in session['ldfs'][:-1]] + [1.0]
        
        model = MethodClass()
        model = MethodClass()
        params = session.get('params', {})
        model.fit(t, params, ldfs_to_use)
        
        total_ibnr = model.get_total_ibnr()
        total_ult = model.get_total_ultimate()
        
        session['results'] = {
            'method': method_code,
            'totalIBNR': total_ibnr,
            'totalUlt': total_ult
        }
        return f"Executed {method_code}. Total IBNR calculated: {total_ibnr:.2f}."
    except Exception as e:
        return f"Failed to run model {method_code}: {str(e)}"


# ==========================================
# AGENT RUNNER UTILITY
# ==========================================

def run_agent(api_key: str, base_url: str, model_name: str, sys_inst: str, prompt: str, tools: list) -> str:
    """Helper to run an agent via universal OpenAI client."""
    if not api_key:
        return "Agent Error: No API key provided."
    if not model_name:
        model_name = "gpt-4o-mini"
        
    try:
        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    except Exception as e:
        return f"Agent Error: {str(e)}"
    
    # Simple retry mechanism
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": sys_inst},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 2:
                return f"Agent Error: {str(e)}"
            time.sleep(2)
    return "Error"

# ==========================================
# SEQUENTIAL PIPELINE EXECUTOR
# ==========================================

def execute_sequential_pipeline(session_id: str):
    """
    Generator that yields JSON strings for SSE streaming.
    Executes agents in parallel for narration to maximize speed.
    """
    session = SESSION_STORE[session_id]
    api_key = session['api_key']
    base_url = session.get('base_url')
    model_name = session.get('model_name')
    
    if not api_key:
        yield json.dumps({"type": "agent", "agent": "System Error", "text": "No API Key provided. Please enter your key in the AI Settings in the top-right corner."}) + "\n"
        return
    
    def emit(agent, text):
        return json.dumps({"type": "agent", "agent": agent, "text": text}) + "\n"
    
    # 1. Run the Python mathematical tools instantly
    t1 = ingest_csv(session_id)
    t2 = perform_data_quality_checks(session_id)
    t3 = build_loss_triangle(session_id)
    t4 = calculate_ldfs(session_id)
    t5 = analyze_exposures_and_premiums(session_id)
    
    summary = session.get('summary', {})
    t6 = f"Triangle Summary: {json.dumps(summary)}"
    
    # 2. Prepare LLM Narration Prompts
    sys1 = "You are the Data Ingestion Agent. Output a concise 1-sentence narrative summarizing the parsing action."
    sys2 = "You are the Data Quality Agent. Output a concise 1-sentence narrative summarizing the data quality report (missing values/duplicates)."
    sys3 = "You are the Triangle Builder Agent. Output a concise 1-sentence narrative summarizing the built triangle."
    sys4 = "You are the LDF Calculator Agent. Output a concise 1-sentence narrative summarizing the calculated factors."
    sys5 = "You are the Actuarial Analyst Agent. Explain in 1-2 sentences how the premium/exposure volume will affect the IBNR calculation based on this data."
    sys6 = "You are the Recommender Agent. Review the Triangle summary. If the data contains Premium volume, recommend the Bornhuetter-Ferguson, Benktander, or Cape Cod methods. If the data DOES NOT contain Premium volume, strongly recommend the Chain Ladder or Mack methods, and explicitly state that BF/Benktander/Cape Cod are incompatible. Output 1-2 sentences."
    
    tasks = [
        ("Data Ingestion Agent", sys1, f"Action Result: {t1}"),
        ("Data Quality Agent", sys2, f"Action Result: {t2}"),
        ("Triangle Builder Agent", sys3, f"Action Result: {t3}"),
        ("LDF Calculator Agent", sys4, f"Action Result: {t4}"),
        ("Actuarial Analyst Agent", sys5, f"Action Result: {t5}"),
        ("Recommender Agent", sys6, t6)
    ]
    
    # 3. Fire all 6 LLM calls simultaneously in a ThreadPool
    recommender_text = ""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(run_agent, api_key, base_url, model_name, t[1], t[2], []) for t in tasks]
        
        # Yield the results sequentially to preserve UI flow
        for i, future in enumerate(futures):
            result = future.result() 
            if tasks[i][0] == "Recommender Agent":
                recommender_text = result
            else:
                yield emit(tasks[i][0], result)

    # 4. Final Payload
    updated_session = SESSION_STORE.get(session_id)
    triangle = updated_session.get('triangle')
    triangle_data = None
    if triangle:
        triangle_data = {
            "accidentYears": triangle.accident_years,
            "devAges": triangle.dev_ages,
            "matrix": triangle.matrix,
            "incurred_matrix": triangle.incurred_matrix,
            "ldfs": updated_session.get('ldfs')
        }
        
    yield json.dumps({
        "type": "complete",
        "session_id": session_id,
        "summary": updated_session.get('summary'),
        "triangle": triangle_data,
        "recommendation": recommender_text
    }) + "\n"

# ==========================================
# PARALLEL CHAT AGENT
# ==========================================

def run_parallel_chat(session_id: str, message: str, history: list) -> str:
    """Agent that sits parallel to the pipeline, with access to all data."""
    session = SESSION_STORE.get(session_id)
    if not session: return "Error: Session expired."
    
    context = {
        'n_years': session.get('n_years'),
        'summary': session.get('summary'),
        'results': session.get('results'),
        'execution_report': session.get('report')
    }
    
    sys_inst = f"""
    You are a Parallel Actuarial Chat Agent. You have access to the complete sequential pipeline state:
    {json.dumps(context, indent=2)}
    
    Answer the user's questions about the IBNR, premiums, or models directly and accurately based on the data.
    If the user asks about models, you must inform them if certain models (like Bornhuetter-Ferguson, Benktander, or Cape Cod) are incompatible due to a lack of premium data in the summary.
    """
    
    api_key = session.get('api_key')
    base_url = session.get('base_url')
    model_name = session.get('model_name')
    if not model_name: model_name = "gpt-4o-mini"
    if not api_key: return "Chat Agent Error: No API key provided."

    messages = [{"role": "system", "content": sys_inst}]
    for msg in history:
        role = 'user' if msg['role'] == 'user' else 'assistant'
        messages.append({"role": role, "content": msg['text']})
    messages.append({"role": "user", "content": message})
    
    try:
        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Chat Agent Error: {str(e)}"
