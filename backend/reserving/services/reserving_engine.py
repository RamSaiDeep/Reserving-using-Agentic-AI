import copy
import concurrent.futures
import numpy as np
import uuid
import datetime
import json
from typing import Dict, Any, List, Optional

from reserving.methods import METHODS
from reserving.schemas.reserving import ExecuteRequest, MethodConfig
from reserving.core.tools import compute_suggested_elr
from reserving.core.standardizer import standardize_method_output
import agent_workflow

class ReservingEngine:
    @staticmethod
    def _on_level_premiums(t_eval, rate_changes):
        """Adjusts premiums in t_eval to current rate levels using on-level factors."""
        if rate_changes and t_eval.premiums:
            import pandas as pd
            from reserving.core.on_level import OnLevelPremiumCalculator
            prem_data = [{"accident_year": int(ay), "earned_premium": float(p)} for ay, p in t_eval.premiums.items()]
            calc = OnLevelPremiumCalculator(pd.DataFrame(prem_data), pd.DataFrame(rate_changes))
            on_level_df = calc.calculate()
            t_eval.premiums = dict(zip(on_level_df["accident_year"], on_level_df["on_level_premium"]))

    @staticmethod
    def _resolve_tail_factor(ldfs_to_use, t_eval, tail_factor_input):
        """Resolves the tail factor, computing it dynamically if 1.0 or not provided."""
        from reserving.core.tools import compute_tail_factor
        tail_result = compute_tail_factor(ldfs_to_use, t_eval)
        chosen_tail = tail_result["chosen"]
        chosen_reason = tail_result["reason"]
        
        # If user explicitly passed a tail factor that is not 1.0 (or if custom LDFs has manual tail), prioritize it
        if ldfs_to_use and ldfs_to_use[-1] != 1.0:
            chosen_tail = ldfs_to_use[-1]
            chosen_reason = f"User Manual Override ({chosen_tail})"
        elif tail_factor_input is not None and tail_factor_input != 1.0:
            chosen_tail = tail_factor_input
            chosen_reason = f"User Manual Override ({chosen_tail})"
            
        return chosen_tail, chosen_reason

    @staticmethod
    def execute_single_model(req: ExecuteRequest) -> Dict[str, Any]:
        """
        Executes a single reserving method, handling on-level premiums, tail factor calculation,
        mathematical model fitting, standardized outputs, diagnostics, and narration.
        """
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Invalid session_id"}
        
        if req.api_key: session['api_key'] = req.api_key
        if req.base_url: session['base_url'] = req.base_url
        if req.model_name: session['model_name'] = req.model_name
        
        from reserving.core.tools import (get_environment_sensitivity, compute_ibnr_table,
                                           compute_loss_ratios, suggest_elr,
                                           compute_ldf_stability)
                                           
        MethodClass = METHODS.get(req.method_code)
        if not MethodClass:
            return {"success": False, "error": "Invalid method code"}
            
        if MethodClass.needs_premium and not session['triangle'].premiums:
            error_msg = (f"Data Input Insufficient: The {MethodClass.label} model requires "
                         f"Premium data, which was not found in your dataset. Please choose a different model.")
            session['report'] = error_msg
            return {"success": True, "results": [], "totalIBNR": 0, "totalUlt": 0, "totalPaid": 0, "narration": error_msg}

        t_eval = copy.deepcopy(session['triangle'])
        
        # 1. On-Level Premium
        ReservingEngine._on_level_premiums(t_eval, req.rate_changes)
        
        # 2. Determine LDFs and matrix based on Selected Data Source
        data_source = req.data_source or "paid"
        if not MethodClass.supports_source_selection:
            data_source = "both"
        
        ldfs_to_use = copy.deepcopy(req.custom_ldfs) if req.custom_ldfs is not None else []
        if data_source == "incurred":
            matrix_to_use = t_eval.incurred_matrix
            ldf_basis_name = "incurred"
            tail_input = req.incurred_tail_factor
            if req.custom_incurred_ldfs:
                ldfs_to_use = copy.deepcopy(req.custom_incurred_ldfs)
        elif data_source == "paid":
            matrix_to_use = t_eval.matrix
            ldf_basis_name = "paid"
            tail_input = req.paid_tail_factor
        else: # both
            matrix_to_use = t_eval.matrix
            ldf_basis_name = "both"
            tail_input = req.paid_tail_factor
            
        # Fallback to calculated LDFs from session if empty
        if not ldfs_to_use:
            raw_ldfs = session.get('incurred_ldfs' if data_source == "incurred" else 'ldfs')
            if raw_ldfs:
                if isinstance(raw_ldfs, list) and len(raw_ldfs) > 0 and isinstance(raw_ldfs[0], dict):
                    ldfs_to_use = [float(x.get('volumeWeighted', 1.0) or 1.0) for x in raw_ldfs]
                else:
                    ldfs_to_use = copy.deepcopy(raw_ldfs)
                    
        # 3. Resolve Tail Factor
        chosen_tail, chosen_reason = ReservingEngine._resolve_tail_factor(ldfs_to_use, t_eval, tail_input)
        if ldfs_to_use:
            ldfs_to_use[-1] = chosen_tail
        else:
            ldfs_to_use = [chosen_tail]

        # 4. Run Model fitting using EXPLICIT matrix argument (never swap/mutate t_eval.matrix!)
        model = MethodClass()
        # Resolve default parameters if not provided in req.params
        params = copy.deepcopy(req.params) if req.params is not None else {}
        mature_thresh = req.mature_cdf_threshold if req.mature_cdf_threshold is not None else 1.05
        suggested_elr_val = compute_suggested_elr(t_eval, data_source, mature_thresh) or 65.0
        
        if req.method_code == 'BF':
            if 'aprioriLossRatio' not in params or params['aprioriLossRatio'] is None:
                params['aprioriLossRatio'] = suggested_elr_val
        elif req.method_code == 'BK':
            if 'aprioriLossRatio' not in params or params['aprioriLossRatio'] is None:
                params['aprioriLossRatio'] = suggested_elr_val
            if 'iterations' not in params or params['iterations'] is None:
                params['iterations'] = 2
        elif req.method_code == 'CC':
            if 'aprioriLossRatio' not in params or params['aprioriLossRatio'] is None:
                params['aprioriLossRatio'] = suggested_elr_val
            if 'decay' not in params or params['decay'] is None:
                params['decay'] = 1.0
        elif req.method_code == 'ELR':
            if 'aprioriLossRatio' not in params or params['aprioriLossRatio'] is None:
                params['aprioriLossRatio'] = suggested_elr_val
        elif req.method_code == 'CLK':
            if 'curveType' not in params or params['curveType'] is None:
                params['curveType'] = 'weibull'
        elif req.method_code == 'FS':
            if 'approach' not in params or params['approach'] is None:
                params['approach'] = 'approach1'
            if 'inflationRate' not in params or params['inflationRate'] is None:
                params['inflationRate'] = 3.0
        
        # Inject standard parameters
        legacy_comp = req.legacy_compatibility
        if legacy_comp is None:
            legacy_comp = True
        allow_neg = req.allow_negative_ibnr
        if allow_neg is None:
            allow_neg = False
            
        params['legacy_compatibility'] = legacy_comp
        params['allow_negative_ibnr'] = allow_neg
        
        # Fit model
        model.fit(t_eval, params, ldfs_to_use, matrix=matrix_to_use)
        
        diag       = [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0) for row in matrix_to_use]
        total_paid = sum(v for v in diag if v is not None)
        
        # 5. Compute helper metrics
        ibnr_table = compute_ibnr_table(t_eval, model, ldfs_to_use)
        loss_ratios = compute_loss_ratios(t_eval, ibnr_table) if t_eval.premiums else []
        elr_suggestion = suggest_elr(t_eval)
        ldf_stability  = compute_ldf_stability(t_eval)
        env_sensitivity = get_environment_sensitivity(req.method_code)
        
        # PROCESS descriptions
        PROCESS_EXPLANATIONS = {
            "CL":  "Chain Ladder projects ultimate claims by multiplying the latest paid diagonal by Cumulative Development Factors (CDFs) derived from historical age-to-age LDFs. IBNR = Ultimate − Paid.",
            "MCL": "Mack Chain Ladder calculates identical ultimates to CL but additionally computes sigma-squared variance for each column, producing standard errors and confidence intervals (75th/95th percentile) around the IBNR estimate.",
            "BF":  "Bornhuetter-Ferguson splits the IBNR into (a) expected unreported claims = Expected Ultimate × (1 − 1/CDF), plus (b) actual paid to date. Expected Ultimate = Premium × A Priori ELR.",
            "CC":  "Cape Cod derives the ELR automatically from actual data: ELR = Σ(Reported Claims) / Σ(Used-Up Premium). Used-Up Premium = Earned Premium × % Reported (1/CDF). IBNR is then computed identically to BF.",
            "BK":  "Benktander iteratively refines the BF estimate: BF Ultimate is fed back as the new A Priori, and IBNR is recomputed. Each iteration shifts credibility from BF toward Chain Ladder proportional to % reported.",
            "CO":  "Case Outstanding method sets IBNR = total case reserves currently held by adjusters. It assumes zero future newly-reported claims. Reserve = Incurred − Paid = Case Reserves.",
            "CLK": "Clark Stochastic fits a continuous growth curve (Log-Logistic or Weibull) to the paid triangle using maximum likelihood. Stabilised CDFs from the curve are applied to project ultimates with a distribution of outcomes.",
            "FS":  "Frequency-Severity Method implements Chapter 11 techniques, projecting ultimate claims count and ultimate average severity separately (or using disposal and frequency rates) to compute reserves."
        }
        
        inputs_txt = f"Data used: {len(t_eval.accident_years)} accident years, evaluated to {max(t_eval.dev_ages)} months."
        if t_eval.premiums:
            inputs_txt += " Premium data was included."
            
        process_txt = PROCESS_EXPLANATIONS.get(req.method_code, "")
        output_txt = f"The model projected a Total IBNR of {round(model.get_total_ibnr(), 0):,.0f} and a Total Ultimate of {round(model.get_total_ultimate(), 0):,.0f}."
        
        ldf_txt = "LDFs were mathematically computed. "
        if ldf_stability:
            ldf_txt += f"Overall stability is based on {len(ldf_stability)} development periods. "
            
        impact_txt = "Premium and exposure changes directly scale the A Priori ELR and Expected Ultimates in this model." if t_eval.premiums else "No premium or exposure data used in this model."
        if req.method_code in ['CL', 'MCL', 'CO', 'CLK']:
            impact_txt = "This method relies purely on historical development patterns, meaning premium/exposure changes do not impact the projection."
            
        parsed = {
            "inputs": inputs_txt,
            "process": process_txt,
            "output_text": output_txt,
            "ldf_analysis": ldf_txt,
            "tail_factor_selection": f"Selected tail factor: {chosen_reason}.",
            "impact": impact_txt,
            "environment_sensitivity": env_sensitivity,
            "output_numbers": {"Total IBNR": round(model.get_total_ibnr(), 0), "Total Ultimate": round(model.get_total_ultimate(), 0)},
            "loss_ratios": loss_ratios,
            "suggested_elr": elr_suggestion
        }
        final_msg = json.dumps(parsed)
        session['report'] = final_msg
        
        # 6. Call standardize_method_output
        cdfs_curve = t_eval.compute_cdfs(ldfs_to_use)
        
        # Construct config mapping for standardizer
        configs = {req.method_code: req}
        
        std_out = standardize_method_output(
            code=req.method_code,
            label=MethodClass.label,
            source_val=data_source,
            t_eval=t_eval,
            model=model,
            configs=configs
        )
        
        volatility = getattr(model, 'volatility', 0.0)
        
        # Write to session
        session['results'] = std_out['results']
        session['total_ultimate'] = std_out['ultimate']
        session['total_ibnr'] = std_out['ibnr']
        session['volatility'] = volatility
        session['cdfs']      = cdfs_curve
        if data_source == "incurred":
            session['incurred_ldfs'] = ldfs_to_use
        else:
            session['ldfs'] = ldfs_to_use
        session['dev_ages']  = t_eval.dev_ages
        session['totalIBNR'] = std_out['ibnr']
        session['totalUlt']  = std_out['ultimate']
        session['data_source'] = data_source
        
        # Store diagnostics for Analysis Agent
        session['loss_ratios'] = loss_ratios
        session['suggested_elr'] = elr_suggestion
        session['ldf_stability'] = ldf_stability
        session['ratio_triangles'] = getattr(model, 'ratio_triangles', None)
        session['curve_fitting_results'] = getattr(model, 'curve_fitting_results', None)
        
        return {
            "success":   True,
            "results":   std_out['results'],
            "totalIBNR": std_out['ibnr'],
            "totalUlt":  std_out['ultimate'],
            "totalPaid": std_out['paid'],
            "narration": final_msg,
            "cdfs":      cdfs_curve,
            "ldfs":      ldfs_to_use,
            "dev_ages":  t_eval.dev_ages,
            "loss_ratios":   loss_ratios,
            "suggested_elr": elr_suggestion,
            "ldf_stability": ldf_stability,
            "volatility":    volatility,
            **std_out
        }

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
        
        # 1. On-Level Premium
        ReservingEngine._on_level_premiums(t_eval_base, req.rate_changes)
        
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
                        "ibnr": 0.0,
                        "reserve": 0.0,
                        "paid": 0.0,
                        "reported": 0.0,
                        "case_outstanding": 0.0
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
                        "ibnr": 0.0,
                        "reserve": 0.0,
                        "paid": 0.0,
                        "reported": 0.0,
                        "case_outstanding": 0.0
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
                chosen_tail, chosen_reason = ReservingEngine._resolve_tail_factor(ldfs_for_run, t_eval, tail_to_use)
                if ldfs_for_run:
                    ldfs_for_run[-1] = chosen_tail
                else:
                    ldfs_for_run = [chosen_tail]

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
                    "ibnr": 0.0,
                    "reserve": 0.0,
                    "paid": 0.0,
                    "reported": 0.0,
                    "case_outstanding": 0.0
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
                        "ibnr": 0.0,
                        "reserve": 0.0,
                        "paid": 0.0,
                        "reported": 0.0,
                        "case_outstanding": 0.0
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

        # Default recommended method is CL or the first successful method if CL is not enabled
        rec_code = "CL"
        if not any(m["code"] == "CL" and m["status"] == "success" for m in methods_out):
            first_success = next((m for m in methods_out if m["status"] == "success"), None)
            if first_success:
                rec_code = first_success["code"]
        
        rec_model = next((m for m in methods_out if m["code"] == rec_code and m["status"] == "success"), None)
        best_estimate_val = rec_model["ultimate"] if rec_model else (median_ultimate if median_ultimate > 0 else 0.0)
        
        run_id = str(uuid.uuid4())
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        selected_methods = [code for code, cfg in configs.items() if cfg.enabled]

        # ── TOOL: Compliance Engine (ASOP) ────────────────────────────────────
        compliance_audit = {}
        if 'compliance_engine' in session:
            ce = session['compliance_engine']
            executed = [m["code"] for m in methods_out if m["status"] == "success"]
            ce.run_estimation_checks(executed)
            ce.run_selection_checks()
            ce.run_results_checks()
            compliance_audit = ce.audit_log

        results_obj = {
            "run_id": run_id,
            "execution_id": run_id,
            "timestamp": timestamp,
            "selected_methods": selected_methods,
            "paid_ldfs": paid_ldfs_to_use,
            "incurred_ldfs": incurred_ldfs_to_use,
            "paid_tail_factor": req.paid_tail_factor,
            "incurred_tail_factor": req.incurred_tail_factor,
            "configs": {k: v.dict() if hasattr(v, 'dict') else v for k, v in configs.items()},
            "best_estimate": best_estimate_val,
            "selected_method": rec_code,
            "ai_recommendation": None,
            "methods": methods_out,
            "compliance_audit": compliance_audit
        }
        
        session['results'] = results_obj
        if 'executions' not in session:
            session['executions'] = {}
        session['executions'][run_id] = results_obj
        
        # Consolidate top-level session variables for active method & active source basis
        rec_model_res = next((m for m in methods_out if m.get('code') == rec_code and m.get('status') == 'success'), None)
        
        session['totalIBNR'] = rec_model_res.get('ibnr', 0.0) if rec_model_res else 0.0
        session['totalUlt'] = rec_model_res.get('ultimate', best_estimate_val) if rec_model_res else best_estimate_val
        session['total_ibnr'] = session['totalIBNR']
        session['total_ultimate'] = session['totalUlt']
        session['data_source'] = global_source
        session['ldfs'] = paid_ldfs_to_use
        session['incurred_ldfs'] = incurred_ldfs_to_use
        
        return {
            "success": True,
            "execution_id": run_id,
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
            "ai_recommendation": None,
            "methods": methods_out,
            "compliance_audit": compliance_audit
        }
