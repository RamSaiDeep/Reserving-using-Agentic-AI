import json
from agents.diagnostics_agent import DiagnosticsAgent
from agents.reserving_agent import ReservingAgent
from agents.comparison_agent import ComparisonAgent
from agents.recommendation_agent import RecommendationAgent
from agents.reporting_agent import ReportingAgent
from agents.utils import run_agent

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

        # 1. Run DiagnosticsAgent (computes advanced diagnostics)
        diag_agent = DiagnosticsAgent(api_key, base_url, model_name)
        diagnostics = diag_agent.analyze(triangle, df)
        session['diagnostics_analysis'] = diagnostics
        
        metrics = diagnostics.get("metrics", {})
        overall = metrics.get("overall", {})
        
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
        ldf_stab = metrics.get("ldf_stability", {})
        avg_cov = ldf_stab.get("average_cov", 0.0)
        if ldf_stab.get("cl_suitable_indicator") == "Unstable" or avg_cov > 0.12:
            supervisor_cautions.append("High LDF volatility detected (avg CoV > 0.12). Prioritized Mack Chain Ladder to quantify reserve uncertainty; recommend comparing against Bornhuetter-Ferguson (BF) for stability.")
            
        # C. If premium is unavailable: skip Cape Cod and ELR
        has_premium = overall.get("has_premium", False)
        if not has_premium:
            results_summary = [r for r in results_summary if r.get("code") not in ["BF", "BK", "CC", "ELR"]]
            
        # D. If reporting pattern fit is poor: warn user and lower confidence
        rep_pattern = metrics.get("reporting_pattern", {})
        fit_metrics = rep_pattern.get("fit_metrics", {})
        r2 = fit_metrics.get("r2", 1.0)
        if r2 < 0.60:
            supervisor_cautions.append("Poor reporting pattern growth curve fit (R2 < 0.60). Reduced confidence in development-based methods.")

        # 2. ReservingAgent outputs
        results_val = session.get('results') or {}
        reserving_outputs = {
            "selected_method": results_val.get('method', 'CL') if isinstance(results_val, dict) else 'CL',
            "best_estimate": results_val.get('totalUlt', 0.0) if isinstance(results_val, dict) else 0.0,
            "methods": results_summary
        }

        # 3. Run ComparisonAgent
        comp_agent = ComparisonAgent(api_key, base_url, model_name)
        comparison = comp_agent.compare(results_summary)
        session['comparison'] = comparison

        # 4. Run RecommendationAgent
        rec_agent = RecommendationAgent(api_key, base_url, model_name)
        recommendation = rec_agent.recommend(diagnostics, reserving_outputs, comparison)
        
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

        # 5. Run ReportingAgent
        rep_agent = ReportingAgent(api_key, base_url, model_name)
        report = rep_agent.generate_report(diagnostics, reserving_outputs, comparison, recommendation)
        session['report_markdown'] = report.get('report_markdown')
        session['report'] = report.get('report_markdown')

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

    def run_parallel_chat(self, session_id: str, session: dict, message: str, history: list) -> str:
        """Delegates chat queries to the LLM, enriching context with all agent outputs."""
        api_key = session.get('api_key')
        base_url = session.get('base_url')
        model_name = session.get('model_name')
        
        try:
            from reserving.diagnostics import compute_diagnostics
            t = session.get('triangle')
            diag_metrics = compute_diagnostics(t) if t else {}
            
            # Prune large matrices to save tokens
            if 'ratio_triangles' in diag_metrics:
                for key in ['paid_to_incurred', 'settlement_rate']:
                    matrix = diag_metrics['ratio_triangles'].get(key, [])
                    if matrix and isinstance(matrix, list) and len(matrix) > 0 and isinstance(matrix[0], list):
                        cols = len(matrix[0])
                        avgs = []
                        for c in range(cols):
                            col_vals = [matrix[r][c] for r in range(len(matrix)) if c < len(matrix[r]) and matrix[r][c] is not None]
                            avgs.append(round(sum(col_vals)/len(col_vals), 3) if col_vals else None)
                        diag_metrics['ratio_triangles'][key] = {"average_by_development_age": avgs, "note": "Full matrix compressed to save tokens."}
        except Exception:
            diag_metrics = {}
            
        context = {
            'n_years': session.get('n_years'),
            'summary': session.get('summary'),
            'results': session.get('results'),
            'ldfs_curve': session.get('ldfs'),
            'cdfs_curve': session.get('cdfs'),
            'development_ages_months': session.get('dev_ages'),
            'total_ibnr': session.get('totalIBNR'),
            'execution_report': session.get('report'),
            'diagnostics': diag_metrics,
            'multi_agent_diagnostics': session.get('diagnostics_analysis'),
            'multi_agent_comparison': session.get('comparison'),
            'multi_agent_recommendation': session.get('recommendation')
        }
        
        sys_inst = f"""You are the Analysis Chat Agent, an expert actuary. You have studied the book 'Estimating Unpaid Claims Using Basic Techniques' by Jacqueline Friedland in immense detail.
Context: {json.dumps(context)}
Rules:
1. If asked about diagnostics, provide a detailed report analyzing the curves of loss ratios, development ratios, and settlement rates using the 'diagnostics' object. Reference Friedland's methodologies explicitly.
2. For Curve Fitting, explain the mathematical fit for Pareto, Weibull, and Loglogistic distributions using the tail factors.
3. Provide a detailed analysis of the Paid-to-Incurred ratio triangle to detect Case Reserve adequacy trends.
4. Provide a detailed report of Settlement Rates (Closed vs Reported claims).
5. Explain your chosen Tail Factor using the execution_report.
6. If asked to on-level premiums, use tool 'calculate_on_level_premiums'.
Be concise and actuarially precise."""

        messages = [{"role": "system", "content": sys_inst}]
        for msg in history:
            role = 'user' if msg['role'] == 'user' else 'assistant'
            messages.append({"role": role, "content": msg['text']})
        messages.append({"role": "user", "content": message})
        
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
        
        from openai import OpenAI
        import openai
        
        try:
            client = OpenAI(
                api_key=api_key, 
                base_url=base_url if base_url else None,
                default_headers={"ngrok-skip-browser-warning": "true"}
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                temperature=0.5
            )
            
            response_msg = response.choices[0].message
            
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
                
                final_response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.5
                )
                return final_response.choices[0].message.content
            else:
                return response_msg.content
        except Exception as e:
            return f"Chat Agent Error: {str(e)}"
