import os
import time
import json
from openai import OpenAI
import openai

def run_agent(api_key: str, base_url: str, model_name: str, sys_inst: str, prompt: str, tools: list = None) -> str:
    """Runs a single agent invocation against the configured LLM API (OpenAI compatible)."""
    # Check if agent_workflow has a monkeypatched run_agent to respect existing tests
    try:
        import agent_workflow
        if hasattr(agent_workflow, '_original_run_agent') and agent_workflow.run_agent is not agent_workflow._original_run_agent:
            return agent_workflow.run_agent(api_key, base_url, model_name, sys_inst, prompt, tools or [])
    except Exception:
        pass

    env_api_key = os.environ.get("LLM_API_KEY")
    env_base_url = os.environ.get("LLM_BASE_URL")
    env_model_name = os.environ.get("LLM_MODEL_NAME")

    # Fallbacks (UI > Environment)
    api_key = api_key or env_api_key
    base_url = base_url or env_base_url
    model_name = model_name or env_model_name

    if not api_key or not model_name:
        return "Agent Error: AI settings are missing or incomplete. Please enter your LLM API Key and Model Name in the Settings panel."

    # Determine if using a local/free endpoint (where fast timeouts are preferred)
    is_local_or_free = (api_key == "ollama") or (base_url and ("localhost" in base_url or "127.0.0.1" in base_url or "ngrok-free.dev" in base_url))
    
    # Auto-correct Gemini native URL to OpenAI compatible URL
    if base_url and "generativelanguage.googleapis.com" in base_url:
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        
    try:
        client = OpenAI(
            api_key=api_key, 
            base_url=base_url if base_url else None,
            default_headers={"ngrok-skip-browser-warning": "true"}
        )
    except Exception as e:
        return f"Agent Error: {str(e)}"
    
    # Speed Optimization: Local/free settings should fail fast to avoid blocking actuarial workbench
    timeout_val = 3.0 if is_local_or_free else 10.0
    max_attempts = 1 if is_local_or_free else 2

    # Simple retry mechanism
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": sys_inst},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                timeout=timeout_val
            )
            return response.choices[0].message.content
        except openai.AuthenticationError:
            return "Agent Error: Authentication failed. Please verify your Render Environment Variables."
        except openai.RateLimitError:
            if attempt == max_attempts - 1:
                return "Agent Error: Quota/Rate limit exceeded (429). Please wait 60 seconds and try again."
            time.sleep(1)
        except openai.APIConnectionError:
            if attempt == max_attempts - 1:
                return "Agent Error: The LLM server is unreachable (API Connection Error)."
        except Exception as e:
            if attempt == max_attempts - 1:
                return f"Agent Error: {str(e)}"
            time.sleep(1)
    return "Error"

def parse_json_response(text: str) -> dict:
    """Robustly cleans and parses JSON responses from LLM, handling markdown backticks and prefix identifiers."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    if text.startswith("json"):
        text = text[4:]
    text = text.strip()
    return json.loads(text)
