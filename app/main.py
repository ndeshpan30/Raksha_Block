from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
import numpy as np
from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import get_db, init_db, SessionLocal
from app.models import MaintenanceRequestModel
from app.schemas import (
    MaintenanceRequestResponse,
    RiskPredictionInput,
    RiskPredictionResponse,
    OptimizationPlanResponse,
    OptimizationPlanInput,
    BundledBlockSchema,
    BlockExplainResponse,
    BlockActionInput,
    BlockActionResponse,
    BaselineScheduleMetrics,
)
from app.ingestion import ingest_from_files
from app.risk_model import (
    predict_risk_score,
    predict_risk_scores,
    get_risk_tier,
    get_model_metadata,
    extract_features_dict,
)
from app.optimizer import (
    optimize_requests,
    OptimizerConfig,
    OptimizationResult,
    calculate_baseline_schedule,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema is created and populated on application launch."""
    init_db()
    with SessionLocal() as db:
        count = db.query(MaintenanceRequestModel).count()
        if count == 0:
            ingest_from_files(db=db)
        else:
            # Backfill any existing database requests where risk_score is NULL or 0.0
            unscored = db.query(MaintenanceRequestModel).filter(
                (MaintenanceRequestModel.risk_score.is_(None)) | (MaintenanceRequestModel.risk_score == 0.0)
            ).all()
            if unscored:
                for req in unscored:
                    req.risk_score = predict_risk_score(req)
                db.commit()

        # Phase 7 Pre-warm: pre-solve baseline to populate solution cache for instant delta re-optimization
        all_reqs = db.query(MaintenanceRequestModel).all()
        if all_reqs:
            baseline_result = optimize_requests(all_reqs)
            for b in baseline_result.blocks:
                b_dict = b.to_dict()
                _LATEST_BLOCKS_CACHE[b.block_id] = b_dict
    yield


app = FastAPI(
    title="RAKSHA-BLOCK: AI Maintenance Coordination API",
    description=(
        "SIH26027 — AI-powered coordination of Indian Railways maintenance block requests "
        "across Engineering (P-Way), S&T, and TRD departments."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/requests",
    response_model=List[MaintenanceRequestResponse],
    tags=["Requests"],
    summary="Fetch all ingested maintenance block requests",
)
def get_requests(
    department: Optional[str] = Query(None, description="Filter by department (ENG, S&T, TRD)"),
    section_id: Optional[str] = Query(None, description="Filter by track section ID"),
    limit: Optional[int] = Query(None, ge=0, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all normalized maintenance block requests ingested from legacy systems
    (TMS, SMMS, TDMS, COA), enriched with LightGBM operational failure risk scores (0-100).
    """
    query = db.query(MaintenanceRequestModel)

    if department:
        query = query.filter(MaintenanceRequestModel.department == department.strip().upper())
    if section_id:
        query = query.filter(MaintenanceRequestModel.section_id == section_id.strip())

    query = query.order_by(
        MaintenanceRequestModel.requested_window_start,
        MaintenanceRequestModel.request_id,
    )

    if offset > 0:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return query.all()


# Alias route matching ARCHITECTURE.md specification (/api/v1/requests)
@app.get(
    "/api/v1/requests",
    response_model=List[MaintenanceRequestResponse],
    tags=["Requests"],
    include_in_schema=False,
)
def get_requests_v1(
    department: Optional[str] = Query(None),
    section_id: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return get_requests(department=department, section_id=section_id, limit=limit, offset=offset, db=db)


# ==============================================================================
# Phase 3 ML Risk Scoring Endpoints
# ==============================================================================

@app.post(
    "/api/v1/risk/score",
    response_model=RiskPredictionResponse,
    tags=["ML Risk Scoring"],
    summary="Run LightGBM risk inference on asset condition features",
)
@app.post(
    "/risk/score",
    response_model=RiskPredictionResponse,
    tags=["ML Risk Scoring"],
    include_in_schema=False,
)
def score_request_risk(payload: RiskPredictionInput):
    """
    Run on-demand tabular inference using the trained LightGBM model.
    Outputs a calibrated failure risk score (0.0 - 100.0) and operational priority tier.
    """
    input_dict = payload.model_dump()
    feat_dict = extract_features_dict(input_dict)
    score = predict_risk_score(feat_dict)
    tier = get_risk_tier(score)
    return RiskPredictionResponse(
        request_id=payload.request_id,
        risk_score=score,
        risk_tier=tier,
        features=feat_dict,
    )


@app.get(
    "/api/v1/risk/distribution",
    tags=["ML Risk Scoring"],
    summary="Fetch risk score distribution across all database requests",
)
@app.get(
    "/risk/distribution",
    tags=["ML Risk Scoring"],
    include_in_schema=False,
)
def get_risk_distribution(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Computes statistical distribution metrics across all ingested requests
    to verify model non-degeneracy (min, max, mean, std, percentiles, histogram).
    """
    requests = db.query(MaintenanceRequestModel).all()
    if not requests:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "p50_median": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "tier_distribution": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "ascii_histogram": [],
            "message": "No maintenance requests found in database.",
        }

    scores = [r.risk_score if r.risk_score is not None else predict_risk_score(r) for r in requests]
    scores_arr = np.array(scores, dtype=float)

    counts, bin_edges = np.histogram(scores_arr, bins=10, range=(0.0, 100.0))
    ascii_bars = []
    for i in range(len(counts)):
        bar = "#" * int(counts[i] // 2)
        ascii_bars.append(f"[{bin_edges[i]:5.1f} - {bin_edges[i+1]:5.1f}]: {counts[i]:3d} | {bar}")

    tier_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for s in scores:
        tier = get_risk_tier(s)
        tier_counts[tier] += 1

    return {
        "count": len(scores),
        "min": round(float(np.min(scores_arr)), 2),
        "max": round(float(np.max(scores_arr)), 2),
        "mean": round(float(np.mean(scores_arr)), 2),
        "std": round(float(np.std(scores_arr)), 2),
        "p10": round(float(np.percentile(scores_arr, 10)), 2),
        "p25": round(float(np.percentile(scores_arr, 25)), 2),
        "p50_median": round(float(np.median(scores_arr)), 2),
        "p75": round(float(np.percentile(scores_arr, 75)), 2),
        "p90": round(float(np.percentile(scores_arr, 90)), 2),
        "tier_distribution": tier_counts,
        "ascii_histogram": ascii_bars,
    }


@app.get(
    "/api/v1/risk/model-info",
    tags=["ML Risk Scoring"],
    summary="Get risk model metadata and hyperparameters",
)
@app.get(
    "/risk/model-info",
    tags=["ML Risk Scoring"],
    include_in_schema=False,
)
def get_model_info():
    """Return model type, feature names, urgency mapping, and performance metrics."""
    return get_model_metadata()


# ==============================================================================
# Phase 4 CP-SAT Optimizer Endpoints
# ==============================================================================

_LATEST_BLOCKS_CACHE: Dict[str, Dict[str, Any]] = {}


@app.post(
    "/optimize",
    response_model=OptimizationPlanResponse,
    tags=["Optimization Engine"],
    summary="Trigger CP-SAT optimizer to generate bundled maintenance block plan",
)
@app.post(
    "/api/v1/optimizer/plan",
    response_model=OptimizationPlanResponse,
    tags=["Optimization Engine"],
    include_in_schema=False,
)
def create_block_plan(
    payload: Optional[OptimizationPlanInput] = None,
    section_id: Optional[str] = Query(None, description="Optional track section filter (when optimizing DB records)"),
    department: Optional[str] = Query(None, description="Optional department filter (when optimizing DB records)"),
    delta_mode: Optional[bool] = Query(None, description="Enable localized delta re-optimization"),
    db: Session = Depends(get_db),
):
    """
    Solves the multi-department Resource-Constrained Project Scheduling Problem with
    Cross-Departmental Spatial/Temporal Bundling (RCPSP-CDSTB) using Google OR-Tools CP-SAT.

    If `requests` is supplied in the JSON payload, the optimizer schedules those requests.
    If omitted or empty, it queries the maintenance requests from the relational database.

    Supports Phase 7 Localized Delta Re-optimization for interactive What-If live simulations:
    re-solves only affected subproblems while reusing unaffected clusters, achieving sub-second (< 100ms)
    re-solve latency.
    """
    is_delta = (
        delta_mode
        if delta_mode is not None
        else (payload.delta_mode if payload and payload.delta_mode is not None else False)
    )
    mod_req_ids = list(payload.modified_request_ids) if payload and payload.modified_request_ids else []
    recompute = payload.recompute_risk if payload and payload.recompute_risk is not None else False

    if is_delta and not mod_req_ids and payload and payload.requests:
        # Auto-detect modified requests by comparing against current DB records
        db_reqs = {r.request_id: r for r in db.query(MaintenanceRequestModel).all()}
        for r_in in payload.requests:
            rid = str(r_in.get("request_id"))
            db_r = db_reqs.get(rid)
            if db_r:
                ws = str(r_in.get("requested_window_start", ""))[:19]
                we = str(r_in.get("requested_window_end", ""))[:19]
                db_ws = db_r.requested_window_start.isoformat()[:19] if db_r.requested_window_start else ""
                db_we = db_r.requested_window_end.isoformat()[:19] if db_r.requested_window_end else ""
                dur = int(r_in.get("required_duration_minutes", db_r.required_duration_minutes))
                urg = str(r_in.get("urgency_category", db_r.urgency_category or "")).upper()
                db_urg = str(db_r.urgency_category or "").upper()
                if ws != db_ws or we != db_we or dur != db_r.required_duration_minutes or urg != db_urg:
                    mod_req_ids.append(rid)

    cfg = OptimizerConfig(
        spatial_proximity_km=payload.spatial_proximity_km if payload and payload.spatial_proximity_km is not None else 2.0,
        max_block_km_span=payload.max_block_km_span if payload and payload.max_block_km_span is not None else 15.0,
        delta_mode=is_delta,
        modified_request_ids=mod_req_ids,
        recompute_risk=recompute,
    )

    if payload and payload.requests:
        target_requests = payload.requests
    else:
        query = db.query(MaintenanceRequestModel)
        if section_id:
            query = query.filter(MaintenanceRequestModel.section_id == section_id.strip())
        if department:
            query = query.filter(MaintenanceRequestModel.department == department.strip().upper())
        target_requests = query.all()

    result = optimize_requests(target_requests, config=cfg)
    plan_dict = result.to_dict()
    for b in plan_dict.get("blocks", []):
        if "block_id" in b:
            _LATEST_BLOCKS_CACHE[b["block_id"]] = b
    return plan_dict


@app.get(
    "/api/v1/optimizer/comparison",
    response_model=BaselineScheduleMetrics,
    tags=["Optimization Engine"],
    summary="Fetch before/after comparative KPI metrics (baseline vs CP-SAT optimized)",
)
def get_optimizer_comparison(db: Session = Depends(get_db)):
    """
    Phase 8: Returns quantitative before/after comparison contrasting the unbundled naive baseline
    against the CP-SAT mathematically optimized possession plan.
    """
    requests = db.query(MaintenanceRequestModel).all()
    if not requests:
        try:
            import json, os
            data_path = os.path.join(os.path.dirname(__file__), "..", "data", "maintenance_requests.json")
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    requests = json.load(f)
        except Exception:
            pass
    opt_result = optimize_requests(requests)
    return opt_result.baseline_comparison


@app.get(
    "/api/v1/optimizer/baseline",
    tags=["Optimization Engine"],
    summary="Fetch unbundled naive baseline schedule",
)
def get_baseline_schedule(db: Session = Depends(get_db)):
    """
    Phase 8: Computes and returns the unbundled naive baseline possession schedule.
    """
    requests = db.query(MaintenanceRequestModel).all()
    if not requests:
        try:
            import json, os
            data_path = os.path.join(os.path.dirname(__file__), "..", "data", "maintenance_requests.json")
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    requests = json.load(f)
        except Exception:
            pass
    return calculate_baseline_schedule(requests)


# ==============================================================================
# Phase 5 Explainability & Block Management Endpoints
# ==============================================================================

@app.get(
    "/api/v1/blocks",
    response_model=List[BundledBlockSchema],
    tags=["Optimization Engine"],
    summary="Fetch all optimized bundled maintenance blocks from database requests",
)
@app.get(
    "/blocks",
    response_model=List[BundledBlockSchema],
    tags=["Optimization Engine"],
    include_in_schema=False,
)
def get_blocks(
    section_id: Optional[str] = Query(None, description="Optional track section filter"),
    department: Optional[str] = Query(None, description="Optional department filter"),
    db: Session = Depends(get_db),
):
    """
    Retrieves optimized bundled maintenance blocks for current database requests,
    complete with Phase 5 structured explanations and constituent breakdowns.
    """
    query = db.query(MaintenanceRequestModel)
    if section_id:
        query = query.filter(MaintenanceRequestModel.section_id == section_id.strip())
    if department:
        query = query.filter(MaintenanceRequestModel.department == department.strip().upper())
    requests = query.all()
    result = optimize_requests(requests)
    blocks_dict = [b.to_dict() for b in result.blocks]
    for b in blocks_dict:
        if "block_id" in b:
            _LATEST_BLOCKS_CACHE[b["block_id"]] = b
    return blocks_dict


@app.get(
    "/api/v1/blocks/{block_id}/explain",
    response_model=BlockExplainResponse,
    tags=["Explainability Engine"],
    summary="Get detailed plain-language and structured constraint explanation for a block",
)
@app.get(
    "/blocks/{block_id}/explain",
    response_model=BlockExplainResponse,
    tags=["Explainability Engine"],
    include_in_schema=False,
)
def explain_block(block_id: str, db: Session = Depends(get_db)):
    """
    Returns the comprehensive 'Why this block?' explanation object including
    merged requests details, driving risk factors, driving constraints,
    and alternatives evaluated for the specified block.
    """
    if block_id in _LATEST_BLOCKS_CACHE:
        cached_b = _LATEST_BLOCKS_CACHE[block_id]
        return BlockExplainResponse(
            block_id=cached_b["block_id"],
            explanation_text=cached_b["explanation_text"],
            explanation_detail=cached_b.get("explanation_detail") or cached_b.get("explanation", {}),
            explanation=cached_b.get("explanation") or cached_b.get("explanation_detail", {}),
        )

    requests = db.query(MaintenanceRequestModel).all()
    result = optimize_requests(requests)
    for b in result.blocks:
        b_dict = b.to_dict()
        _LATEST_BLOCKS_CACHE[b.block_id] = b_dict
        if b.block_id == block_id:
            return BlockExplainResponse(
                block_id=b.block_id,
                explanation_text=b.explanation_text,
                explanation_detail=b_dict.get("explanation_detail", {}),
                explanation=b_dict.get("explanation_detail", {}),
            )
    raise HTTPException(status_code=404, detail=f"Block '{block_id}' not found in current optimization plan.")


@app.post(
    "/api/v1/blocks/{block_id}/action",
    response_model=BlockActionResponse,
    tags=["Controller Actions"],
    summary="Controller approve, reject, or modify scheduled block",
)
@app.post(
    "/blocks/{block_id}/action",
    response_model=BlockActionResponse,
    tags=["Controller Actions"],
    include_in_schema=False,
)
def block_action(block_id: str, payload: BlockActionInput):
    """
    Accepts Section Controller or Chief Controller decisions (APPROVE, REJECT, MODIFY)
    on an AI-scheduled maintenance block.
    """
    act = payload.action.strip().upper()
    valid_actions = {"APPROVE", "REJECT", "MODIFY", "APPROVED", "REJECTED", "MODIFIED"}
    if act not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{payload.action}'. Expected one of: APPROVE, REJECT, MODIFY.",
        )
    status_map = {
        "APPROVE": "APPROVED_BY_CONTROLLER",
        "APPROVED": "APPROVED_BY_CONTROLLER",
        "REJECT": "REJECTED_BY_CONTROLLER",
        "REJECTED": "REJECTED_BY_CONTROLLER",
        "MODIFY": "MODIFIED_BY_CONTROLLER",
        "MODIFIED": "MODIFIED_BY_CONTROLLER",
    }
    final_status = status_map.get(act, "PROPOSED")
    notes_suffix = f" Notes: {payload.controller_notes}" if payload.controller_notes else ""
    return BlockActionResponse(
        block_id=block_id,
        action=act,
        status=final_status,
        message=f"Block {block_id} status updated to {final_status}.{notes_suffix}",
    )


@app.get(
    "/api/v1/health",
    tags=["System"],
    summary="System health check",
)
@app.get(
    "/health",
    tags=["System"],
    include_in_schema=False,
)
def health_check():
    """Returns system status, active version, and service identifier."""
    return {"status": "healthy", "service": "RAKSHA-BLOCK", "version": "1.0.0"}



