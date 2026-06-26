import json
import concurrent.futures
import time
from openai import OpenAI
from agents.diagnostics_agent import DiagnosticsAgent
from agents.comparison_agent import ComparisonAgent
from agents.recommendation_agent import RecommendationAgent
from agents.reporting_agent import ReportingAgent
from agents.utils import run_agent, _log_instrumentation_call, token_estimator, TOKEN_BUDGETS
from agents.prompt_builders import ChatPromptBuilder, ChatIntent, ChatRequest, ChatClassifier, ContextBuilder
from agents.parser import parse_request
from agents.planner import create_execution_plan
from agents.stage_manager import StageManager

class SupervisorAgent:
    """
    SupervisorAgent
    Entry point.
    Responsible for:
      - receiving user intent
      - routing work to specialist agents
      - maintaining workflow state
      - combining responses
      - making supervisor decisions based on deterministic diagnostics
    Never performs actuarial calculations.
    """
    def __init__(self):
        pass

    def execute_sequential_pipeline_part1(self, session_id: str, session: dict, rate_changes: list = None):
        """Orchestrates Part 1 of the pipeline (Parsing, DQ checks, Triangle, LDF calculation)."""
        from agent_workflow import ingest_csv, perform_data_quality_checks, build_loss_triangle, calculate_ldfs
        
        def emit(agent, text):
            return json.dumps({"type": "agent", "agent": agent, "text": text}) + "\n"
        
        # 1. Run the initial parsing tools
        t1 = ingest_csv(session_id)
        t2 = perform_data_quality_checks(session_id)
        
        # Flush Cloudflare/Nginx buffer with 4KB of whitespace padding
        yield json.dumps({"type": "padding", "data": " " * 4096}) + "\n"
        
        # 2. Process Rate Changes
        t3 = build_loss_triangle(session_id)
        triangle = session.get('triangle')
        
        # Decision: If triangle is not built, stop execution and raise error
        if not triangle:
            yield emit("Analysis Agent", "Critical Data Error: Could not build loss triangle from this dataset.")
            return
            
        preprocessing_text = "No premium data found in dataset to on-level."
        if rate_changes and triangle and triangle.premiums:
            try:
                import pandas as pd
                from reserving.core.on_level import OnLevelPremiumCalculator
                prem_data = [{"accident_year": int(ay), "earned_premium": float(p)} for ay, p in triangle.premiums.items()]
                calc = OnLevelPremiumCalculator(pd.DataFrame(prem_data), pd.DataFrame(rate_changes))
                on_level_df = calc.calculate()
                
                # Update premiums in place before building the summary
                triangle.premiums = dict(zip(on_level_df["accident_year"], on_level_df["on_level_premium"]))
                preprocessing_text = "Action Result: Successfully calculated On-Level Premiums using the provided rate changes."
            except Exception as e:
                preprocessing_text = f"Action Result: Failed to calculate on-level premiums: {str(e)}"
        elif rate_changes:
            preprocessing_text = "Action Result: Rate changes were provided, but the uploaded dataset has no Premium column to on-level."
        else:
            preprocessing_text = "Action Result: No historical rate changes were provided."

        # 3. Run remaining tools for part 1
        t4 = calculate_ldfs(session_id)
        
        # 4. Stream Deterministic Outputs via Analysis Agent
        yield emit("Analysis Agent", f"Data Ingestion: {t1}")
        yield emit("Analysis Agent", f"Data Quality: {t2}")
        yield emit("Analysis Agent", preprocessing_text)
        yield emit("Analysis Agent", f"Triangle Builder: {t3}")
        yield emit("Analysis Agent", f"LDF Calculator: {t4}")

        # Continue to Part 2
        yield from self.execute_sequential_pipeline_part2(session_id, session)

    def execute_sequential_pipeline_part2(self, session_id: str, session: dict, conditions: dict = None):
        """Orchestrates Part 2 of the pipeline (Mechanical matrix compatibility)."""
        from agent_workflow import compute_recommender_matrix
        
        def emit(agent, text):
            return json.dumps({"type": "agent", "agent": agent, "text": text}) + "\n"

        triangle = session.get('triangle')
        has_premium = bool(triangle and triangle.premiums)
        business_context = session.get('business_context', '')
        n_years = session.get('n_years')
        
        sorted_models, matrix_reason = compute_recommender_matrix(business_context, has_premium, n_years)
        best_model = sorted_models[0][0] if sorted_models else "None"
        
        # Construct mechanical HTML response
        md_lines = [
            f"<b>Mechanical Matrix Recommendation</b>",
            f"<br/>The optimal method is <b>{best_model}</b>, {matrix_reason}.",
            f"<br/><br/><b>Model Compatibility Scores:</b><br/>",
            f"<i>(Higher is better. Incompatible models are hidden)</i><br/><ul style='margin-top: 8px;'>"
        ]
        for model, score in sorted_models:
            md_lines.append(f"<li><b>{model}</b>: {score} points</li>")
        md_lines.append("</ul>")
            
        recommender_text = "".join(md_lines)
        yield emit("Recommender Agent", "I have analyzed the data and provided a model recommendation in the main panel.")

        # Final Payload
        triangle_data = None
        if triangle:
            from reserving.core.tools import compute_suggested_elr, compute_mature_accident_years, compute_method_availability
            mature_info = compute_mature_accident_years(triangle)
            triangle_data = {
                "accidentYears": triangle.accident_years,
                "devAges": triangle.dev_ages,
                "matrix": triangle.matrix,
                "incurred_matrix": triangle.incurred_matrix,
                "ldfs": session.get('ldfs'),
                "incurred_ldfs": session.get('incurred_ldfs'),
                "hasPremium": bool(triangle.premiums),
                "suggested_elr_paid": compute_suggested_elr(triangle, "paid"),
                "suggested_elr_incurred": compute_suggested_elr(triangle, "incurred"),
                "suggested_mature_years": mature_info.get("mature_years", []),
                "mature_reasoning": mature_info.get("reasoning", {}),
                "method_availability": compute_method_availability(triangle)
            }
            
        yield json.dumps({
            "type": "complete",
            "session_id": session_id,
            "summary": session.get('summary'),
            "triangle": triangle_data,
            "recommendation": recommender_text
        }) + "\n"

    def generate_recommendation_and_report(self, session_id: str, session: dict, results_summary: list) -> dict:
        """
        Orchestrates the full specialist agent suite:
        1. DiagnosticsAgent for qualitative assessments of the data.
        2. ComparisonAgent to compare reserving results.
        3. RecommendationAgent to choose the best reserving method.
        4. ReportingAgent to write the final actuarial report.
        """
        api_key = session.get('api_key')
        base_url = session.get('base_url')
        model_name = session.get('model_name')
        triangle = session.get('triangle')
        df = session.get('df')

        # 1. Run deterministic diagnostics first to apply supervisor decisions
        from reserving.diagnostics.diagnostics import compute_diagnostics
        raw_metrics = compute_diagnostics(triangle)
        overall = raw_metrics.get('overall', {})
        
        # ── Supervisor Decision Intelligence ──────────────────────────────────
        
        # A. Stop execution if poor data quality is identified
        n_ays = overall.get("n_accident_years", 0)
        n_devs = overall.get("n_dev_periods", 0)
        total_paid = overall.get("total_paid", 0.0)
        
        if n_ays < 3 or n_devs < 3:
            raise ValueError(
                f"Data Quality Error: The loss triangle is too small (Accident Years: {n_ays}, "
                f"Development Periods: {n_devs}). At least 3 accident years and development periods "
                f"are required for stable actuarial calculations. Please re-upload a complete dataset."
            )
            
        if total_paid <= 0:
            raise ValueError(
                "Data Quality Error: The total paid claims in the latest diagonal is zero or negative. "
                "Actuarial reserving methods cannot be executed on zero or negative cumulative claims. "
                "Please verify your data mapping and re-upload."
            )
            
        supervisor_cautions = []
        
        # B. If LDF volatility is high: prioritize Mack and compare against BF
        ldf_stab = raw_metrics.get("ldf_stability", {})
        avg_cov = ldf_stab.get("average_cov", 0.0)
        if ldf_stab.get("cl_suitable_indicator") == "Unstable" or avg_cov > 0.12:
            supervisor_cautions.append("High LDF volatility detected (avg CoV > 0.12). Prioritized Mack Chain Ladder to quantify reserve uncertainty; recommend comparing against Bornhuetter-Ferguson (BF) for stability.")
            
        # C. If premium is unavailable: skip Cape Cod and ELR
        has_premium = overall.get("has_premium", False)
        if not has_premium:
            results_summary = [r for r in results_summary if r.get("code") not in ["BF", "BK", "CC", "ELR"]]
            
        # D. If reporting pattern fit is poor: warn user and lower confidence
        rep_pattern = raw_metrics.get("reporting_pattern", {})
        fit_metrics = rep_pattern.get("fit_metrics", {})
        r2 = fit_metrics.get("r2", 1.0)
        if r2 < 0.60:
            supervisor_cautions.append("Poor reporting pattern growth curve fit (R2 < 0.60). Reduced confidence in development-based methods.")

        # 2. Run DiagnosticsAgent and ComparisonAgent concurrently
        # Each future has a 30s timeout so a slow model (e.g. OpenRouter/NVIDIA 524)
        # cannot block the pipeline for more than 30s on this stage.
        diag_agent = DiagnosticsAgent(api_key, base_url, model_name)
        comp_agent = ComparisonAgent(api_key, base_url, model_name)
        
        _diag_fallback = {
            "metrics": compute_diagnostics(triangle),
            "llm_analysis": {"data_quality_assessment": "Diagnostics timed out — deterministic metrics are still available."}
        }
        _comp_fallback = {"comparison_table": [], "differences": {}, "explanation": "Comparison timed out — numerical indications above are still valid."}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            diag_future = executor.submit(diag_agent.analyze, triangle, df)
            comp_future = executor.submit(comp_agent.compare, results_summary)
            
            try:
                diagnostics = diag_future.result(timeout=30.0)
            except (concurrent.futures.TimeoutError, Exception) as e:
                print(f"[DiagnosticsAgent] Timeout/Error — using fallback: {e}")
                diagnostics = _diag_fallback
                
            try:
                comparison = comp_future.result(timeout=30.0)
            except (concurrent.futures.TimeoutError, Exception) as e:
                print(f"[ComparisonAgent] Timeout/Error — using fallback: {e}")
                comparison = _comp_fallback
            
        session['diagnostics_analysis'] = diagnostics
        session['comparison'] = comparison

        # 3. Prepare reserving outputs
        results_val = session.get('results') or {}
        reserving_outputs = {
            "selected_method": results_val.get('method', 'CL') if isinstance(results_val, dict) else 'CL',
            "best_estimate": results_val.get('totalUlt', 0.0) if isinstance(results_val, dict) else 0.0,
            "methods": results_summary
        }

        # 4. Run RecommendationAgent (30s timeout with deterministic fallback)
        rec_agent = RecommendationAgent(api_key, base_url, model_name)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                rec_future = executor.submit(rec_agent.recommend, diagnostics, reserving_outputs, comparison)
                recommendation = rec_future.result(timeout=30.0)
        except (concurrent.futures.TimeoutError, Exception) as e:
            print(f"[RecommendationAgent] Timeout/Error — using deterministic fallback: {e}")
            # Deterministic fallback: pick method with highest suitability score
            metrics_inner = diagnostics.get("metrics", {})
            suitability = metrics_inner.get("suitability", {})
            scores = suitability.get("scores", {})
            best_method = max(scores, key=scores.get) if scores else "CL"
            from reserving.diagnostics.trace_generator import generate_decision_trace
            recommendation = {
                "recommended_method": best_method,
                "confidence": "Medium",
                "reasoning": ["Deterministic fallback: selected based on highest suitability score.", f"LLM recommendation timed out: {str(e)}"],
                "assumptions_used": "Volume weighted LDF averages.",
                "cautions": ["AI recommendation pipeline timed out. Result is based on deterministic suitability scoring only."],
                "alternative_methods": [],
                "decision_trace": generate_decision_trace(metrics_inner, best_method)
            }
        
        # Apply supervisor dynamic intelligence overrides
        cautions_list = recommendation.get("cautions", [])
        for c in supervisor_cautions:
            if c not in cautions_list:
                cautions_list.append(c)
        recommendation["cautions"] = cautions_list
        
        # If reporting pattern fit is poor, lower confidence in development methods
        rec_method = recommendation.get("recommended_method", "CL")
        if r2 < 0.60 and rec_method in ["CL", "MCL"]:
            recommendation["confidence"] = "Low"
            
        session['recommendation'] = recommendation

        # 5. Run ReportingAgent — non-blocking with a 25s wall-clock limit
        # If the model is slow (e.g. OpenRouter/NVIDIA 524s), we fall back to a
        # deterministic template so the recommendation still returns to the user.
        def _run_report():
            try:
                rep_agent = ReportingAgent(api_key, base_url, model_name)
                report = rep_agent.generate_report(diagnostics, reserving_outputs, comparison, recommendation)
                session['report_markdown'] = report.get('report_markdown')
                session['report'] = report.get('report_markdown')
            except Exception as e:
                print(f"[ReportingAgent] Non-blocking fallback triggered: {e}")

        report_future = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_run_report)
        try:
            report_future.result(timeout=25.0)
        except concurrent.futures.TimeoutError:
            # Report generation timed out — build a fast deterministic fallback
            rec_method = recommendation.get('recommended_method', 'CL')
            rec_confidence = recommendation.get('confidence', 'Medium')
            rec_reasoning = recommendation.get('reasoning', [])
            fallback_report = (
                f"# Actuarial Reserving Report\n\n"
                f"## Executive Summary\n"
                f"**Recommended Method:** {rec_method} | **Confidence:** {rec_confidence}\n\n"
                f"## Reasoning\n"
                + "\n".join(f"- {r}" for r in rec_reasoning) +
                f"\n\n## Note\n"
                f"Full report generation timed out. The recommendation above is based on deterministic "
                f"suitability scoring and diagnostics and is not affected by this timeout.\n"
            )
            session['report_markdown'] = fallback_report
            session['report'] = fallback_report
            print("[ReportingAgent] Timeout reached — deterministic fallback report stored.")
        except Exception as e:
            print(f"[ReportingAgent] Unexpected error in non-blocking wrapper: {e}")

        # Return recommendation dict formatted exactly as expected by the UI/reserving engine
        return {
            "recommended_method": recommendation.get("recommended_method", "CL"),
            "confidence": recommendation.get("confidence", "Medium"),
            "reasoning": recommendation.get("reasoning", ["Determined by Multi-Agent recommendation layer."]),
            "assumptions_used": recommendation.get("assumptions_used", ""),
            "cautions": recommendation.get("cautions", []),
            "alternative_methods": recommendation.get("alternative_methods", []),
            "decision_trace": recommendation.get("decision_trace", [])
        }

    def answer_dataset_query(self, session: dict, message: str) -> str:
        """Deterministically answers dataset metadata questions from the uploaded dataframe or session metadata."""
        df = session.get('df')
        triangle = session.get('triangle')
        summary = session.get('summary')
        
        if df is None:
            return "No dataset has been prepared. Please upload a dataset first."
            
        msg_lower = message.lower()
        
        # 1. Shape/Rows/Size
        if any(k in msg_lower for k in ["row", "shape", "size", "dimension", "record"]):
            return f"The dataset contains {len(df)} rows and {len(df.columns)} columns (shape: {df.shape[0]} x {df.shape[1]})."
            
        # 2. Columns/Variables
        if any(k in msg_lower for k in ["column", "variable", "field", "header"]):
            cols = ", ".join([f"'{c}'" for c in df.columns])
            return f"The following columns/variables are present in the dataset: {cols}."
            
        # 3. Accident Years
        if any(k in msg_lower for k in ["accident year", "origin year", "accident years", "origin years", "origin period", "accident period", "accident periods"]):
            if triangle and triangle.accident_years:
                ays = sorted(list(triangle.accident_years))
                return f"There are {len(ays)} accident years present in the dataset: {', '.join(map(str, ays))} (ranging from {ays[0]} to {ays[-1]})."
            return "Accident years could not be extracted from the dataset."
            
        # 4. Missing values
        if any(k in msg_lower for k in ["missing", "null", "nan", "blank", "empty"]):
            missing_counts = df.isnull().sum()
            total_missing = missing_counts.sum()
            if total_missing == 0:
                return "There are no missing values in the dataset."
            else:
                details = ", ".join([f"'{col}': {count}" for col, count in missing_counts.items() if count > 0])
                return f"The dataset has {total_missing} missing values. Breakdown by column: {details}."
                
        # 5. Entities
        if any(k in msg_lower for k in ["entit", "company", "companies", "segment", "segments", "lob", "line of business", "lines of business", "carrier", "carriers"]):
            entities = summary.get('entities') if summary else None
            if entities:
                return f"The following entities are present in the dataset: {', '.join(entities)} (total of {len(entities)} entities)."
            return "No multiple entities or segmentations were detected in the dataset."
            
        # 6. Development periods
        if any(k in msg_lower for k in ["dev", "period", "age", "development period", "development periods", "dev period", "dev periods"]):
            if triangle and triangle.dev_ages:
                periods = sorted(list(triangle.dev_ages))
                return f"The following development periods are present: {', '.join(map(str, periods))} (total of {len(periods)} periods)."
            return "Development periods could not be extracted from the dataset."
            
        # Fallback dataset summary
        cols = ", ".join([f"'{c}'" for c in df.columns])
        num_ays = len(triangle.accident_years) if (triangle and triangle.accident_years) else 0
        ays_str = f" (ranging from {triangle.accident_years[0]} to {triangle.accident_years[-1]})" if (triangle and triangle.accident_years) else ""
        num_devs = len(triangle.dev_ages) if (triangle and triangle.dev_ages) else 0
        
        return (
            f"Dataset Summary:\n"
            f"- Shape: {df.shape[0]} rows by {df.shape[1]} columns\n"
            f"- Columns: {cols}\n"
            f"- Accident Years: {num_ays}{ays_str}\n"
            f"- Development Periods: {num_devs}\n"
            f"- Missing Values: {df.isnull().sum().sum()}"
        )

    def run_parallel_chat(self, session_id: str, session: dict, message: str, history: list) -> str:
        """Delegates chat queries to the stage manager and LLM, enriching context dynamically."""
        api_key = session.get('api_key')
        base_url = session.get('base_url')
        model_name = session.get('model_name')
        
        # 1. Parse request deterministically
        parsed_req = parse_request(message, history)
        
        # 2. Classify intent to ChatRequest
        chat_req = ChatClassifier.classify(message, parsed_req)
        
        # 3. Conversational Memory: Inherit missing entities from session chat state
        if chat_req.intent in [ChatIntent.CALCULATION, ChatIntent.COMPARISON, ChatIntent.DIAGNOSTIC, ChatIntent.RECOMMENDATION]:
            if not chat_req.methods and session.get('last_method'):
                chat_req.methods = session.get('last_method')
            if not chat_req.basis and session.get('last_basis'):
                chat_req.basis = session.get('last_basis')
            if not chat_req.columns and session.get('last_columns'):
                chat_req.columns = session.get('last_columns')
            if "accident_year" not in chat_req.entities and session.get('last_accident_year'):
                chat_req.entities["accident_year"] = session.get('last_accident_year')
                
        # Update parsed_req with the inherited entities to keep stage planner aligned
        parsed_req["methods"] = chat_req.methods
        parsed_req["basis"] = chat_req.basis
        
        # 4. Refuse out of scope/unknown immediately
        if chat_req.intent == ChatIntent.UNKNOWN:
            return (
                "This assistant is designed specifically for actuarial reserving analysis. "
                "I can answer questions about uploaded datasets, reserving methods, diagnostics, "
                "model comparisons, reserve estimates, and actuarial concepts. "
                "Your question is outside the scope of this application."
            )
            
        # 5. Create execution plan
        plan = create_execution_plan(parsed_req)
        
        # 6. Resolve and execute stages via Stage Manager if required by chat intent
        trace = []
        if chat_req.intent not in [ChatIntent.CONCEPTUAL, ChatIntent.METHOD_EXPLANATION, ChatIntent.UNKNOWN]:
            try:
                manager = StageManager()
                if chat_req.intent in [ChatIntent.RECOMMENDATION, ChatIntent.REPORT] or plan["need_recommendation"]:
                    manager.ensure_stage("recommendation", plan, session_id, session, trace)
                elif chat_req.intent in [ChatIntent.CALCULATION, ChatIntent.COMPARISON, ChatIntent.DIAGNOSTIC] or plan["need_results"]:
                    manager.ensure_stage("results", plan, session_id, session, trace)
                elif chat_req.intent in [ChatIntent.COLUMN_INFO, ChatIntent.DATA_EXPLORATION] or plan["need_dataset"]:
                    manager.ensure_stage("preprocessing", plan, session_id, session, trace)
            except Exception as e:
                return f"Actuarial Assistant Error: {str(e)}"
            
        # 7. Render prompt context using ContextBuilder & ChatPromptBuilder
        context = ContextBuilder.build(session, chat_req)
        sys_inst, sections = ChatPromptBuilder.render(context, chat_req.intent)
        
        # Prepend trace to chat history so LLM can refer to execution details
        chat_prompt = ""
        messages = [{"role": "system", "content": sys_inst}]
        for msg in history:
            role = 'user' if msg['role'] == 'user' else 'assistant'
            messages.append({"role": role, "content": msg['text']})
            
        # Format user message including trace if trace steps occurred
        user_content = message
        if trace:
            trace_block = "\n".join(trace)
            user_content = (
                f"[Actuarial Execution Trace]\n"
                f"{trace_block}\n"
                f"----------------------------------------\n"
                f"{message}"
            )
        messages.append({"role": "user", "content": user_content})
        
        # Build chat prompt string for instrumentation tracking
        for m in messages[1:]:
            chat_prompt += f"\n[{m['role']}]: {m['content']}"
            
        # Pre-execution hard budget check (based on estimation)
        budgets = TOKEN_BUDGETS.get("ChatAgent", {"soft": 10000, "hard": 18000})
        hard_limit = budgets.get("hard", 18000)
        estimated_input = token_estimator(sys_inst + chat_prompt)
        
        if estimated_input > hard_limit:
            raise ValueError(
                f"Pre-execution Cancelled: Estimated prompt size for ChatAgent is {estimated_input} tokens, "
                f"which exceeds the configured hard token budget limit of {hard_limit} tokens."
            )
            
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "calculate_on_level_premiums",
                    "description": "Calculates on-level premiums using historical rate changes and the currently active premium dataset.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rate_changes": {
                               "type": "array",
                                "description": "Array of rate changes.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "effective_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                                        "rate_change": {"type": "number", "description": "Rate change as a decimal (e.g. 0.05 for +5%)"}
                                    },
                                    "required": ["effective_date", "rate_change"]
                                }
                            }
                        },
                        "required": ["rate_changes"]
                    }
                }
            }
        ]
        
        is_local_or_free = (
            (api_key == "ollama") or 
            (base_url and ("localhost" in base_url or "127.0.0.1" in base_url or "ngrok-free.dev" in base_url or "openrouter.ai" in base_url)) or
            (model_name and "free" in model_name.lower())
        )
        timeout_val = 30.0 if is_local_or_free else 10.0
        
        try:
            client = OpenAI(
                api_key=api_key, 
                base_url=base_url if base_url else None,
                default_headers={"ngrok-skip-browser-warning": "true"}
            )
            
            start_time = time.perf_counter()
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                temperature=0.5,
                timeout=timeout_val
            )
            elapsed = time.perf_counter() - start_time
            
            response_msg = response.choices[0].message
            
            actual_prompt = None
            actual_completion = None
            if hasattr(response, 'usage') and response.usage:
                actual_prompt = getattr(response.usage, 'prompt_tokens', None)
                actual_completion = getattr(response.usage, 'completion_tokens', None)
                
            # Log instrumentation
            _log_instrumentation_call(
                agent_name="ChatAgent",
                sys_inst=sys_inst,
                prompt=chat_prompt,
                response_content=response_msg.content or "",
                elapsed=elapsed,
                model_name=model_name,
                sections=sections,
                actual_prompt_tokens=actual_prompt,
                actual_completion_tokens=actual_completion
            )
            
            final_content = ""
            if response_msg.tool_calls:
                messages.append(response_msg)
                for tool_call in response_msg.tool_calls:
                    if tool_call.function.name == "calculate_on_level_premiums":
                        args = json.loads(tool_call.function.arguments)
                        rc_list = args.get("rate_changes", [])
                        
                        triangle = session.get('triangle')
                        if not triangle or not triangle.premiums:
                            tool_result = "Error: No premium data available in the current dataset to on-level."
                        else:
                            try:
                                import pandas as pd
                                from reserving.core.on_level import OnLevelPremiumCalculator
                                prem_data = [{"accident_year": int(ay), "earned_premium": float(p)} for ay, p in triangle.premiums.items()]
                                calc = OnLevelPremiumCalculator(pd.DataFrame(prem_data), pd.DataFrame(rc_list))
                                on_level_df = calc.calculate()
                                tool_result = on_level_df.to_json(orient="records")
                            except Exception as e:
                                tool_result = f"Error computing on-level premiums: {str(e)}"
                                
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": tool_result
                        })
                
                start_time = time.perf_counter()
                final_response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.5,
                    timeout=timeout_val
                )
                elapsed_final = time.perf_counter() - start_time
                final_content = final_response.choices[0].message.content
                
                actual_prompt_final = None
                actual_completion_final = None
                if hasattr(final_response, 'usage') and final_response.usage:
                    actual_prompt_final = getattr(final_response.usage, 'prompt_tokens', None)
                    actual_completion_final = getattr(final_response.usage, 'completion_tokens', None)
                    
                _log_instrumentation_call(
                    agent_name="ChatAgent_ToolResolution",
                    sys_inst=sys_inst,
                    prompt=chat_prompt + f"\n[Tool Result]: {tool_result}",
                    response_content=final_content,
                    elapsed=elapsed_final,
                    model_name=model_name,
                    sections=sections,
                    actual_prompt_tokens=actual_prompt_final,
                    actual_completion_tokens=actual_completion_final
                )
            else:
                final_content = response_msg.content or ""
                
            # Update session conversational state
            session['last_intent'] = chat_req.intent.value
            if chat_req.methods:
                session['last_method'] = chat_req.methods
            if chat_req.basis:
                session['last_basis'] = chat_req.basis
            if chat_req.columns:
                session['last_columns'] = chat_req.columns
            if "accident_year" in chat_req.entities:
                session['last_accident_year'] = chat_req.entities["accident_year"]
            if session.get('results'):
                session['last_result'] = session.get('results')
                
            return final_content
        except Exception as e:
            return f"Chat Agent Error: {str(e)}"
