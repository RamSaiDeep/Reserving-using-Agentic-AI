import copy
from reserving.schemas.reserving import ExecuteRequest
from reserving.services import ReservingEngine

class BaseStage:
    """Abstract base class for all pipeline orchestration stages."""
    @property
    def deps(self) -> list:
        return []
        
    def run(self, session_id: str, session: dict, plan: dict, trace: list) -> None:
        raise NotImplementedError()

class DatasetStage(BaseStage):
    """Verifies that the dataset CSV has been uploaded."""
    @property
    def deps(self) -> list:
        return []
        
    def run(self, session_id: str, session: dict, plan: dict, trace: list) -> None:
        if not session.get('csv_text'):
            raise ValueError(
                "Please upload a reserving dataset (CSV) in the dashboard before asking questions about your data or reserve calculations."
            )
        if "✓ Dataset found" not in trace:
            trace.append("✓ Dataset found")

class PreprocessingStage(BaseStage):
    """Ingests dataset, checks data quality, builds triangle and calculates LDFs."""
    @property
    def deps(self) -> list:
        return ["dataset"]
        
    def run(self, session_id: str, session: dict, plan: dict, trace: list) -> None:
        if not session.get('triangle'):
            from agent_workflow import ingest_csv, perform_data_quality_checks, build_loss_triangle, calculate_ldfs
            ingest_csv(session_id)
            perform_data_quality_checks(session_id)
            build_loss_triangle(session_id)
            calculate_ldfs(session_id)
            trace.append("✓ Triangle and LDFs prepared from raw dataset")
        else:
            if "✓ Triangle already prepared" not in trace:
                trace.append("✓ Triangle already prepared")

class ResultsStage(BaseStage):
    """Executes necessary deterministic reserving methods on demand and caches them."""
    @property
    def deps(self) -> list:
        return ["preprocessing"]
        
    def run(self, session_id: str, session: dict, plan: dict, trace: list) -> None:
        if not plan["need_results"]:
            return
            
        if "results_by_method" not in session:
            session["results_by_method"] = {}
            
        req_basis = plan["basis"] or session.get("data_source", "paid") or "paid"
        
        # Decide which methods to run
        requested_methods = plan["methods_required"]
        if not requested_methods:
            if plan.get("explicit_all", False) or plan["intent"] == "RECOMMENDATION_QUERY":
                # Run all standard models if explicitly requested or recommendation/best method asked
                requested_methods = ["CL", "MCL", "BF", "CC", "BK", "ELR", "CLK"]
            else:
                # Default to Chain Ladder only if no specific method is requested and the user did not request all methods
                requested_methods = ["CL"]
            
        method_executed = False
        for code in requested_methods:
            cached_res = session["results_by_method"].get(code)
            # Re-run if not in cache or if user explicitly requested a different basis than what was cached
            needs_run = (
                not cached_res or 
                cached_res.get("status") != "success" or 
                cached_res.get("source", "").lower() != req_basis.lower()
            )
            
            if needs_run:
                trace.append(f"Running {code} model on {req_basis} basis...")
                req = ExecuteRequest(
                    session_id=session_id,
                    method_code=code,
                    data_source=req_basis
                )
                res = ReservingEngine.execute_single_model(req)
                session["results_by_method"][code] = res
                method_executed = True
            else:
                if f"✓ {code} results pulled from cache" not in trace:
                    trace.append(f"✓ {code} results pulled from cache")
                    
        # Recompile the global session["results"] structure to maintain UI compatibility
        methods_list = []
        for c, r in session["results_by_method"].items():
            methods_list.append(r)
            
        # Determine recommended method
        rec_code = "CL"
        if rec_code not in session["results_by_method"] or session["results_by_method"][rec_code].get("status") != "success":
            success_codes = [c for c, r in session["results_by_method"].items() if r.get("status") == "success"]
            if success_codes:
                rec_code = success_codes[0]
                
        rec_model = session["results_by_method"].get(rec_code)
        best_estimate_val = rec_model.get("ultimate", 0.0) if rec_model else 0.0
        
        session['results'] = {
            "paid_ldfs": session.get('ldfs'),
            "incurred_ldfs": session.get('incurred_ldfs'),
            "best_estimate": best_estimate_val,
            "selected_method": rec_code,
            "methods": methods_list
        }
        session['totalIBNR'] = rec_model.get("ibnr", 0.0) if rec_model else 0.0
        session['totalUlt'] = best_estimate_val
        session['total_ibnr'] = session['totalIBNR']
        session['total_ultimate'] = session['totalUlt']
        session['data_source'] = req_basis
        
        if method_executed:
            trace.append("✓ Calculated reserves successfully")

class RecommendationStage(BaseStage):
    """Compiles comparative analysis and recommendation reports based on active cached results."""
    @property
    def deps(self) -> list:
        return ["results"]
        
    def run(self, session_id: str, session: dict, plan: dict, trace: list) -> None:
        if not plan["need_recommendation"]:
            return
            
        if not session.get('recommendation'):
            trace.append("Generating recommendation...")
            
            # Map only available and successful methods in results_by_method cache
            results_by_method = session.get("results_by_method", {})
            results_summary_for_ai = []
            for code, m in results_by_method.items():
                if m.get("status") == "success":
                    results_summary_for_ai.append({
                        "code": m.get("code") or code,
                        "name": m.get("name") or m.get("method"),
                        "status": "success",
                        "ibnr": m.get("ibnr", 0.0),
                        "ultimate": m.get("ultimate", 0.0),
                        "loss_ratio": m.get("loss_ratio", 0.0),
                        "maturity_score": m.get("maturity_score", 0.0),
                        "reserve_to_case_ratio": m.get("reserve_to_case_ratio", 0.0)
                    })
                    
            from agents.supervisor import SupervisorAgent
            supervisor = SupervisorAgent()
            supervisor.generate_recommendation_and_report(session_id, session, results_summary_for_ai)
            trace.append("✓ Recommendation and report compiled successfully")
        else:
            if "✓ Recommendation and report pulled from cache" not in trace:
                trace.append("✓ Recommendation and report pulled from cache")

class StageManager:
    """Dependency-based stage orchestrator."""
    def __init__(self):
        self.stages = {
            "dataset": DatasetStage(),
            "preprocessing": PreprocessingStage(),
            "results": ResultsStage(),
            "recommendation": RecommendationStage()
        }
        
    def ensure_stage(self, stage_name: str, plan: dict, session_id: str, session: dict, trace: list, visited=None) -> None:
        if visited is None:
            visited = set()
            
        if stage_name in visited:
            return
            
        stage = self.stages.get(stage_name)
        if not stage:
            return
            
        # DFS resolution
        for dep in stage.deps:
            self.ensure_stage(dep, plan, session_id, session, trace, visited)
            
        stage.run(session_id, session, plan, trace)
        visited.add(stage_name)
