"""
RAKSHA-BLOCK: CP-SAT Block Scheduling & Spatial-Temporal Bundling Optimizer
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination

Solves the multi-department Resource-Constrained Project Scheduling Problem
with Cross-Departmental Spatial/Temporal Bundling (RCPSP-CDSTB) using
Google OR-Tools CP-SAT (ortools.sat.python.cp_model).
"""

import time
import copy
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict

from ortools.sat.python import cp_model

from app.explainer import generate_block_explanation

logger = logging.getLogger("raksha.optimizer")


@dataclass
class OptimizerConfig:
    """Configuration parameters for CP-SAT Block Scheduling & Bundling Optimizer."""
    spatial_proximity_km: float = 2.0
    max_block_km_span: float = 15.0
    weight_block_count: int = 10000
    weight_duration: int = 10
    weight_risk_delay: int = 1
    unassigned_penalty: int = 200000
    time_limit_seconds: float = 30.0
    num_search_workers: int = 4
    random_seed: int = 42
    delta_mode: bool = False
    modified_request_ids: List[str] = field(default_factory=list)
    recompute_risk: bool = False


@dataclass
class ConstituentRequestSummary:
    """Summary of a maintenance request bundled into a block."""
    request_id: str
    department: str
    work_type: str
    asset_id: str
    asset_type: str
    chainage_start: float
    chainage_end: float
    requested_window_start: str
    requested_window_end: str
    required_duration_minutes: int
    scheduled_start: str
    scheduled_end: str
    risk_score: float
    requires_power_block: bool
    requires_traffic_block: bool


@dataclass
class BundledBlock:
    """Consolidated railway maintenance possession block scheduled by CP-SAT."""
    block_id: str
    section_id: str
    corridor_slot: str
    start_km: float
    end_km: float
    scheduled_start: str
    scheduled_end: str
    total_duration_minutes: int
    bundled_request_ids: List[str]
    departments_involved: List[str]
    power_block_granted: bool
    traffic_block_granted: bool
    savings_minutes: int
    explanation_text: str
    explanation_detail: Dict[str, Any] = field(default_factory=dict)
    explanation: Optional[Dict[str, Any]] = None
    approval_status: str = "PROPOSED"
    constituent_requests: List[Dict[str, Any]] = field(default_factory=list)
    is_modified: bool = False
    delta_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("explanation") and d.get("explanation_detail"):
            d["explanation"] = d["explanation_detail"]
        return d


@dataclass
class BaselineComparison:
    """Quantitative before/after comparison between naive baseline and CP-SAT optimized schedule."""
    baseline_block_count: int
    optimized_block_count: int
    block_count_reduction: int
    block_count_reduction_pct: float
    baseline_possession_minutes: int
    baseline_possession_hours: float
    optimized_possession_minutes: int
    optimized_possession_hours: float
    possession_savings_minutes: int
    possession_savings_hours: float
    possession_reduction_pct: float
    baseline_traffic_halts: int
    optimized_traffic_halts: int
    avoided_traffic_halts: int
    coordinated_bundles_created: int
    triple_department_bundles: int
    dual_department_bundles: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


@dataclass
class OptimizationResult:
    """Comprehensive output of the block scheduling optimization run."""
    status: str
    total_requests_in: int
    total_blocks_out: int
    bundled_blocks_count: int
    single_blocks_count: int
    total_original_duration_minutes: int
    total_bundled_duration_minutes: int
    total_savings_minutes: int
    savings_percentage: float
    solve_time_seconds: float
    blocks: List[BundledBlock] = field(default_factory=list)
    reoptimization_mode: str = "FULL"
    delta_request_ids: List[str] = field(default_factory=list)
    affected_blocks_count: int = 0
    baseline_comparison: Optional[Union[BaselineComparison, Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        comp_dict = None
        if self.baseline_comparison is not None:
            comp_dict = self.baseline_comparison.to_dict() if hasattr(self.baseline_comparison, "to_dict") else self.baseline_comparison
        return {
            "status": self.status,
            "total_requests_in": self.total_requests_in,
            "total_blocks_out": self.total_blocks_out,
            "bundled_blocks_count": self.bundled_blocks_count,
            "single_blocks_count": self.single_blocks_count,
            "total_original_duration_minutes": self.total_original_duration_minutes,
            "total_bundled_duration_minutes": self.total_bundled_duration_minutes,
            "total_savings_minutes": self.total_savings_minutes,
            "savings_percentage": round(self.savings_percentage, 2),
            "solve_time_seconds": round(self.solve_time_seconds, 4),
            "blocks": [b.to_dict() for b in self.blocks],
            "reoptimization_mode": self.reoptimization_mode,
            "delta_request_ids": self.delta_request_ids,
            "affected_blocks_count": self.affected_blocks_count,
            "baseline_comparison": comp_dict,
        }


def normalize_request_dict(req: Any, recompute_risk: bool = False) -> Dict[str, Any]:
    """
    Normalizes a request input from dict, Pydantic schema, or SQLAlchemy model
    into a standard dictionary format with parsed datetimes.
    """
    if hasattr(req, "model_dump"):
        d = req.model_dump()
    elif hasattr(req, "to_dict"):
        d = req.to_dict()
    elif hasattr(req, "__dict__"):
        d = {k: v for k, v in req.__dict__.items() if not k.startswith("_")}
    elif isinstance(req, dict):
        d = dict(req)
    else:
        raise ValueError(f"Unsupported request object type: {type(req)}")

    ws = d.get("requested_window_start")
    if isinstance(ws, str):
        ws_dt = datetime.fromisoformat(ws.replace("Z", "+00:00")).replace(tzinfo=None)
    elif isinstance(ws, datetime):
        ws_dt = ws.replace(tzinfo=None)
    else:
        raise ValueError(f"Invalid requested_window_start in request {d.get('request_id')}: {ws}")

    we = d.get("requested_window_end")
    if isinstance(we, str):
        we_dt = datetime.fromisoformat(we.replace("Z", "+00:00")).replace(tzinfo=None)
    elif isinstance(we, datetime):
        we_dt = we.replace(tzinfo=None)
    else:
        raise ValueError(f"Invalid requested_window_end in request {d.get('request_id')}: {we}")

    # Fallback/extract risk_score
    risk = d.get("risk_score")
    if risk is None or recompute_risk or d.get("recompute_risk"):
        try:
            from app.risk_model import predict_risk_score
            risk = predict_risk_score(d)
        except Exception:
            risk = 50.0 if risk is None else risk

    return {
        "request_id": str(d.get("request_id")),
        "department": str(d.get("department", "ENG")).upper(),
        "section_id": str(d.get("section_id")),
        "corridor_slot": str(d.get("corridor_slot", "SLOT_NIGHT")),
        "chainage_start": float(d.get("chainage_start", 0.0)),
        "chainage_end": float(d.get("chainage_end", 0.0)),
        "dt_start": ws_dt,
        "dt_end": we_dt,
        "required_duration_minutes": int(d.get("required_duration_minutes", 60)),
        "work_type": str(d.get("work_type", "Track Maintenance")),
        "asset_id": str(d.get("asset_id", "ASSET-001")),
        "asset_type": str(d.get("asset_type", "Track")),
        "risk_score": float(risk),
        "urgency_category": str(d.get("urgency_category", d.get("urgency_tier", "MEDIUM"))).upper(),
        "requires_power_block": bool(d.get("requires_power_block", False)),
        "requires_traffic_block": bool(d.get("requires_traffic_block", True)),
        "status": str(d.get("status", "PENDING")),
        "raw": d,
    }


def are_spatially_interfering(r1: Dict[str, Any], r2: Dict[str, Any], proximity: float = 2.0) -> bool:
    """
    Checks if two requests on the same section spatially interfere with each other.
    Interference occurs if linear chainages overlap or the physical gap between them
    is within safety proximity (e.g. 2.0 km). Spatially interfering requests must be
    co-optimized in the same subproblem to prevent track double-booking.
    """
    if r1["section_id"] != r2["section_id"]:
        return False
    c_start1, c_end1 = r1["chainage_start"], r1["chainage_end"]
    c_start2, c_end2 = r2["chainage_start"], r2["chainage_end"]
    return (c_start1 <= c_end2 + proximity and c_end1 >= c_start2 - proximity)


def are_temporally_overlapping(r1: Dict[str, Any], r2: Dict[str, Any]) -> bool:
    """
    Checks if two requests have overlapping requested operational time windows.
    Requests with disjoint requested windows can never execute concurrently
    and must not be bundled into a single block with dead possession time.
    """
    return r1["dt_start"] < r2["dt_end"] and r2["dt_start"] < r1["dt_end"]


def find_bridging_requests(
    req_i: Dict[str, Any],
    req_j: Dict[str, Any],
    all_cluster_reqs: List[Dict[str, Any]],
    proximity: float = 2.0,
) -> List[int]:
    """
    Finds indices of candidate requests k in cluster that bridge the spatial gap
    between req_i and req_j, ensuring chainage continuity without gaps > proximity.
    """
    c1_s, c1_e = req_i["chainage_start"], req_i["chainage_end"]
    c2_s, c2_e = req_j["chainage_start"], req_j["chainage_end"]
    if c1_s > c2_s:
        c1_s, c1_e, c2_s, c2_e = c2_s, c2_e, c1_s, c1_e

    gap = c2_s - c1_e
    if gap <= proximity:
        return []

    bridgers = []
    for idx, r in enumerate(all_cluster_reqs):
        if r["chainage_start"] <= c1_e + proximity and r["chainage_end"] >= c2_s - proximity:
            bridgers.append(idx)
    return bridgers


def are_spatially_compatible(r1: Dict[str, Any], r2: Dict[str, Any], config: OptimizerConfig) -> bool:
    """
    Checks if two requests are directly pairwise compatible for physical possession bundling.
    Must be on the same section, chainages must overlap or be within proximity gap,
    and total combined span must not exceed max_block_km_span.
    """
    if r1["section_id"] != r2["section_id"]:
        return False

    c_start1, c_end1 = r1["chainage_start"], r1["chainage_end"]
    c_start2, c_end2 = r2["chainage_start"], r2["chainage_end"]

    min_start = min(c_start1, c_start2)
    max_end = max(c_end1, c_end2)
    span = max_end - min_start
    if span > config.max_block_km_span:
        return False

    is_overlapping_or_close = (
        c_start1 <= c_end2 + config.spatial_proximity_km
        and c_end1 >= c_start2 - config.spatial_proximity_km
    )
    return is_overlapping_or_close


def partition_into_scheduling_subproblems(
    requests: List[Dict[str, Any]],
    config: OptimizerConfig,
) -> List[List[Dict[str, Any]]]:
    """
    Partitions maintenance requests into independent spatial-temporal clusters using
    connected components on the spatial interference graph.
    Two requests can interact (bundle or compete) if and only if they are on
    the same section, in the same operational corridor window, and spatially interfering
    (overlapping chainage or within spatial proximity).
    """
    from collections import defaultdict

    # 1. Group by (section_id, date, corridor_slot)
    groups = defaultdict(list)
    for r in requests:
        date_str = r["dt_start"].strftime("%Y-%m-%d")
        slot_key = (r["section_id"], date_str, r["corridor_slot"])
        groups[slot_key].append(r)

    # 2. Within each group, compute connected components via spatial interference graph
    subproblems: List[List[Dict[str, Any]]] = []

    for slot_key, rlist in groups.items():
        n = len(rlist)
        if n == 1:
            subproblems.append(rlist)
            continue

        adj = {i: [] for i in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if are_spatially_interfering(rlist[i], rlist[j], config.spatial_proximity_km):
                    adj[i].append(j)
                    adj[j].append(i)

        visited = set()
        for i in range(n):
            if i not in visited:
                comp = []
                queue = [i]
                visited.add(i)
                while queue:
                    curr = queue.pop(0)
                    comp.append(rlist[curr])
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                subproblems.append(comp)

    return subproblems


def solve_cluster_cp_sat(
    cluster: List[Dict[str, Any]],
    config: OptimizerConfig,
    block_seq_start: int,
) -> Tuple[List[BundledBlock], int, bool]:
    """
    Formulates and solves the CP-SAT scheduling and bundling model for a cluster of requests.
    Returns generated BundledBlock objects, updated sequence counter, and whether all requests
    were scheduled feasibly/optimally.
    """
    K = len(cluster)
    if K == 0:
        return [], block_seq_start, True

    # Reference timeline epoch (minimum window start of the cluster)
    epoch = min(r["dt_start"] for r in cluster)
    horizon_end = max(r["dt_end"] for r in cluster)
    max_horizon_minutes = max(1, int((horizon_end - epoch).total_seconds() // 60))

    model = cp_model.CpModel()

    # Request decision variables
    starts = []
    ends = []
    durs = []
    risks = []

    for i, r in enumerate(cluster):
        w_start = max(0, int((r["dt_start"] - epoch).total_seconds() // 60))
        w_end = min(max_horizon_minutes, int((r["dt_end"] - epoch).total_seconds() // 60))
        dur = r["required_duration_minutes"]

        # Ensure valid bounds
        dur = min(dur, max(1, w_end - w_start))
        durs.append(dur)
        risks.append(r["risk_score"])

        latest_start = max(w_start, w_end - dur)
        s_var = model.NewIntVar(w_start, latest_start, f"s_{i}")
        e_var = model.NewIntVar(w_start + dur, w_end, f"e_{i}")
        model.Add(e_var == s_var + dur)

        starts.append(s_var)
        ends.append(e_var)

    # Candidate Blocks (at most K blocks)
    y = [model.NewBoolVar(f"y_{b}") for b in range(K)]
    B_start = [model.NewIntVar(0, max_horizon_minutes, f"bs_{b}") for b in range(K)]
    B_end = [model.NewIntVar(0, max_horizon_minutes, f"be_{b}") for b in range(K)]
    B_dur = [model.NewIntVar(0, max_horizon_minutes, f"bd_{b}") for b in range(K)]

    block_intervals = []
    for b in range(K):
        model.Add(B_end[b] == B_start[b] + B_dur[b])
        b_int = model.NewOptionalIntervalVar(B_start[b], B_dur[b], B_end[b], y[b], f"b_int_{b}")
        block_intervals.append(b_int)

    # Assignment variables: x[i, b] == 1 if request i is in block b, u[i] == 1 if deferred
    x = {}
    u = [model.NewBoolVar(f"u_{i}") for i in range(K)]
    for i in range(K):
        for b in range(K):
            x[i, b] = model.NewBoolVar(f"x_{i}_{b}")
        model.Add(sum(x[i, b] for b in range(K)) + u[i] == 1)

    # Block activation, containment, and duration bounds
    for b in range(K):
        # Durations cannot exceed sum of constituent requests (guarantees savings >= 0, prevents dead track closure)
        model.Add(B_dur[b] <= sum(durs[i] * x[i, b] for i in range(K)))
        for i in range(K):
            model.Add(x[i, b] <= y[b])
            model.Add(B_start[b] <= starts[i]).OnlyEnforceIf(x[i, b])
            model.Add(ends[i] <= B_end[b]).OnlyEnforceIf(x[i, b])
        model.Add(y[b] <= sum(x[i, b] for i in range(K)))

    # Incompatibility and bridging constraints between requests sharing a block
    for i in range(K):
        for j in range(i + 1, K):
            c_min = min(cluster[i]["chainage_start"], cluster[j]["chainage_start"])
            c_max = max(cluster[i]["chainage_end"], cluster[j]["chainage_end"])
            span = c_max - c_min

            # 1. Temporal disjointness: requests whose requested windows do not overlap cannot share a block
            t_disjoint = not are_temporally_overlapping(cluster[i], cluster[j])

            # 2. Max physical chainage span violation
            span_viol = span > config.max_block_km_span

            if t_disjoint or span_viol:
                for b in range(K):
                    model.Add(x[i, b] + x[j, b] <= 1)
            else:
                # 3. Spatial proximity and bridging: gap must not exceed proximity unless bridged
                bridgers = find_bridging_requests(cluster[i], cluster[j], cluster, config.spatial_proximity_km)
                gap = max(
                    0.0,
                    max(cluster[i]["chainage_start"], cluster[j]["chainage_start"])
                    - min(cluster[i]["chainage_end"], cluster[j]["chainage_end"]),
                )
                if gap > config.spatial_proximity_km:
                    if not bridgers:
                        for b in range(K):
                            model.Add(x[i, b] + x[j, b] <= 1)
                    else:
                        for b in range(K):
                            model.Add(x[i, b] + x[j, b] <= 1 + sum(x[k, b] for k in bridgers))

    # Disjunctive NoOverlap between active blocks within the same spatial track zone
    model.AddNoOverlap(block_intervals)

    # Symmetry breaking
    for b in range(K - 1):
        model.Add(y[b] >= y[b + 1])
    model.Add(x[0, 0] + u[0] == 1)

    for i in range(K):
        for b in range(i + 1, K):
            model.Add(x[i, b] == 0)

    # Multi-Objective Function:
    # 1. Minimize block count
    # 2. Minimize total possession minutes
    # 3. Prioritize high-risk requests into earliest possible slot
    # 4. Strongly penalize deferring any request
    term_block_count = config.weight_block_count * sum(y[b] for b in range(K))
    term_duration = config.weight_duration * sum(B_dur[b] for b in range(K))
    term_risk_delay = sum(
        max(1, int(round(risks[i]))) * (starts[i] - max(0, int((cluster[i]["dt_start"] - epoch).total_seconds() // 60)))
        for i in range(K)
    )
    term_unassigned = sum(
        (config.unassigned_penalty + int(round(risks[i])) * 1000) * u[i]
        for i in range(K)
    )

    model.Minimize(term_block_count + term_duration + term_risk_delay + term_unassigned)

    # Solve with CP-SAT
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.time_limit_seconds
    solver.parameters.num_search_workers = config.num_search_workers
    solver.parameters.random_seed = config.random_seed

    status = solver.Solve(model)

    blocks_generated: List[BundledBlock] = []
    is_fully_assigned = True

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for b in range(K):
            if solver.Value(y[b]) == 1:
                assigned_indices = [i for i in range(K) if solver.Value(x[i, b]) == 1]
                if not assigned_indices:
                    continue

                b_start_min = solver.Value(B_start[b])
                b_end_min = solver.Value(B_end[b])
                b_dur_min = solver.Value(B_dur[b])

                sched_start_dt = epoch + timedelta(minutes=b_start_min)
                sched_end_dt = epoch + timedelta(minutes=b_end_min)

                assigned_reqs = [cluster[i] for i in assigned_indices]
                sec_id = assigned_reqs[0]["section_id"]
                slot_id = assigned_reqs[0]["corridor_slot"]

                start_km = min(r["chainage_start"] for r in assigned_reqs)
                end_km = max(r["chainage_end"] for r in assigned_reqs)

                depts_involved = sorted(list(set(r["department"] for r in assigned_reqs)))
                has_power = any(r["requires_power_block"] for r in assigned_reqs)
                has_traffic = any(r["requires_traffic_block"] for r in assigned_reqs)

                sum_req_dur = sum(r["required_duration_minutes"] for r in assigned_reqs)
                savings = max(0, sum_req_dur - b_dur_min)

                # Build constituent summaries
                req_summaries = []
                req_ids = []
                for i in assigned_indices:
                    r = cluster[i]
                    req_ids.append(r["request_id"])
                    r_start_min = solver.Value(starts[i])
                    r_end_min = solver.Value(ends[i])
                    r_s_dt = epoch + timedelta(minutes=r_start_min)
                    r_e_dt = epoch + timedelta(minutes=r_end_min)

                    summary = ConstituentRequestSummary(
                        request_id=r["request_id"],
                        department=r["department"],
                        work_type=r["work_type"],
                        asset_id=r["asset_id"],
                        asset_type=r["asset_type"],
                        chainage_start=r["chainage_start"],
                        chainage_end=r["chainage_end"],
                        requested_window_start=r["dt_start"].isoformat(),
                        requested_window_end=r["dt_end"].isoformat(),
                        required_duration_minutes=r["required_duration_minutes"],
                        scheduled_start=r_s_dt.isoformat(),
                        scheduled_end=r_e_dt.isoformat(),
                        risk_score=round(r["risk_score"], 2),
                        requires_power_block=r["requires_power_block"],
                        requires_traffic_block=r["requires_traffic_block"],
                    )
                    req_summaries.append(asdict(summary))

                # Generate Phase 5 structured explanation
                block_seq_start += 1
                block_id = f"BLK-{sched_start_dt.strftime('%Y%m%d')}-{block_seq_start:04d}"

                explanation_obj = generate_block_explanation(
                    section_id=sec_id,
                    corridor_slot=slot_id,
                    start_km=round(start_km, 2),
                    end_km=round(end_km, 2),
                    scheduled_start=sched_start_dt.isoformat(),
                    scheduled_end=sched_end_dt.isoformat(),
                    total_duration_minutes=b_dur_min,
                    departments_involved=depts_involved,
                    power_block_granted=has_power,
                    traffic_block_granted=has_traffic,
                    savings_minutes=savings,
                    constituent_requests=req_summaries,
                    spatial_proximity_km=config.spatial_proximity_km,
                    max_block_km_span=config.max_block_km_span,
                    is_deferred=False,
                )
                expl_detail = explanation_obj.model_dump()
                expl = explanation_obj.summary

                block_obj = BundledBlock(
                    block_id=block_id,
                    section_id=sec_id,
                    corridor_slot=slot_id,
                    start_km=round(start_km, 2),
                    end_km=round(end_km, 2),
                    scheduled_start=sched_start_dt.isoformat(),
                    scheduled_end=sched_end_dt.isoformat(),
                    total_duration_minutes=b_dur_min,
                    bundled_request_ids=req_ids,
                    departments_involved=depts_involved,
                    power_block_granted=has_power,
                    traffic_block_granted=has_traffic,
                    savings_minutes=savings,
                    explanation_text=expl,
                    explanation_detail=expl_detail,
                    explanation=expl_detail,
                    approval_status="PROPOSED",
                    constituent_requests=req_summaries,
                )
                blocks_generated.append(block_obj)

        # Record any unassigned / deferred requests
        for i in range(K):
            if solver.Value(u[i]) == 1:
                is_fully_assigned = False
                r = cluster[i]
                block_seq_start += 1
                b_id = f"BLK-{r['dt_start'].strftime('%Y%m%d')}-{block_seq_start:04d}"
                summary = ConstituentRequestSummary(
                    request_id=r["request_id"],
                    department=r["department"],
                    work_type=r["work_type"],
                    asset_id=r["asset_id"],
                    asset_type=r["asset_type"],
                    chainage_start=r["chainage_start"],
                    chainage_end=r["chainage_end"],
                    requested_window_start=r["dt_start"].isoformat(),
                    requested_window_end=r["dt_end"].isoformat(),
                    required_duration_minutes=r["required_duration_minutes"],
                    scheduled_start=r["dt_start"].isoformat(),
                    scheduled_end=r["dt_end"].isoformat(),
                    risk_score=round(r["risk_score"], 2),
                    requires_power_block=r["requires_power_block"],
                    requires_traffic_block=r["requires_traffic_block"],
                )
                explanation_obj = generate_block_explanation(
                    section_id=r["section_id"],
                    corridor_slot=r["corridor_slot"],
                    start_km=round(r["chainage_start"], 2),
                    end_km=round(r["chainage_end"], 2),
                    scheduled_start=r["dt_start"].isoformat(),
                    scheduled_end=r["dt_end"].isoformat(),
                    total_duration_minutes=0,
                    departments_involved=[r["department"]],
                    power_block_granted=False,
                    traffic_block_granted=False,
                    savings_minutes=0,
                    constituent_requests=[asdict(summary)],
                    spatial_proximity_km=config.spatial_proximity_km,
                    max_block_km_span=config.max_block_km_span,
                    is_deferred=True,
                )
                expl_detail = explanation_obj.model_dump()
                expl = explanation_obj.summary

                block_obj = BundledBlock(
                    block_id=b_id,
                    section_id=r["section_id"],
                    corridor_slot=r["corridor_slot"],
                    start_km=round(r["chainage_start"], 2),
                    end_km=round(r["chainage_end"], 2),
                    scheduled_start=r["dt_start"].isoformat(),
                    scheduled_end=r["dt_end"].isoformat(),
                    total_duration_minutes=0,
                    bundled_request_ids=[r["request_id"]],
                    departments_involved=[r["department"]],
                    power_block_granted=False,
                    traffic_block_granted=False,
                    savings_minutes=0,
                    explanation_text=expl,
                    explanation_detail=expl_detail,
                    explanation=expl_detail,
                    approval_status="DEFERRED",
                    constituent_requests=[asdict(summary)],
                )
                blocks_generated.append(block_obj)

    else:
        # Fallback: schedule each request as an individual block at requested start
        is_fully_assigned = False
        logger.warning(f"CP-SAT solver returned {solver.StatusName(status)} for cluster of {K} requests; using heuristic fallback.")
        for r in cluster:
            block_seq_start += 1
            b_id = f"BLK-{r['dt_start'].strftime('%Y%m%d')}-{block_seq_start:04d}"
            s_dt = r["dt_start"]
            e_dt = s_dt + timedelta(minutes=r["required_duration_minutes"])
            dur = r["required_duration_minutes"]

            summary = ConstituentRequestSummary(
                request_id=r["request_id"],
                department=r["department"],
                work_type=r["work_type"],
                asset_id=r["asset_id"],
                asset_type=r["asset_type"],
                chainage_start=r["chainage_start"],
                chainage_end=r["chainage_end"],
                requested_window_start=r["dt_start"].isoformat(),
                requested_window_end=r["dt_end"].isoformat(),
                required_duration_minutes=dur,
                scheduled_start=s_dt.isoformat(),
                scheduled_end=e_dt.isoformat(),
                risk_score=round(r["risk_score"], 2),
                requires_power_block=r["requires_power_block"],
                requires_traffic_block=r["requires_traffic_block"],
            )

            explanation_obj = generate_block_explanation(
                section_id=r["section_id"],
                corridor_slot=r["corridor_slot"],
                start_km=round(r["chainage_start"], 2),
                end_km=round(r["chainage_end"], 2),
                scheduled_start=s_dt.isoformat(),
                scheduled_end=e_dt.isoformat(),
                total_duration_minutes=dur,
                departments_involved=[r["department"]],
                power_block_granted=r["requires_power_block"],
                traffic_block_granted=r["requires_traffic_block"],
                savings_minutes=0,
                constituent_requests=[asdict(summary)],
                spatial_proximity_km=config.spatial_proximity_km,
                max_block_km_span=config.max_block_km_span,
                is_deferred=False,
            )
            expl_detail = explanation_obj.model_dump()
            expl = explanation_obj.summary

            block_obj = BundledBlock(
                block_id=b_id,
                section_id=r["section_id"],
                corridor_slot=r["corridor_slot"],
                start_km=round(r["chainage_start"], 2),
                end_km=round(r["chainage_end"], 2),
                scheduled_start=s_dt.isoformat(),
                scheduled_end=e_dt.isoformat(),
                total_duration_minutes=dur,
                bundled_request_ids=[r["request_id"]],
                departments_involved=[r["department"]],
                power_block_granted=r["requires_power_block"],
                traffic_block_granted=r["requires_traffic_block"],
                savings_minutes=0,
                explanation_text=expl,
                explanation_detail=expl_detail,
                explanation=expl_detail,
                approval_status="PROPOSED",
                constituent_requests=[asdict(summary)],
            )
            blocks_generated.append(block_obj)

    return blocks_generated, block_seq_start, is_fully_assigned


_SUBPROBLEM_SOLUTION_CACHE: Dict[Tuple, Tuple[List[BundledBlock], bool]] = {}


def clear_subproblem_cache() -> None:
    """Clear cached subproblem solutions (e.g. for testing or full hard reset)."""
    global _SUBPROBLEM_SOLUTION_CACHE
    _SUBPROBLEM_SOLUTION_CACHE.clear()


def make_cluster_cache_key(comp: List[Dict[str, Any]], config: OptimizerConfig) -> Tuple:
    """
    Computes a deterministic hashable cache key for an independent scheduling cluster.
    If all constituent request constraints, time windows, and optimizer parameters
    match, the CP-SAT cluster solution is mathematically invariant and reusable.
    """
    req_tuples = tuple(
        sorted(
            (
                str(r["request_id"]),
                str(r["section_id"]),
                str(r["corridor_slot"]),
                r["dt_start"].isoformat(),
                r["dt_end"].isoformat(),
                int(r["required_duration_minutes"]),
                round(float(r["risk_score"]), 2),
                str(r.get("urgency_category", "")).upper(),
                round(float(r["chainage_start"]), 3),
                round(float(r["chainage_end"]), 3),
                bool(r["requires_power_block"]),
                bool(r["requires_traffic_block"]),
            )
            for r in comp
        )
    )
    return (req_tuples, round(config.spatial_proximity_km, 2), round(config.max_block_km_span, 2))


def optimize_requests(
    requests: List[Any],
    config: Optional[OptimizerConfig] = None,
) -> OptimizationResult:
    """
    Main entry point for block scheduling optimization.
    Accepts any iterable of requests (dicts, Pydantic models, or SQLAlchemy models).
    Returns an OptimizationResult containing all generated BundledBlocks.

    When `config.delta_mode` is enabled (Phase 7 Localized Delta Re-optimization),
    it re-solves ONLY the subproblems affected by modified requests while reusing
    cached solutions for all unaffected spatial-temporal clusters. This achieves
    sub-second (< 50-100ms) re-solve latency for interactive what-if live demos.
    """
    t_start = time.time()
    cfg = config or OptimizerConfig()

    if not requests:
        empty_comp = BaselineComparison(
            baseline_block_count=0,
            optimized_block_count=0,
            block_count_reduction=0,
            block_count_reduction_pct=0.0,
            baseline_possession_minutes=0,
            baseline_possession_hours=0.0,
            optimized_possession_minutes=0,
            optimized_possession_hours=0.0,
            possession_savings_minutes=0,
            possession_savings_hours=0.0,
            possession_reduction_pct=0.0,
            baseline_traffic_halts=0,
            optimized_traffic_halts=0,
            avoided_traffic_halts=0,
            coordinated_bundles_created=0,
            triple_department_bundles=0,
            dual_department_bundles=0,
        )
        return OptimizationResult(
            status="OPTIMAL",
            total_requests_in=0,
            total_blocks_out=0,
            bundled_blocks_count=0,
            single_blocks_count=0,
            total_original_duration_minutes=0,
            total_bundled_duration_minutes=0,
            total_savings_minutes=0,
            savings_percentage=0.0,
            solve_time_seconds=0.0,
            blocks=[],
            reoptimization_mode="FULL",
            delta_request_ids=[],
            affected_blocks_count=0,
            baseline_comparison=empty_comp,
        )

    mod_id_set = set(cfg.modified_request_ids or [])

    # 1. Normalize requests (only recompute risk for modified requests or requests missing risk_score)
    normalized = []
    for r in requests:
        rid = None
        if isinstance(r, dict):
            rid = str(r.get("request_id", ""))
        elif hasattr(r, "request_id"):
            rid = str(r.request_id)
        should_recompute = cfg.recompute_risk and (not mod_id_set or (rid in mod_id_set))
        normalized.append(normalize_request_dict(r, recompute_risk=should_recompute))

    # 2. Partition into spatial-temporal subproblems
    subproblems = partition_into_scheduling_subproblems(normalized, cfg)

    # 3. Solve each subproblem (with localized delta re-optimization caching)
    all_blocks: List[BundledBlock] = []
    block_seq_counter = 0
    all_fully_assigned = True
    delta_req_ids: List[str] = list(cfg.modified_request_ids)
    affected_blocks_cnt = 0
    mod_id_set = set(cfg.modified_request_ids or [])

    for comp in subproblems:
        c_key = make_cluster_cache_key(comp, cfg)
        comp_req_ids = [r["request_id"] for r in comp]
        has_explicit_mod = any(rid in mod_id_set for rid in comp_req_ids)

        # Delta Mode: check if this independent cluster can be reused from cache
        if cfg.delta_mode and not has_explicit_mod and c_key in _SUBPROBLEM_SOLUTION_CACHE:
            cached_blocks, is_assigned = _SUBPROBLEM_SOLUTION_CACHE[c_key]
            if not is_assigned:
                all_fully_assigned = False
            for cb in cached_blocks:
                block_seq_counter += 1
                b_copy = copy.deepcopy(cb)
                all_blocks.append(b_copy)
        else:
            # Re-solve cluster with Google OR-Tools CP-SAT
            blocks, block_seq_counter, is_fully_assigned = solve_cluster_cp_sat(comp, cfg, block_seq_counter)
            if not is_fully_assigned:
                all_fully_assigned = False

            # Mark visual delta indicators if cluster was modified or solved under delta mode
            is_delta = cfg.delta_mode or has_explicit_mod
            if is_delta:
                affected_blocks_cnt += len(blocks)
                for b in blocks:
                    b.is_modified = True
                    b.delta_type = "REOPTIMIZED"
                for rid in comp_req_ids:
                    if rid not in delta_req_ids:
                        delta_req_ids.append(rid)

            # Store baseline into solution cache
            _SUBPROBLEM_SOLUTION_CACHE[c_key] = (copy.deepcopy(blocks), is_fully_assigned)
            all_blocks.extend(blocks)

    # 4. Sort blocks chronologically by scheduled start and section
    all_blocks.sort(key=lambda b: (b.scheduled_start, b.section_id, b.start_km))

    # Re-index block IDs chronologically for clean output presentation
    for idx, b in enumerate(all_blocks, start=1):
        dt_prefix = b.scheduled_start[:10].replace("-", "")
        b.block_id = f"BLK-{dt_prefix}-{idx:04d}"

    # 5. Compute aggregate metrics
    total_in = len(normalized)
    total_out = len(all_blocks)
    bundled_count = sum(1 for b in all_blocks if len(b.bundled_request_ids) > 1)
    single_count = total_out - bundled_count

    total_orig_dur = sum(r["required_duration_minutes"] for r in normalized)
    total_bundled_dur = sum(b.total_duration_minutes for b in all_blocks)
    total_savings = sum(b.savings_minutes for b in all_blocks)
    savings_pct = (total_savings / total_orig_dur * 100.0) if total_orig_dur > 0 else 0.0

    # 6. Phase 8: Compute Quantitative Baseline Comparison Metrics
    baseline_halts = sum(1 for r in normalized if r.get("requires_traffic_block", True))
    optimized_halts = sum(1 for b in all_blocks if b.traffic_block_granted)
    avoided_halts = max(0, baseline_halts - optimized_halts)
    block_reduction = max(0, total_in - total_out)
    block_reduction_pct = round(block_reduction / total_in * 100.0, 2) if total_in > 0 else 0.0

    triple_bundles = sum(1 for b in all_blocks if len(b.departments_involved) >= 3)
    dual_bundles = sum(1 for b in all_blocks if len(b.departments_involved) == 2)

    baseline_comp = BaselineComparison(
        baseline_block_count=total_in,
        optimized_block_count=total_out,
        block_count_reduction=block_reduction,
        block_count_reduction_pct=block_reduction_pct,
        baseline_possession_minutes=total_orig_dur,
        baseline_possession_hours=round(total_orig_dur / 60.0, 1),
        optimized_possession_minutes=total_bundled_dur,
        optimized_possession_hours=round(total_bundled_dur / 60.0, 1),
        possession_savings_minutes=total_savings,
        possession_savings_hours=round(total_savings / 60.0, 1),
        possession_reduction_pct=round(savings_pct, 2),
        baseline_traffic_halts=baseline_halts,
        optimized_traffic_halts=optimized_halts,
        avoided_traffic_halts=avoided_halts,
        coordinated_bundles_created=bundled_count,
        triple_department_bundles=triple_bundles,
        dual_department_bundles=dual_bundles,
    )

    t_end = time.time()

    overall_status = "OPTIMAL" if all_fully_assigned else "FEASIBLE"
    if total_in > 0 and total_out == 0:
        overall_status = "INFEASIBLE"

    reopt_mode = "LOCALIZED_DELTA" if cfg.delta_mode else "FULL"

    return OptimizationResult(
        status=overall_status,
        total_requests_in=total_in,
        total_blocks_out=total_out,
        bundled_blocks_count=bundled_count,
        single_blocks_count=single_count,
        total_original_duration_minutes=total_orig_dur,
        total_bundled_duration_minutes=total_bundled_dur,
        total_savings_minutes=total_savings,
        savings_percentage=round(savings_pct, 2),
        solve_time_seconds=round(t_end - t_start, 4),
        blocks=all_blocks,
        reoptimization_mode=reopt_mode,
        delta_request_ids=delta_req_ids,
        affected_blocks_count=affected_blocks_cnt,
        baseline_comparison=baseline_comp,
    )


def calculate_baseline_schedule(requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phase 8: Computes the naive, unbundled baseline schedule where every maintenance request
    is sanctioned separately as an isolated possession block with zero cross-departmental bundling.
    """
    if not requests:
        return {
            "block_count": 0,
            "total_duration_minutes": 0,
            "total_duration_hours": 0.0,
            "traffic_halts": 0,
            "power_halts": 0,
            "total_baseline_blocks": 0,
            "total_baseline_minutes": 0,
            "total_baseline_hours": 0.0,
            "total_traffic_halts": 0,
            "total_power_blocks": 0,
            "unbundled_policy": "ISOLATED_SINGLE_REQUEST_PER_BLOCK",
            "blocks": [],
        }

    normalized = [normalize_request_dict(r) for r in requests]
    total_count = len(normalized)
    total_mins = sum(r["required_duration_minutes"] for r in normalized)
    traffic_halts = sum(1 for r in normalized if r.get("requires_traffic_block", True))
    power_blocks = sum(1 for r in normalized if r.get("requires_power_block", False))

    baseline_blocks = []
    for idx, r in enumerate(normalized, start=1):
        s_dt = r["dt_start"]
        e_dt = s_dt + timedelta(minutes=r["required_duration_minutes"])
        dt_prefix = s_dt.strftime("%Y%m%d")

        baseline_blocks.append({
            "block_id": f"BASE-{dt_prefix}-{idx:04d}",
            "request_id": r["request_id"],
            "department": r["department"],
            "section_id": r["section_id"],
            "corridor_slot": r["corridor_slot"],
            "start_km": r["chainage_start"],
            "end_km": r["chainage_end"],
            "scheduled_start": s_dt.isoformat(),
            "scheduled_end": e_dt.isoformat(),
            "total_duration_minutes": r["required_duration_minutes"],
            "work_type": r["work_type"],
            "asset_id": r.get("asset_id", ""),
            "risk_score": r.get("risk_score", 0.0),
            "requires_power_block": r.get("requires_power_block", False),
            "requires_traffic_block": r.get("requires_traffic_block", True),
            "bundled_request_ids": [r["request_id"]],
            "departments_involved": [r["department"]],
            "savings_minutes": 0,
        })

    return {
        "block_count": total_count,
        "total_duration_minutes": total_mins,
        "total_duration_hours": round(total_mins / 60.0, 1),
        "traffic_halts": traffic_halts,
        "power_halts": power_blocks,
        "total_baseline_blocks": total_count,
        "total_baseline_minutes": total_mins,
        "total_baseline_hours": round(total_mins / 60.0, 1),
        "total_traffic_halts": traffic_halts,
        "total_power_blocks": power_blocks,
        "unbundled_policy": "ISOLATED_SINGLE_REQUEST_PER_BLOCK",
        "blocks": baseline_blocks,
    }
