import copy
import concurrent.futures
import numpy as np
import uuid
import datetime
from typing import Dict, Any, List, Optional

from reserving.methods import METHODS
from reserving.schemas.reserving import ExecuteRequest, MethodConfig
from reserving.core.tools import compute_suggested_elr
from reserving.core.standardizer import standardize_method_output
import agent_workflow

class ReservingEngine:
    @staticmethod
    def execute_models(req: ExecuteRequest) -> Dict[str, Any]:
        """
        Orchestrates model execution, parameter default resolutions,
        tail factor adjustments, parallel run executions, results standardization,
        and diagnostic suggestions.
        """
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Invalid session_id"}
        
        if req.api_key: session['api_key'] = req.api_key
        if req.base_url: session['base_url'] = req.base_url
        if req.model_name: session['model_name'] = req.model_name

        # Enforce AI settings availability
        api_key = req.api_key or session.get('api_key')
        model_name = req.model_name or session.get('model_name')
        
        # Prepare base triangle copy
        t_eval_base = copy.deepcopy(session['triangle'])
        
        # Determine configs
        configs = req.configs
        if not configs:
            configs = {}
            for code, MethodClass in METHODS.items():
                run_p = True
                run_i = True
                if MethodClass.requires_paid_triangle and not MethodClass.requires_incurred_triangle:
                    run_i = False
                elif MethodClass.requires_incurred_triangle and not MethodClass.requires_paid_triangle:
                    run_p = False
                configs[code] = MethodConfig(
                    enabled=True,
                    run_paid=run_p,
                    run_incurred=run_i
                )

        paid_ldfs_to_use = req.paid_ldfs if req.paid_ldfs is not None else (req.custom_ldfs if req.custom_ldfs is not None else [])
        incurred_ldfs_to_use = req.incurred_ldfs if req.incurred_ldfs is not None else (req.custom_incurred_ldfs if req.custom_incurred_ldfs is not None else [])

        # Fallback to calculated LDFs from session if empty
        if not paid_ldfs_to_use and session.get('ldfs'):
            raw_ldfs = session.get('ldfs')
            if isinstance(raw_ldfs, list) and len(raw_ldfs) > 0 and isinstance(raw_ldfs[0], dict):
                paid_ldfs_to_use = [float(x.get('volumeWeighted', 1.0) or 1.0) for x in raw_ldfs]
            else:
                paid_ldfs_to_use = raw_ldfs
        if not incurred_ldfs_to_use and session.get('incurred_ldfs'):
            raw_inc_ldfs = session.get('incurred_ldfs')
            if isinstance(raw_inc_ldfs, list) and len(raw_inc_ldfs) > 0 and isinstance(raw_inc_ldfs[0], dict):
                incurred_ldfs_to_use = [float(x.get('volumeWeighted', 1.0) or 1.0) for x in raw_inc_ldfs]
            else:
                incurred_ldfs_to_use = raw_inc_ldfs

        # Precompute suggested ELRs once to avoid redundant execution in thread pool
        mature_thresh = req.mature_cdf_threshold if req.mature_cdf_threshold is not None else 1.05
        suggested_elr_paid = compute_suggested_elr(t_eval_base, "paid", mature_thresh) or 65.0
        suggested_elr_incurred = compute_suggested_elr(t_eval_base, "incurred", mature_thresh) or 65.0

        # Define single method execution runner for a specific source
        def run_method_for_source(code, MethodClass, source_val):
            try:
                # determine result_id, source_label, name_label
                if source_val == "both":
                    result_id = code
                    source_label = "Paid + Incurred"
                    name_label = MethodClass.label
                else:
                    result_id = f"{code}_{source_val.upper()}"
                    source_label = source_val.capitalize()
                    name_label = f"{MethodClass.label} ({source_label})"

                method_config = configs.get(code)
                if not method_config:
                    return {
                        "result_id": result_id,
                        "method": MethodClass.label,
                        "source": source_label,
                        "status": "disabled",
                        "reason": "Method not configured",
                        "assumptions": {},
                        "results": [],
                        "error": None,
                        "code": result_id,
                        "name": name_label,
                        "ultimate": 0.0,
                        "ibnr": 0.0
                    }
                
                # Check availability (premium-dependent methods)
                if MethodClass.needs_premium and not t_eval_base.premiums:
                    return {
                        "result_id": result_id,
                        "method": MethodClass.label,
                        "source": source_label,
                        "status": "disabled",
                        "reason": "Missing Earned Premium",
                        "assumptions": {},
                        "results": [],
                        "error": "Method requires Premium data, which is missing.",
                        "code": result_id,
                        "name": name_label,
                        "ultimate": 0.0,
                        "ibnr": 0.0
                    }

                model = MethodClass()
                t_eval = copy.deepcopy(t_eval_base)

                # Determine explicit matrix and LDFs based on source
                if source_val == "incurred":
                    matrix_to_use = t_eval_base.incurred_matrix
                    ldfs_for_run = copy.deepcopy(incurred_ldfs_to_use)
                    tail_to_use = req.incurred_tail_factor
                    ldf_basis_name = "incurred"
                elif source_val == "paid":
                    matrix_to_use = t_eval_base.matrix
                    ldfs_for_run = copy.deepcopy(paid_ldfs_to_use)
                    tail_to_use = req.paid_tail_factor
                    ldf_basis_name = "paid"
                else: # both (requires both paid and incurred)
                    matrix_to_use = t_eval_base.matrix
                    ldfs_for_run = copy.deepcopy(paid_ldfs_to_use)
                    tail_to_use = req.paid_tail_factor
                    ldf_basis_name = "both"

                # Apply tail factor if last factor is 1.0 (or default tail factor)
                if ldfs_for_run and ldfs_for_run[-1] == 1.0:
                    ldfs_for_run[-1] = tail_to_use

                # Derive defaults or use config parameters
                suggested_elr_pct = suggested_elr_incurred if source_val == "incurred" else suggested_elr_paid
                
                legacy_comp = req.legacy_compatibility
                if method_config and method_config.legacy_compatibility is not None:
                    legacy_comp = method_config.legacy_compatibility
                if legacy_comp is None:
                    legacy_comp = True
                    
                allow_neg = req.allow_negative_ibnr
                if method_config and method_config.allow_negative_ibnr is not None:
                    allow_neg = method_config.allow_negative_ibnr
                if allow_neg is None:
                    allow_neg = False
                
                params = {
                    'legacy_compatibility': legacy_comp,
                    'allow_negative_ibnr': allow_neg
                }
                assumptions = {
                    "source": source_label,
                    "ldf_basis": ldf_basis_name,
                    "tail_factor": float(tail_to_use),
                    "allow_negative_ibnr": allow_neg,
                    "legacy_compatibility": legacy_comp
                }

                if code == 'BF':
                    val = method_config.aprioriLossRatio if method_config.aprioriLossRatio is not None else suggested_elr_pct
                    params['aprioriLossRatio'] = val
                    assumptions['aprioriLossRatio'] = float(val) / 100.0
                elif code == 'BK':
                    val = method_config.aprioriLossRatio if method_config.aprioriLossRatio is not None else suggested_elr_pct
                    params['aprioriLossRatio'] = val
                    params['iterations'] = method_config.iterations if method_config.iterations is not None else 2
                    assumptions['aprioriLossRatio'] = float(val) / 100.0
                    assumptions['iterations'] = int(params['iterations'])
                elif code == 'CC':
                    val = method_config.aprioriLossRatio if method_config.aprioriLossRatio is not None else suggested_elr_pct
                    params['aprioriLossRatio'] = val
                    assumptions['aprioriLossRatio'] = float(val) / 100.0
                    params['decay'] = method_config.decay if method_config.decay is not None else 1.0
                    assumptions['decay'] = float(params['decay'])
                elif code == 'ELR':
                    val = method_config.aprioriLossRatio if method_config.aprioriLossRatio is not None else suggested_elr_pct
                    params['aprioriLossRatio'] = val
                    assumptions['apriori_loss_ratio'] = float(val) / 100.0
                elif code == 'CLK':
                    params['curveType'] = method_config.curveType if method_config.curveType is not None else 'weibull'
                    assumptions['curveType'] = params['curveType']
                elif code == 'FS':
                    params['approach'] = method_config.approach if method_config.approach is not None else 'approach1'
                    params['inflationRate'] = method_config.inflationRate if method_config.inflationRate is not None else 3.0
                    assumptions['approach'] = params['approach']
                    assumptions['inflationRate'] = float(params['inflationRate'])

                # FIT model using EXPLICIT matrix argument (zero triangle.matrix swap/mutation!)
                model.fit(t_eval, params, ldfs_for_run, matrix=matrix_to_use)
                
                # Standardize outputs using the standardizer
                std_out = standardize_method_output(
                    code=code,
                    label=MethodClass.label,
                    source_val=source_val,
                    t_eval=t_eval_base,
                    model=model,
                    configs=configs
                )
                return std_out
            except Exception as e:
                if source_val == "both":
                    result_id = code
                    source_label = "Paid + Incurred"
                    name_label = MethodClass.label
                else:
                    result_id = f"{code}_{source_val.upper()}"
                    source_label = source_val.capitalize()
                    name_label = f"{MethodClass.label} ({source_label})"
                return {
                    "result_id": result_id,
                    "method": MethodClass.label,
                    "source": source_label,
                    "status": "error",
                    "reason": str(e),
                    "assumptions": {},
                    "results": [],
                    "error": str(e),
                    "code": result_id,
                    "name": name_label,
                    "ultimate": 0.0,
                    "ibnr": 0.0
                }

        # Build execution tasks list
        global_source = req.data_source or "paid"
        tasks_to_run = []
        for code, MethodClass in METHODS.items():
            method_config = configs.get(code)
            if not method_config:
                continue
                
            if not method_config.enabled:
                if MethodClass.supports_source_selection:
                    tasks_to_run.append((code, MethodClass, global_source, True))
                else:
                    tasks_to_run.append((code, MethodClass, "both", True))
                continue
                
            if MethodClass.supports_source_selection:
                is_disabled_for_source = False
                if global_source == "paid" and method_config.run_paid is False:
                    is_disabled_for_source = True
                elif global_source == "incurred" and method_config.run_incurred is False:
                    is_disabled_for_source = True
                tasks_to_run.append((code, MethodClass, global_source, is_disabled_for_source))
            else:
                tasks_to_run.append((code, MethodClass, "both", False))

        # Run concurrent executions
        methods_out = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {}
            for code, MethodClass, source_val, is_disabled in tasks_to_run:
                # result_id and labeling for disabled runs
                if source_val == "both":
                    result_id = code
                    source_label = "Paid + Incurred"
                    name_label = MethodClass.label
                else:
                    result_id = f"{code}_{source_val.upper()}"
                    source_label = source_val.capitalize()
                    name_label = f"{MethodClass.label} ({source_label})"

                if is_disabled:
                    methods_out.append({
                        "result_id": result_id,
                        "method": MethodClass.label,
                        "source": source_label,
                        "status": "disabled",
                        "reason": "Disabled by user",
                        "assumptions": {},
                        "results": [],
                        "error": None,
                        "code": result_id,
                        "name": name_label,
                        "ultimate": 0.0,
                        "ibnr": 0.0
                    })
                else:
                    futures[executor.submit(run_method_for_source, code, MethodClass, source_val)] = (code, source_val)
                    
            for future in concurrent.futures.as_completed(futures):
                methods_out.append(future.result())

        # Difference from Median Ultimate (excluding unsuccessful / disabled runs)
        successful_runs = [m for m in methods_out if m["status"] == "success"]
        successful_ultimates = [m["ultimate"] for m in successful_runs]
        if successful_ultimates:
            median_ultimate = float(np.median(successful_ultimates))
            for m in methods_out:
                if m["status"] == "success":
                    m["diff_from_median"] = (m["ultimate"] - median_ultimate) / median_ultimate if median_ultimate > 0 else 0.0
                else:
                    m["diff_from_median"] = 0.0
        else:
            median_ultimate = 0.0
            for m in methods_out:
                m["diff_from_median"] = 0.0

        methods_out.sort(key=lambda x: x["result_id"])

        # Reserve Recommendation Agent
        results_summary_for_ai = [
            {
                "code": m["code"],
                "name": m["name"],
                "status": m["status"],
                "ibnr": m.get("ibnr", 0.0),
                "ultimate": m.get("ultimate", 0.0),
                "loss_ratio": m.get("loss_ratio", 0.0),
                "maturity_score": m.get("maturity_score", 0.0),
                "reserve_to_case_ratio": m.get("reserve_to_case_ratio", 0.0)
            } for m in methods_out if m["status"] == "success"
        ]
        
        session['api_key'] = req.api_key or session.get('api_key')
        session['base_url'] = req.base_url or session.get('base_url')
        session['model_name'] = req.model_name or session.get('model_name')
        
        ai_recommendation = agent_workflow.run_reserve_recommendation_agent(req.session_id, results_summary_for_ai)
        
        rec_code = ai_recommendation.get("recommended_method", "CL")
        rec_model = next((m for m in methods_out if m["code"] == rec_code and m["status"] == "success"), None)
        best_estimate_val = rec_model["ultimate"] if rec_model else (median_ultimate if median_ultimate > 0 else 0.0)
        
        run_id = str(uuid.uuid4())
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        selected_methods = [code for code, cfg in configs.items() if cfg.enabled]

        session['results'] = {
            "run_id": run_id,
            "timestamp": timestamp,
            "selected_methods": selected_methods,
            "paid_ldfs": paid_ldfs_to_use,
            "incurred_ldfs": incurred_ldfs_to_use,
            "paid_tail_factor": req.paid_tail_factor,
            "incurred_tail_factor": req.incurred_tail_factor,
            "configs": {k: v.dict() if hasattr(v, 'dict') else v for k, v in configs.items()},
            "best_estimate": best_estimate_val,
            "selected_method": rec_code,
            "ai_recommendation": ai_recommendation,
            "methods": methods_out
        }
        
        return {
            "success": True,
            "run_id": run_id,
            "timestamp": timestamp,
            "selected_methods": selected_methods,
            "paid_ldfs": paid_ldfs_to_use,
            "incurred_ldfs": incurred_ldfs_to_use,
            "paid_tail_factor": req.paid_tail_factor,
            "incurred_tail_factor": req.incurred_tail_factor,
            "configs": configs,
            "summary": {
                "best_estimate": best_estimate_val,
                "selected_method": rec_code
            },
            "ai_recommendation": ai_recommendation,
            "methods": methods_out
        }
