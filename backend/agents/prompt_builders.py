import json
import re
from enum import Enum

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

class ChatIntent(str, Enum):
    UNKNOWN = "UNKNOWN"
    CONCEPTUAL = "CONCEPTUAL"
    COLUMN_INFO = "COLUMN_INFO"
    DATA_EXPLORATION = "DATA_EXPLORATION"
    CALCULATION = "CALCULATION"
    METHOD_EXPLANATION = "METHOD_EXPLANATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    RECOMMENDATION = "RECOMMENDATION"
    COMPARISON = "COMPARISON"
    REPORT = "REPORT"

class ChatRequest:
    def __init__(
        self,
        intent: ChatIntent,
        methods: list = None,
        basis: str = None,
        columns: list = None,
        comparison: bool = False,
        recommendation: bool = False,
        message: str = "",
        entities: dict = None
    ):
        self.intent = intent
        self.methods = methods or []
        self.basis = basis  # "paid", "incurred", "both", or None
        self.columns = columns or []
        self.comparison = comparison
        self.recommendation = recommendation
        self.message = message
        self.entities = entities or {}

class ChatClassifier:
    @staticmethod
    def classify(message: str, parsed_req: dict) -> ChatRequest:
        msg_lower = message.lower().strip()
        
        # Extract intent from parsed_req
        parsed_intent = parsed_req.get("intent", "ACTUARIAL_KNOWLEDGE")
        
        # Reserving methods & basis
        methods = parsed_req.get("methods") or []
        basis = parsed_req.get("basis")
        
        # Flags
        comparison = parsed_req.get("comparison", False)
        recommendation = parsed_req.get("recommendation", False)
        
        # Entities dictionary
        entities = {}
        
        # Extract accident year from message (e.g. "for 1997", "accident year 1995", "1994 reserve")
        ay_match = re.search(r'\b(19\d{2}|20\d{2})\b', msg_lower)
        if ay_match:
            entities["accident_year"] = int(ay_match.group(1))
            
        # Extract number/parameter to identify if it is unknown
        num_matches = re.findall(r'\b\d+\b', msg_lower)
        # Exclude years from numeric parameters
        non_year_nums = [n for n in num_matches if not (n.startswith("19") or n.startswith("20")) or len(n) != 4]
        if non_year_nums:
            entities["numeric_parameter"] = non_year_nums[0]
            
        # Extract columns mentioned in message
        columns = []
        # Check standard columns
        for col_name in ["accidentyear", "developmentlag", "cumpaidloss_c", "earnedpremnet_c", "postedreserve97_c", "bulkloss_c"]:
            if col_name in msg_lower:
                columns.append(col_name)
        
        # Map parsed_req intent to ChatIntent
        intent = ChatIntent.CONCEPTUAL
        
        is_conceptual_query = any(w in msg_lower for w in ["what is", "explain", "definition", "meaning of", "define", "concept"])
        has_specific_reserving_entities = (
            len(methods) > 0 or 
            bool(basis) or 
            "accident_year" in entities or 
            any(w in msg_lower for w in ["calculate", "compute", "run", "triangle", "method", "estimate", "results"])
        )
        
        # Check unknown triggers:
        if parsed_intent == "OUT_OF_SCOPE":
            intent = ChatIntent.UNKNOWN
        elif comparison or "compare" in msg_lower or "vs" in msg_lower:
            intent = ChatIntent.COMPARISON
        elif recommendation or "recommend" in msg_lower or "best estimate" in msg_lower:
            intent = ChatIntent.RECOMMENDATION
        elif "report" in msg_lower or "summary" in msg_lower or "summarise" in msg_lower:
            intent = ChatIntent.REPORT
        elif "diagnostic" in msg_lower or "outlier" in msg_lower or "stability" in msg_lower or "suitability" in msg_lower:
            intent = ChatIntent.DIAGNOSTIC
        elif (any(m in msg_lower for m in ["chain ladder", "chainladder", "mack", "bf", "bornhuetter", "cape cod", "benktander", "clark"]) or methods) and is_conceptual_query:
            intent = ChatIntent.METHOD_EXPLANATION
        elif is_conceptual_query and not has_specific_reserving_entities:
            intent = ChatIntent.CONCEPTUAL
        elif parsed_intent == "DATASET_QUERY" or any(k in msg_lower for k in ["row", "column", "variable", "shape", "dimension", "size", "record", "header", "field"]):
            # Differentiate COLUMN_INFO vs DATA_EXPLORATION
            if any(k in msg_lower for k in ["column", "variable", "field", "schema", "header"]):
                intent = ChatIntent.COLUMN_INFO
            else:
                intent = ChatIntent.DATA_EXPLORATION
        elif parsed_intent == "CALCULATION_QUERY" or len(methods) > 0 or bool(basis) or "accident_year" in entities or "reserve" in msg_lower or "ultimate" in msg_lower or "ibnr" in msg_lower:
            intent = ChatIntent.CALCULATION
            
        if columns:
            entities["columns"] = columns
            
        return ChatRequest(
            intent=intent,
            methods=methods,
            basis=basis,
            columns=columns,
            comparison=comparison,
            recommendation=recommendation,
            message=message,
            entities=entities
        )

class ContextBuilder:
    @staticmethod
    def build(session_data: dict, chat_req: ChatRequest) -> dict:
        intent = chat_req.intent
        
        # Priority-Based Context Assembly dictionaries
        context_items = {
            1: {}, # Priority 1 (Highest)
            2: {}, # Priority 2 (High)
            3: {}, # Priority 3 (Medium)
            4: {}  # Priority 4 (Low)
        }
        
        # Always include basic session properties (Priority 1)
        context_items[1]["n_years"] = session_data.get('n_years')
        if chat_req.basis:
            context_items[1]["requested_basis"] = chat_req.basis
            
        results_val = session_data.get('results') or {}
        
        if intent == ChatIntent.CONCEPTUAL:
            pass
            
        elif intent == ChatIntent.METHOD_EXPLANATION:
            methods_list = chat_req.methods if chat_req.methods else ["CL", "MCL", "BF", "CC", "BK", "CLK", "ELR"]
            metadata = {}
            for m in methods_list:
                m_upper = m.upper()
                if m_upper == "CL":
                    metadata["Chain Ladder (CL)"] = {
                        "description": "Projects future claims by multiplying cumulative paid or incurred losses by loss development factors.",
                        "assumptions": "Historical development patterns will continue into the future.",
                        "inputs": "Cumulative loss triangle.",
                        "outputs": "Ultimate losses, IBNR, and Reserve.",
                        "limitations": "Highly sensitive to outliers and assumes stable reporting/settlement patterns."
                    }
                elif m_upper == "MCL":
                    metadata["Mack Chain Ladder (MCL)"] = {
                        "description": "A distribution-free formula to estimate the standard error of the Chain Ladder ultimate loss projections.",
                        "assumptions": "Claims in different accident years are independent; variance of future development is proportional to the previous loss.",
                        "inputs": "Cumulative loss triangle.",
                        "outputs": "Ultimate losses, IBNR, parameter/process error, standard error of reserves.",
                        "limitations": "Subject to the same structural limitations as Chain Ladder, requires positive cumulative values."
                    }
                elif m_upper == "BF":
                    metadata["Bornhuetter-Ferguson (BF)"] = {
                        "description": "Estimates IBNR by multiplying an a priori expected loss ratio (ELR) by the earned premium and the percentage of claims unpaid/unreported.",
                        "assumptions": "Unreported losses develop according to the prior expected loss ratio, independent of actual claims to date.",
                        "inputs": "Premium, prior expected loss ratio (ELR), loss development pattern.",
                        "outputs": "IBNR, Ultimate losses, Reserve.",
                        "limitations": "Dependent on the accuracy of the a priori ELR assumption."
                    }
                elif m_upper == "CC":
                    metadata["Cape Cod (CC)"] = {
                        "description": "A Bornhuetter-Ferguson derivative where the expected loss ratio is estimated directly from the historical experience of all accident years combined.",
                        "assumptions": "Expected losses are proportional to exposure (earned premium), and the overall ELR across years is stable.",
                        "inputs": "Premium/exposure, cumulative loss triangle, LDFs.",
                        "outputs": "IBNR, Ultimate losses, Reserve.",
                        "limitations": "Assumes a stable base ELR; less suitable if exposures are changing significantly."
                    }
                elif m_upper == "BK":
                    metadata["Benktander (BK)"] = {
                        "description": "An iterative method that blends the Chain Ladder and Bornhuetter-Ferguson methods, acting as a credibility-weighted average.",
                        "assumptions": "Prior estimates can be updated iteratively to form a more stable estimate than CL.",
                        "inputs": "Premium, expected loss ratio, loss development pattern.",
                        "outputs": "Ultimate losses, IBNR.",
                        "limitations": "Computationally more complex; depends on initial ELR quality."
                    }
            context_items[3]["methods_metadata"] = metadata
            
        elif intent == ChatIntent.COLUMN_INFO:
            context_items[2]["original_columns"] = session_data.get('summary', {}).get('original_columns', [])
            if chat_req.columns:
                context_items[1]["requested_columns"] = chat_req.columns
                
        elif intent == ChatIntent.DATA_EXPLORATION:
            df = session_data.get('df')
            if df is not None:
                context_items[2]["dataset_summary"] = {
                    "shape": f"{df.shape[0]} rows by {df.shape[1]} columns",
                    "columns": list(df.columns),
                    "missing_values_count": int(df.isnull().sum().sum())
                }
            summary = session_data.get('summary') or {}
            if summary.get('entities'):
                context_items[2]["entities_present"] = summary.get('entities')
                
        elif intent == ChatIntent.CALCULATION:
            methods_out = results_val.get('methods') or []
            min_methods = []
            for m in methods_out:
                if m.get("status") == "success":
                    code = m.get("code")
                    base_code = code.split('_')[0].upper()
                    if chat_req.methods and base_code not in [meth.upper() for meth in chat_req.methods]:
                        continue
                    min_methods.append({
                        "code": code,
                        "name": m.get("name"),
                        "ultimate": m.get("ultimate"),
                        "ibnr": m.get("ibnr"),
                        "loss_ratio": m.get("loss_ratio"),
                        "reserve": m.get("reserve")
                    })
            context_items[1]["methods_summary"] = min_methods
            
            context_items[1]["overall_results"] = {
                "selected_method": results_val.get('selected_method', 'CL'),
                "best_estimate": results_val.get('best_estimate', 0.0),
                "total_ibnr": session_data.get('totalIBNR', 0.0)
            }
            if "accident_year" in chat_req.entities:
                context_items[1]["target_accident_year"] = chat_req.entities["accident_year"]
                
        elif intent == ChatIntent.DIAGNOSTIC:
            diag_analysis = session_data.get('diagnostics_analysis') or {}
            metrics = diag_analysis.get('metrics') or {}
            overall = metrics.get('overall') or {}
            ldf_stability = metrics.get('ldf_stability') or {}
            
            context_items[3]["diagnostics"] = {
                "n_accident_years": overall.get("n_accident_years"),
                "n_dev_periods": overall.get("n_dev_periods"),
                "average_ldf_cov": ldf_stability.get("average_cov"),
                "ldf_suitability_indicator": ldf_stability.get("cl_suitable_indicator"),
                "data_quality_assessment": diag_analysis.get('llm_analysis', {}).get('data_quality_assessment', 'Standard')
            }
            if session_data.get('ldfs'):
                context_items[4]["ldfs_curve"] = session_data.get('ldfs')
            if session_data.get('cdfs'):
                context_items[4]["cdfs_curve"] = session_data.get('cdfs')
                
        elif intent == ChatIntent.RECOMMENDATION:
            rec_val = session_data.get('recommendation') or {}
            context_items[2]["recommendation"] = {
                "recommended_method": rec_val.get("recommended_method"),
                "confidence": rec_val.get("confidence"),
                "reasoning": rec_val.get("reasoning", [])[:3],
                "cautions": rec_val.get("cautions", [])[:3]
            }
            diag_analysis = session_data.get('diagnostics_analysis') or {}
            metrics = diag_analysis.get('metrics') or {}
            overall = metrics.get('overall') or {}
            context_items[3]["diagnostics_summary"] = {
                "n_accident_years": overall.get("n_accident_years"),
                "n_dev_periods": overall.get("n_dev_periods"),
                "total_paid": overall.get("total_paid")
            }
            
        elif intent == ChatIntent.COMPARISON:
            methods_out = results_val.get('methods') or []
            min_methods = []
            for m in methods_out:
                if m.get("status") == "success":
                    code = m.get("code")
                    base_code = code.split('_')[0].upper()
                    if chat_req.methods and base_code not in [meth.upper() for meth in chat_req.methods]:
                        continue
                    min_methods.append({
                        "code": code,
                        "name": m.get("name"),
                        "ultimate": m.get("ultimate"),
                        "ibnr": m.get("ibnr"),
                        "reserve": m.get("reserve")
                    })
            context_items[1]["methods_compared"] = min_methods
            
            context_items[2]["comparison_summary"] = {
                "selected_method": results_val.get('selected_method', 'CL'),
                "best_estimate": results_val.get('best_estimate', 0.0)
            }
            
        elif intent == ChatIntent.REPORT:
            context_items[2]["report_summary"] = {
                "selected_method": results_val.get('selected_method', 'CL'),
                "best_estimate": results_val.get('best_estimate', 0.0),
                "total_ibnr": session_data.get('totalIBNR', 0.0)
            }
            rec_val = session_data.get('recommendation') or {}
            context_items[2]["recommendation"] = {
                "recommended_method": rec_val.get("recommended_method"),
                "confidence": rec_val.get("confidence")
            }
            
        assembled_context = {}
        for p in [1, 2, 3, 4]:
            assembled_context.update(context_items[p])
            
        context_str = json.dumps(assembled_context)
        if len(context_str) > 3000:
            for key in context_items[4].keys():
                assembled_context.pop(key, None)
            context_str = json.dumps(assembled_context)
            
            if len(context_str) > 3000:
                for key in context_items[3].keys():
                    assembled_context.pop(key, None)
                context_str = json.dumps(assembled_context)
                
                if len(context_str) > 3000:
                    for key in context_items[2].keys():
                        assembled_context.pop(key, None)
                        
        return assembled_context

class ChatPromptBuilder:
    """Builds and renders prompts for ChatAgent in supervisor.py."""
    
    @staticmethod
    def render(context: dict, intent: ChatIntent) -> tuple[str, dict]:
        context_json = json.dumps(context)
        
        sys_inst = (
            "You are the Actuarial AI Assistant, an experienced senior actuarial consultant.\n"
            "You are having a professional conversation with another actuary.\n\n"
            f"Current Query Intent: {intent.value}\n"
            f"Context Data (JSON): {context_json}\n\n"
            "Core Decision Tree Workflow:\n"
            "1. Do I understand the user's request? If not, enter Clarification Mode.\n"
            "2. Do I have enough information? If not, enter Clarification Mode.\n"
            "3. Does the answer depend on uploaded data? If yes, answer using the current session context.\n"
            "4. Does the answer depend on execution results? If yes, use the current session results.\n"
            "5. Otherwise answer using actuarial knowledge.\n\n"
            "Clarification Mode Rules:\n"
            "- Trigger Clarification Mode whenever a required parameter (e.g. reserving method, column name, accident year, paid vs incurred basis) is missing or ambiguous.\n"
            "- Never guess or fabricate missing information. Never pretend to know.\n"
            "- Ask exactly one targeted clarification question.\n"
            "- Suggest selectable options (e.g., bullet lists using '•') to guide the user.\n"
            "- Do not continue reasoning or provide a guess after entering Clarification Mode. Stop immediately and wait.\n\n"
            "Confidence Gates:\n"
            "- Never state uncertain information as fact.\n"
            "- If information cannot be verified, state that it is an inference, explain what is known, and what cannot be confirmed. (e.g. 'postedreserve97_c likely represents a posted reserve recorded during the 1997 valuation, but the dataset itself doesn't explicitly define it').\n\n"
            "Actuarial Accuracy Rule:\n"
            "- Use the definitions implemented by the application:\n"
            "  • Reserve = Ultimate - Paid\n"
            "  • IBNR = Ultimate - Reported\n"
            "If actuarial literature differs, explain and use the application's definitions instead of replacing them.\n\n"
            "Response Style & Formatting:\n"
            "- Be conversational. Keep answers concise by default (approx. 3–6 sentences).\n"
            "- Avoid raw prompt markdown artifacts (e.g., repeating formatting or JSON structures).\n"
            "- Avoid report-style headings or section titles unless explicitly requested.\n"
            "- Never restate information the user already knows (e.g. 'You uploaded...') unless necessary.\n"
            "- Allow lists (numbered or bulleted), selective bold text for readability, and simple tables (only when comparing multiple methods).\n\n"
            "Adaptive Response Templates:\n"
            "- Conceptual: Short explanation + why it matters + small practical example.\n"
            "- Dataset/Column: Direct answer + small markdown table (if helpful) + suggested follow-up questions.\n"
            "- Calculation: Direct result + key numbers + one-sentence interpretation.\n"
            "- Comparison: Compact comparison table + takeaway.\n\n"
            "Be conversational, senior, concise, and actuarially precise."
        )
        
        sections = {
            "system_actuary_role": "You are the Actuarial AI Assistant...",
            "context_variables": context_json
        }
        
        return sys_inst, sections
