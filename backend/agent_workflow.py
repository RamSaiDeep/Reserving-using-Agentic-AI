import pandas as pd
from io import StringIO
import json
import uuid
import time
from google import genai

from models.triangle import Triangle
from models.methods import METHODS

# Global Session Store
SESSION_STORE = {}

def create_session(csv_text: str, n_years: int, api_key: str) -> str:
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        'csv_text': csv_text,
        'n_years': n_years,
        'api_key': api_key,
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

def run_agent(api_key: str, sys_inst: str, prompt: str, tools: list) -> str:
    """Helper to run a Gemini agent with specific tools."""
    client = genai.Client(api_key=api_key)
    
    # Simple retry mechanism
    for attempt in range(3):
        try:
            config = genai.types.GenerateContentConfig(
                system_instruction=sys_inst,
                tools=tools if tools else None,
                temperature=0.2
            )
            chat = client.chats.create(model="gemini-2.5-flash", config=config)
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            if attempt == 2:
                return f"Agent Error: {str(e)}"
            time.sleep(2)
    return "Error"

# ==========================================
# SEQUENTIAL PIPELINE EXECUTOR
# ==========================================

def execute_sequential_pipeline(session_id: str) -> list:
    """Executes Agents 1 through 5 sequentially and returns their narratives."""
    session = SESSION_STORE.get(session_id)
    api_key = session['api_key']
    narratives = []
    
    # Agent 1: Ingestion
    sys1 = "You are the Data Ingestion Agent. You MUST call the `ingest_csv` tool exactly once with the provided session_id. Then, output a concise 1-sentence narrative saying you converted the CSV to a Pandas DataFrame."
    msg1 = run_agent(api_key, sys1, f"Process session_id: {session_id}", [ingest_csv])
    narratives.append({'agent': 'Data Ingestion Agent', 'text': msg1})
    
    # Agent 2: Triangle
    sys2 = "You are the Triangle Builder Agent. You MUST call the `build_loss_triangle` tool exactly once with the provided session_id. Then, output a concise 1-sentence narrative saying you built the loss triangle."
    msg2 = run_agent(api_key, sys2, f"Process session_id: {session_id}", [build_loss_triangle])
    narratives.append({'agent': 'Triangle Builder Agent', 'text': msg2})
    
    # Agent 3: LDF
    sys3 = "You are the LDF Calculator Agent. You MUST call the `calculate_ldfs` tool exactly once. Then, output a concise 1-sentence narrative saying you calculated the factors."
    msg3 = run_agent(api_key, sys3, f"Process session_id: {session_id}", [calculate_ldfs])
    narratives.append({'agent': 'LDF Calculator Agent', 'text': msg3})
    
    # Agent 4: Recommender
    summary = session.get('summary', {})
    sys4 = "You are the Recommender Agent. Review the Triangle summary. If it's a new line of business (isNewLOB) or has less data, strongly recommend the Bornhuetter-Ferguson (BF) or Chain Ladder (CL) methods. Otherwise, recommend Cape Cod or Mack. Output 2-3 sentences."
    msg4 = run_agent(api_key, sys4, f"Triangle Summary: {json.dumps(summary)}", [])
    narratives.append({'agent': 'Recommender Agent', 'text': msg4})
    
    # Agent 5: Analyst
    sys5 = "You are the Actuarial Analyst Agent. You MUST call the `analyze_exposures_and_premiums` tool. Then, explain in 2-3 sentences how the premium/exposure volume will affect the IBNR calculation."
    msg5 = run_agent(api_key, sys5, f"Process session_id: {session_id}", [analyze_exposures_and_premiums])
    narratives.append({'agent': 'Actuarial Analyst Agent', 'text': msg5})
    
    # Re-fetch session data that tools modified
    updated_session = SESSION_STORE.get(session_id)
    return narratives, updated_session['summary'], updated_session['triangle'], updated_session['ldfs']

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
        'results': session.get('results')
    }
    
    sys_inst = f"""
    You are a Parallel Actuarial Chat Agent. You have access to the complete sequential pipeline state:
    {json.dumps(context, indent=2)}
    
    Answer the user's questions about the IBNR, premiums, or models directly and accurately based on the data.
    """
    
    # Convert history
    contents = []
    for msg in history:
        role = 'user' if msg['role'] == 'user' else 'model'
        contents.append(genai.types.Content(role=role, parts=[genai.types.Part.from_text(msg['text'])]))
    contents.append(genai.types.Content(role='user', parts=[genai.types.Part.from_text(message)]))
    
    client = genai.Client(api_key=session['api_key'])
    try:
        config = genai.types.GenerateContentConfig(system_instruction=sys_inst, temperature=0.5)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=contents, config=config)
        return response.text
    except Exception as e:
        return f"Chat Agent Error: {str(e)}"
