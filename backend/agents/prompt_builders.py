import json

class DiagnosticsPromptBuilder:
    """Builds and renders prompts for DiagnosticsAgent."""
    
    @staticmethod
    def build_context(overall: dict, ldf_diag: list, loss_ratios: list, dq_status: str) -> dict:
        # Pass only minimal overall statistics to keep it small
        min_overall = {
            "total_paid": overall.get("total_paid"),
            "total_premium": overall.get("total_premium"),
            "overall_paid_lr_pct": overall.get("overall_paid_lr_pct"),
            "n_accident_years": overall.get("n_accident_years"),
            "n_dev_periods": overall.get("n_dev_periods"),
            "has_premium": overall.get("has_premium"),
            "is_long_tail": overall.get("is_long_tail"),
        }
        
        # Take only the first 5 LDF diagnostics transitions
        min_ldf_diag = []
        for r in ldf_diag[:5]:
            min_ldf_diag.append({
                "fromAge": r.get("fromAge"),
                "toAge": r.get("toAge"),
                "volumeWeighted": r.get("volumeWeighted"),
                "straightAvg": r.get("straightAvg"),
                "cov_pct": r.get("cov_pct"),
                "stability": r.get("stability")
            })
            
        # Keep loss ratios minimal
        min_loss_ratios = []
        for lr in loss_ratios:
            min_loss_ratios.append({
                "ay": lr.get("ay"),
                "premium": lr.get("premium"),
                "paid": lr.get("paid"),
                "ultimate_lr_pct": lr.get("ultimate_lr_pct")
            })
            
        return {
            "overall": min_overall,
            "ldf_diag_subset": min_ldf_diag,
            "loss_ratios": min_loss_ratios,
            "data_quality_status": dq_status
        }
        
    @staticmethod
    def render(context: dict) -> tuple[str, str, dict]:
        sys_inst = (
            "You are an expert actuarial diagnostics agent. Your task is to analyze loss reserving data "
            "and provide professional reasoning for data quality, reporting patterns, LDF stability, "
            "outliers, and maturity. Do not perform any actuarial calculations yourself. "
            "Provide your findings in strict JSON format with the following keys:\n"
            "1. 'data_quality_assessment': evaluation of the data completeness and quality.\n"
            "2. 'reporting_pattern_diagnostics': description of how reporting patterns develop over time.\n"
            "3. 'ldf_stability_assessment': evaluation of LDF stability (reference COV, straight avg vs weighted).\n"
            "4. 'outlier_detection': identification of any anomalous accident years or cells.\n"
            "5. 'maturity_assessment': assessment of the triangle's overall maturity.\n"
            "Respond ONLY with the raw JSON string. Do not include markdown formatting."
        )
        
        overall_str = json.dumps(context["overall"])
        ldfs_str = json.dumps(context["ldf_diag_subset"])
        loss_ratios_str = json.dumps(context["loss_ratios"])
        dq_str = context["data_quality_status"]
        
        prompt = (
            f"Actuarial Metrics Summary:\n"
            f"Overall Statistics: {overall_str}\n"
            f"LDF Diagnostics (first few): {ldfs_str}\n"
            f"Loss Ratios by Accident Year: {loss_ratios_str}\n"
            f"Data Quality Status: {dq_str}\n\n"
            "Based on these metrics, provide the assessments requested in the JSON schema."
        )
        
        sections = {
            "overall_statistics": overall_str,
            "ldf_diagnostics": ldfs_str,
            "loss_ratios": loss_ratios_str,
            "data_quality_status": dq_str
        }
        
        return sys_inst, prompt, sections


class ComparisonPromptBuilder:
    """Builds and renders prompts for ComparisonAgent."""
    
    @staticmethod
    def build_context(median_ultimate: float, median_ibnr: float, comparison_table: list, differences: dict) -> dict:
        # Keep comparison table fields clean
        min_table = []
        for c in comparison_table:
            min_table.append({
                "code": c.get("code"),
                "name": c.get("name"),
                "ultimate": c.get("ultimate"),
                "ibnr": c.get("ibnr"),
                "loss_ratio": c.get("loss_ratio")
            })
            
        # Clean differences
        min_diffs = {}
        for code, diff in differences.items():
            min_diffs[code] = {
                "ultimate_pct_diff_vs_median": diff.get("ultimate_pct_diff_vs_median"),
                "ibnr_pct_diff_vs_median": diff.get("ibnr_pct_diff_vs_median")
            }
            
        return {
            "median_ultimate": median_ultimate,
            "median_ibnr": median_ibnr,
            "comparison_table": min_table,
            "differences": min_diffs
        }
        
    @staticmethod
    def render(context: dict) -> tuple[str, str, dict]:
        sys_inst = (
            "You are an expert actuarial comparison analyst. Your job is to compare reserving indications "
            "across different methods (e.g., Bornhuetter-Ferguson, Chain Ladder, Benktander, Cape Cod) "
            "and explain why they differ. Focus on: structural differences (BF uses an a priori ELR and does "
            "not react to early claims; CL is highly sensitive to recent claims; Benktander is a blend). "
            "Be actuarially precise and concise. Do not make up calculations."
        )
        
        table_str = json.dumps(context["comparison_table"])
        diffs_str = json.dumps(context["differences"])
        med_ult = context["median_ultimate"]
        med_ibnr = context["median_ibnr"]
        
        prompt = (
            f"Reserving Indications Comparison:\n"
            f"Median Ultimate: {med_ult:,.2f} | Median IBNR: {med_ibnr:,.2f}\n"
            f"Methods Table: {table_str}\n"
            f"Differences Table: {diffs_str}\n\n"
            "Explain why these methods differ, and how their varying sensitivities to assumptions (e.g. prior ELR, LDFs) explain the differences."
        )
        
        sections = {
            "median_statistics": f"Median Ultimate: {med_ult} | Median IBNR: {med_ibnr}",
            "comparison_table": table_str,
            "differences_table": diffs_str
        }
        
        return sys_inst, prompt, sections


class RecommendationPromptBuilder:
    """Builds and renders prompts for RecommendationAgent."""
    
    @staticmethod
    def build_context(
        suitability: dict,
        reporting_pattern: dict,
        ldf_stability: dict,
        calendar_effects: dict,
        tail_analysis: dict,
        outliers: dict,
        comparison_table: list,
        differences: dict
    ) -> dict:
        # 1. Suitability Scores (out of 100) & pros/cons summaries
        scores = suitability.get("scores", {})
        pros = suitability.get("pros", {})
        cons = suitability.get("cons", {})
        
        # 2. Key Diagnostic summaries (extract only high level variables)
        avg_ay_rmse = 0.0
        ay_fits = reporting_pattern.get("accident_year_fits", [])
        if ay_fits:
            avg_ay_rmse = sum(item.get("rmse", 0.0) for item in ay_fits if item.get("rmse", 0.0) > 0) / len(ay_fits)
            
        diag_summary = {
            "reporting_pattern": {
                "best_fit_curve": reporting_pattern.get("best_fit_curve"),
                "r2": reporting_pattern.get("fit_metrics", {}).get("r2"),
                "avg_ay_rmse": round(avg_ay_rmse, 4),
                "consistency": reporting_pattern.get("reporting_consistency")
            },
            "ldf_stability": {
                "average_cov": ldf_stability.get("average_cov"),
                "unstable_periods_count": len(ldf_stability.get("unstable_periods", [])),
                "indicator": ldf_stability.get("cl_suitable_indicator")
            },
            "calendar_effects": {
                "trend_detected": calendar_effects.get("trend_detected"),
                "trend_direction": calendar_effects.get("trend_direction"),
                "slope": calendar_effects.get("slope"),
                "anomalies_count": len(calendar_effects.get("anomalies", []))
            },
            "tail_analysis": {
                "sensitivity_high_vs_selected_pct": tail_analysis.get("sensitivity", {}).get("high_vs_selected_pct"),
                "selected_vs_no_tail_pct": tail_analysis.get("sensitivity", {}).get("selected_vs_no_tail_pct"),
                "materiality": tail_analysis.get("tail_uncertainty_materiality")
            },
            "outliers": {
                "outlier_count": len(outliers.get("cell_outliers", []))
            }
        }
        
        # 3. Reserving table and differences
        min_table = []
        for c in comparison_table:
            min_table.append({
                "code": c.get("code"),
                "ultimate": c.get("ultimate"),
                "ibnr": c.get("ibnr"),
                "loss_ratio": c.get("loss_ratio")
            })
            
        min_diffs = {}
        for code, diff in differences.items():
            min_diffs[code] = {
                "ultimate_pct_diff_vs_median": diff.get("ultimate_pct_diff_vs_median")
            }
            
        return {
            "suitability_scores": scores,
            "pros": pros,
            "cons": cons,
            "diagnostics": diag_summary,
            "comparison_table": min_table,
            "differences": min_diffs
        }
        
    @staticmethod
    def render(context: dict) -> tuple[str, str, dict]:
        sys_inst = (
            "You are an expert actuarial AI Reserving Recommender. You analyze loss reserving outputs "
            "across multiple methods along with data diagnostics, comparison results, and deterministic method suitability scores. "
            "Your task is to recommend the most appropriate reserving method for the best estimate. "
            "Your recommendation must align with the deterministic suitability scores provided (higher is better). "
            "Explain the recommendation qualitatively using the diagnostics; do not invent actuarial reasoning. "
            "Provide your recommendation in strict JSON format containing these fields:\n"
            "1. 'recommended_method': The code of the method (e.g. 'BK', 'BF', 'CL', 'MCL', 'CC', 'CLK', 'CO', 'ELR')\n"
            "2. 'confidence': The confidence level ('High', 'Medium', 'Low')\n"
            "3. 'reasoning': An array of strings explaining the selection qualitatively based on diagnostics. Do not exceed 4 reasons.\n"
            "4. 'assumptions_used': summary of assumptions used (e.g. volume-weighted LDFs, tail factor, ELR).\n"
            "5. 'cautions': array of strings with any warnings or cautions from the diagnostic checks.\n"
            "6. 'alternative_methods': array of alternative methods that were highly scored but not selected.\n"
            "Respond ONLY with the raw JSON string. Do not include markdown code block formatting."
        )
        
        scores_str = json.dumps(context["suitability_scores"])
        pros_cons = json.dumps({"pros": context["pros"], "cons": context["cons"]})
        diag_str = json.dumps(context["diagnostics"])
        table_str = json.dumps(context["comparison_table"])
        diffs_str = json.dumps(context["differences"])
        
        prompt = (
            f"Deterministic Method Suitability Scores (out of 100): {scores_str}\n"
            f"Method Pros/Cons: {pros_cons}\n"
            f"Diagnostics Summary: {diag_str}\n"
            f"Reserving Indications (results summary): {table_str}\n"
            f"Reserving Differences: {diffs_str}\n\n"
            "Recommend the best method and return the JSON payload. Ensure the recommended method is one of the available codes (e.g. CL, MCL, BF, CC, BK, CLK, CO, ELR)."
        )
        
        sections = {
            "suitability_scores": scores_str,
            "pros_and_cons": pros_cons,
            "diagnostics_summary": diag_str,
            "reserving_table": table_str,
            "reserving_differences": diffs_str
        }
        
        return sys_inst, prompt, sections


class ReportingPromptBuilder:
    """Builds and renders prompts for ReportingAgent."""
    
    @staticmethod
    def build_context(diagnostics_summary: dict, reserving_outputs: dict, comparison_table: list, differences: dict, comparison_explanation: str, recommendation: dict) -> dict:
        # Keep comparison explanation condensed (limit length to prevent massive token usage)
        condensed_comp_exp = comparison_explanation[:2000] + "\n[Truncated for brevity]" if len(comparison_explanation) > 2000 else comparison_explanation
        
        # Diagnostics details summarized
        dq = diagnostics_summary.get("llm_analysis", {}).get("data_quality_assessment", "Standard Data Quality.")
        
        metrics = diagnostics_summary.get("metrics", {})
        overall = metrics.get("overall", {})
        ldf_stability = metrics.get("ldf_stability", {})
        calendar_effects = metrics.get("calendar_effects", {})
        tail_analysis = metrics.get("tail_analysis", {})
        outliers = metrics.get("outliers", {})
        
        compact_diag = {
            "data_quality": dq,
            "overall_dimensions": {
                "n_accident_years": overall.get("n_accident_years"),
                "n_dev_periods": overall.get("n_dev_periods"),
                "total_paid": overall.get("total_paid"),
                "total_premium": overall.get("total_premium")
            },
            "ldf_stability": {
                "average_cov": ldf_stability.get("average_cov"),
                "indicator": ldf_stability.get("cl_suitable_indicator")
            },
            "calendar_effects": {
                "trend_detected": calendar_effects.get("trend_detected"),
                "anomalies": calendar_effects.get("anomalies")
            },
            "tail_analysis": {
                "selected_tail": tail_analysis.get("selected_tail"),
                "sensitivity_pct": tail_analysis.get("sensitivity", {}).get("high_vs_selected_pct"),
                "materiality": tail_analysis.get("tail_uncertainty_materiality")
            },
            "outliers_count": len(outliers.get("cell_outliers", []))
        }
        
        min_table = []
        for c in comparison_table:
            min_table.append({
                "code": c.get("code"),
                "name": c.get("name"),
                "ultimate": c.get("ultimate"),
                "ibnr": c.get("ibnr"),
                "loss_ratio": c.get("loss_ratio"),
                "reserve": c.get("reserve")
            })
            
        return {
            "diagnostics": compact_diag,
            "comparison_explanation": condensed_comp_exp,
            "comparison_table": min_table,
            "differences": differences,
            "recommendation": recommendation,
            "best_estimate": reserving_outputs.get("best_estimate")
        }
        
    @staticmethod
    def render(context: dict) -> tuple[str, str, dict]:
        sys_inst = (
            "You are an expert actuarial reporting agent. Your task is to compile a formal, professional "
            "actuarial report in Markdown format. The report should be comprehensive and suitable for PDF generation later. "
            "Your output must contain these five distinct sections:\n"
            "1. Executive Summary\n"
            "2. Actuarial Report (Methodology, indications, and differences explanation)\n"
            "3. Assumption Summary (tail factors, LDFs, ELR, and negative IBNR configurations)\n"
            "4. Diagnostics Summary (data quality, outliers, stability, maturity)\n"
            "5. Recommendation Summary (method, confidence, reasoning, cautions, and alternatives)\n\n"
            "Use formal professional actuarial language. Do not invent calculations. Represent all figures cleanly."
        )
        
        diag_str = json.dumps(context["diagnostics"])
        table_str = json.dumps(context["comparison_table"])
        diffs_str = json.dumps(context["differences"])
        rec_str = json.dumps(context["recommendation"])
        explanation_str = context["comparison_explanation"]
        best_est = context["best_estimate"]
        
        prompt = (
            f"Diagnostics Summary: {diag_str}\n"
            f"Comparison Table: {table_str}\n"
            f"Differences vs Median: {diffs_str}\n"
            f"Actuarial Method Differences Explanation: {explanation_str}\n"
            f"Best Estimate Ultimate: {best_est}\n"
            f"Recommendation: {rec_str}\n\n"
            "Compile the complete Markdown actuarial report."
        )
        
        sections = {
            "diagnostics_summary": diag_str,
            "comparison_table": table_str,
            "reserving_differences": diffs_str,
            "comparison_narrative": explanation_str,
            "recommendation_details": rec_str
        }
        
        return sys_inst, prompt, sections


class ChatPromptBuilder:
    """Builds and renders prompts for ChatAgent in supervisor.py."""
    
    @staticmethod
    def build_context(session_data: dict) -> dict:
        results_val = session_data.get('results') or {}
        min_results = {
            "selected_method": results_val.get('selected_method', 'CL'),
            "best_estimate": results_val.get('best_estimate', 0.0),
            "total_ibnr": session_data.get('totalIBNR', 0.0)
        }
        
        # Condensed summary of mathematical results
        min_methods = []
        methods_out = results_val.get('methods') or []
        for m in methods_out:
            if m.get("status") == "success":
                min_methods.append({
                    "code": m.get("code"),
                    "name": m.get("name"),
                    "ultimate": m.get("ultimate"),
                    "ibnr": m.get("ibnr"),
                    "loss_ratio": m.get("loss_ratio")
                })
                
        # Condensed diagnostic indicators (instead of raw JSON dump)
        diag_analysis = session_data.get('diagnostics_analysis') or {}
        metrics = diag_analysis.get('metrics') or {}
        overall = metrics.get('overall') or {}
        ldf_stability = metrics.get('ldf_stability') or {}
        
        min_diagnostics = {
            "n_accident_years": overall.get("n_accident_years"),
            "n_dev_periods": overall.get("n_dev_periods"),
            "total_paid": overall.get("total_paid"),
            "average_ldf_cov": ldf_stability.get("average_cov"),
            "ldf_suitability_indicator": ldf_stability.get("cl_suitable_indicator"),
            "diagnostics_text_assessment": diag_analysis.get('llm_analysis', {}).get('data_quality_assessment', 'Standard')
        }
        
        # Selected recommendation parameters
        rec_val = session_data.get('recommendation') or {}
        min_recommendation = {
            "recommended_method": rec_val.get("recommended_method"),
            "confidence": rec_val.get("confidence"),
            "reasoning": rec_val.get("reasoning", [])[:3],  # top 3 reasons
            "cautions": rec_val.get("cautions", [])[:3]      # top 3 cautions
        }
        
        return {
            "n_years": session_data.get('n_years'),
            "results": min_results,
            "methods_summary": min_methods,
            "diagnostics": min_diagnostics,
            "recommendation": min_recommendation,
            "execution_report": session_data.get('report_markdown', 'No report compiled.'),
            "ldfs_curve": session_data.get('ldfs'),
            "cdfs_curve": session_data.get('cdfs')
        }
        
    @staticmethod
    def render(context: dict) -> tuple[str, dict]:
        context_json = json.dumps({
            "n_years": context["n_years"],
            "results": context["results"],
            "methods_summary": context["methods_summary"],
            "diagnostics": context["diagnostics"],
            "recommendation": context["recommendation"],
            "ldfs_curve": context["ldfs_curve"],
            "cdfs_curve": context["cdfs_curve"]
        })
        
        sys_inst = (
            "You are the Analysis Chat Agent, an expert actuary. You have studied the book 'Estimating Unpaid Claims "
            "Using Basic Techniques' by Jacqueline Friedland in immense detail.\n\n"
            f"Context Data:\n{context_json}\n\n"
            f"Actuarial Execution Report (Markdown):\n{context['execution_report']}\n\n"
            "Rules:\n"
            "1. If asked about diagnostics, provide a detailed report analyzing the curves of loss ratios, development ratios, and settlement rates using the context objects. Reference Friedland's methodologies explicitly.\n"
            "2. For Curve Fitting, explain the mathematical fit for Pareto, Weibull, and Loglogistic distributions using the tail factors.\n"
            "3. Provide a detailed analysis of the Paid-to-Incurred ratio triangle to detect Case Reserve adequacy trends.\n"
            "4. Provide a detailed report of Settlement Rates (Closed vs Reported claims).\n"
            "5. Explain your chosen Tail Factor using the execution report.\n"
            "6. If asked to on-level premiums, use tool 'calculate_on_level_premiums'.\n"
            "Be concise and actuarially precise."
        )
        
        sections = {
            "system_actuary_role": "You are the Analysis Chat Agent...",
            "context_variables": context_json,
            "actuarial_execution_report": context["execution_report"]
        }
        
        return sys_inst, sections
