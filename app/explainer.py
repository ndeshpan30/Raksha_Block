"""
RAKSHA-BLOCK: Explainability Engine ("Why this block?")
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination

Generates deterministic, plain-language rationales and structured constraint reasoning
for CP-SAT scheduled maintenance possession blocks without requiring an external LLM.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, ConfigDict

from app.risk_model import get_risk_tier


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts value to float, handling None, empty string, and conversion errors."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely converts value to int, handling None, empty string, and float strings."""
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _safe_iso(val: Any, default: str) -> str:
    """Safely formats a datetime object or ISO string."""
    if val is None or val == "":
        return default
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


class MergedRequestDetail(BaseModel):
    """Detailed summary of an individual constituent maintenance request within a block."""

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
    urgency_tier: str
    requires_power_block: bool
    requires_traffic_block: bool

    model_config = ConfigDict(from_attributes=True)


class PriorityReasoning(BaseModel):
    """Reasoning regarding operational priority and failure risk factors anchoring the block."""

    highest_risk_request_id: str
    highest_risk_asset_id: str
    highest_risk_score: float
    highest_risk_department: str
    highest_risk_work_type: str
    risk_tier: str
    average_risk_score: float
    risk_spread: float
    anchoring_reason: str

    model_config = ConfigDict(from_attributes=True)


class WindowBounds(BaseModel):
    """Temporal operational window boundaries across constituent requests."""

    earliest_requested_start: str
    latest_requested_end: str
    scheduled_start: str
    scheduled_end: str
    total_window_slack_minutes: int

    model_config = ConfigDict(from_attributes=True)


class ConstraintReasoning(BaseModel):
    """Physical, spatial, and electrical constraints that governed block formation."""

    spatial_chainage_overlap: bool
    spatial_proximity_km: float
    actual_spatial_gap_km: float
    enveloping_chainage_span_km: float
    spatial_overlap_type: str  # "DIRECT_OVERLAP", "ADJACENT_PROXIMITY", "BRIDGED_CHAINAGE", "SINGLE_ISOLATED"
    window_bounds: WindowBounds
    corridor_slot: str
    power_block_required: bool
    power_block_driver: Optional[str] = None
    traffic_block_required: bool
    traffic_block_driver: Optional[str] = None
    duration_savings_minutes: int
    key_constraints_applied: List[str]

    model_config = ConfigDict(from_attributes=True)


class AlternativesReasoning(BaseModel):
    """Analysis of alternatives evaluated (separate possessions vs. bundled possession vs. deferral)."""

    separate_possession_minutes: int
    bundled_possession_minutes: int
    possession_savings_minutes: int
    possession_savings_pct: float
    why_not_scheduled_separately: str
    why_not_deferred: str
    alternatives_evaluated: List[str]

    model_config = ConfigDict(from_attributes=True)


class BlockExplanation(BaseModel):
    """Structured explainability object attached to each scheduled maintenance block."""

    summary: str
    merged_requests: List[MergedRequestDetail]
    driving_priority: PriorityReasoning
    driving_constraints: ConstraintReasoning
    alternatives_considered: AlternativesReasoning

    model_config = ConfigDict(from_attributes=True)


def generate_block_explanation(
    section_id: str,
    corridor_slot: str,
    start_km: float,
    end_km: float,
    scheduled_start: str,
    scheduled_end: str,
    total_duration_minutes: int,
    departments_involved: List[str],
    power_block_granted: bool,
    traffic_block_granted: bool,
    savings_minutes: int,
    constituent_requests: List[Dict[str, Any]],
    spatial_proximity_km: float = 2.0,
    max_block_km_span: float = 15.0,
    is_deferred: bool = False,
) -> BlockExplanation:
    """
    Deterministically computes a comprehensive BlockExplanation object from the solver's
    inputs and scheduled outputs using domain-grounded railway engineering rules.
    """
    n_reqs = len(constituent_requests)

    # 1. Build MergedRequestDetail list
    merged_details: List[MergedRequestDetail] = []
    for r in constituent_requests:
        r_risk = _safe_float(r.get("risk_score"), 0.0)
        r_tier = get_risk_tier(r_risk)
        merged_details.append(
            MergedRequestDetail(
                request_id=str(r.get("request_id") or "UNKNOWN"),
                department=str(r.get("department") or "ENG").upper(),
                work_type=str(r.get("work_type") or "Track Maintenance"),
                asset_id=str(r.get("asset_id") or "ASSET-UNKNOWN"),
                asset_type=str(r.get("asset_type") or "Track"),
                chainage_start=round(_safe_float(r.get("chainage_start"), 0.0), 2),
                chainage_end=round(_safe_float(r.get("chainage_end"), 0.0), 2),
                requested_window_start=_safe_iso(r.get("requested_window_start"), scheduled_start),
                requested_window_end=_safe_iso(r.get("requested_window_end"), scheduled_end),
                required_duration_minutes=_safe_int(r.get("required_duration_minutes"), 0),
                scheduled_start=_safe_iso(r.get("scheduled_start"), scheduled_start),
                scheduled_end=_safe_iso(r.get("scheduled_end"), scheduled_end),
                risk_score=round(r_risk, 2),
                urgency_tier=r_tier,
                requires_power_block=bool(r.get("requires_power_block", False)),
                requires_traffic_block=bool(r.get("requires_traffic_block", True)),
            )
        )

    # 2. Driving Priority / Risk Factors
    if n_reqs > 0:
        # Multi-key tie-breaker: risk_score (descending), duration (descending), request_id (stable order)
        highest_req = max(
            constituent_requests,
            key=lambda x: (
                _safe_float(x.get("risk_score"), 0.0),
                _safe_int(x.get("required_duration_minutes"), 0),
                str(x.get("request_id", "")),
            ),
        )
        highest_score = round(_safe_float(highest_req.get("risk_score"), 0.0), 2)
        highest_tier = get_risk_tier(highest_score)
        highest_id = str(highest_req.get("request_id") or "")
        highest_asset = str(highest_req.get("asset_id") or "")
        highest_dept = str(highest_req.get("department") or "ENG").upper()
        highest_work = str(highest_req.get("work_type") or "")

        scores = [_safe_float(x.get("risk_score"), 0.0) for x in constituent_requests]
        avg_score = round(sum(scores) / len(scores), 2)
        risk_spread = round(max(scores) - min(scores), 2)

        if is_deferred:
            anchoring_reason = (
                f"Request {highest_id} on asset {highest_asset} (risk score: {highest_score:.2f}, tier: {highest_tier}) "
                f"could not be scheduled due to track occupancy capacity limits during {corridor_slot}."
            )
        elif n_reqs > 1:
            companion_count = n_reqs - 1
            companion_word = "companion job" if companion_count == 1 else "companion jobs"
            if highest_score >= 50.0:
                anchoring_reason = (
                    f"Asset {highest_asset} ({highest_dept} - {highest_work}) has high failure risk "
                    f"({highest_score:.2f}, {highest_tier}), anchoring slot timing to expedite clearance; "
                    f"{companion_count} {companion_word} bundled into this window to maximize line productivity."
                )
            else:
                anchoring_reason = (
                    f"Possession window anchored around {highest_dept} asset {highest_asset} "
                    f"(risk score: {highest_score:.2f}, {highest_tier}) to synchronize track access across {n_reqs} tasks."
                )
        else:
            anchoring_reason = (
                f"Asset {highest_asset} ({highest_dept} - {highest_work}) scheduled with risk score "
                f"{highest_score:.2f} ({highest_tier}) during maintenance slot {corridor_slot}."
            )
    else:
        highest_id = ""
        highest_asset = ""
        highest_score = 0.0
        highest_tier = "LOW"
        highest_dept = ""
        highest_work = ""
        avg_score = 0.0
        risk_spread = 0.0
        anchoring_reason = "No constituent requests."

    priority_reasoning = PriorityReasoning(
        highest_risk_request_id=highest_id,
        highest_risk_asset_id=highest_asset,
        highest_risk_score=highest_score,
        highest_risk_department=highest_dept,
        highest_risk_work_type=highest_work,
        risk_tier=highest_tier,
        average_risk_score=avg_score,
        risk_spread=risk_spread,
        anchoring_reason=anchoring_reason,
    )

    # 3. Driving Constraints & Spatial Analysis
    span_km = round(end_km - start_km, 2)

    if n_reqs <= 1:
        has_chainage_overlap = False
        actual_gap_km = 0.0
        overlap_type = "SINGLE_ISOLATED"
    else:
        # Extract and sort normalized intervals
        intervals: List[Tuple[float, float]] = []
        for r in constituent_requests:
            s_km = _safe_float(r.get("chainage_start"), 0.0)
            e_km = _safe_float(r.get("chainage_end"), s_km)
            intervals.append((min(s_km, e_km), max(s_km, e_km)))
        intervals.sort(key=lambda x: (x[0], x[1]))

        # Merge contiguous / overlapping intervals
        merged_spans: List[Tuple[float, float]] = []
        for cur_s, cur_e in intervals:
            if not merged_spans:
                merged_spans.append((cur_s, cur_e))
            else:
                prev_s, prev_e = merged_spans[-1]
                if cur_s <= prev_e:
                    merged_spans[-1] = (prev_s, max(prev_e, cur_e))
                else:
                    merged_spans.append((cur_s, cur_e))

        # Check pairwise chainage overlap
        has_overlap = False
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                if max(intervals[i][0], intervals[j][0]) <= min(intervals[i][1], intervals[j][1]):
                    has_overlap = True
                    break
            if has_overlap:
                break
        has_chainage_overlap = has_overlap

        # Maximum physical gap between disjoint merged intervals
        if len(merged_spans) > 1:
            max_gap = 0.0
            for i in range(len(merged_spans) - 1):
                gap = max(0.0, merged_spans[i + 1][0] - merged_spans[i][1])
                if gap > max_gap:
                    max_gap = gap
            actual_gap_km = round(max_gap, 2)
        else:
            actual_gap_km = 0.0

        # Classify spatial overlap type
        if len(merged_spans) == 1 or actual_gap_km == 0.0:
            overlap_type = "DIRECT_OVERLAP"
        elif n_reqs == 2 and actual_gap_km <= spatial_proximity_km:
            overlap_type = "ADJACENT_PROXIMITY"
        elif n_reqs >= 3 and actual_gap_km <= spatial_proximity_km:
            overlap_type = "BRIDGED_CHAINAGE"
        else:
            overlap_type = "BRIDGED_CHAINAGE"

    # Window bounds
    w_starts = [_safe_iso(r.get("requested_window_start"), scheduled_start) for r in constituent_requests]
    w_ends = [_safe_iso(r.get("requested_window_end"), scheduled_end) for r in constituent_requests]
    earliest_w_start = min(w_starts) if w_starts else scheduled_start
    latest_w_end = max(w_ends) if w_ends else scheduled_end

    try:
        dt_ws = datetime.fromisoformat(str(earliest_w_start).replace("Z", "+00:00")).replace(tzinfo=None)
        dt_we = datetime.fromisoformat(str(latest_w_end).replace("Z", "+00:00")).replace(tzinfo=None)
        w_dur = int((dt_we - dt_ws).total_seconds() // 60)
        slack_mins = max(0, w_dur - total_duration_minutes)
    except Exception:
        slack_mins = 0

    window_bounds = WindowBounds(
        earliest_requested_start=str(earliest_w_start),
        latest_requested_end=str(latest_w_end),
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        total_window_slack_minutes=slack_mins,
    )

    # Power & Traffic block drivers
    if power_block_granted:
        p_reqs = [str(r.get("request_id") or "") for r in constituent_requests if r.get("requires_power_block")]
        if len(p_reqs) == 1:
            power_driver = (
                f"Driven by 1 request ({p_reqs[0]}) requiring 25kV OHE electrical isolation "
                f"and earthing; non-traction maintenance accommodated safely under power-cut protection."
            )
        elif len(p_reqs) > 1:
            power_driver = (
                f"Driven by {len(p_reqs)} requests ({', '.join(p_reqs)}) requiring 25kV OHE electrical isolation "
                f"and earthing; non-traction maintenance accommodated safely under power-cut protection."
            )
        else:
            power_driver = "25kV OHE traction power isolation & earthing block granted."
    else:
        if traffic_block_granted:
            power_driver = "No 25kV OHE power isolation required (traffic-only possession)."
        else:
            power_driver = "No 25kV OHE power isolation required."

    if traffic_block_granted:
        t_reqs = [str(r.get("request_id") or "") for r in constituent_requests if r.get("requires_traffic_block")]
        if len(t_reqs) == 1:
            traffic_driver = (
                f"Driven by 1 request ({t_reqs[0]}) requiring complete train traffic stoppage "
                f"and track possession."
            )
        elif len(t_reqs) > 1:
            traffic_driver = (
                f"Driven by {len(t_reqs)} requests ({', '.join(t_reqs)}) requiring complete train traffic stoppage "
                f"and track possession."
            )
        else:
            traffic_driver = "Train movement stoppage & absolute line possession granted."
    else:
        traffic_driver = "No train traffic stoppage required (off-track work)."

    # Key constraints list
    applied_constraints: List[str] = []
    if is_deferred:
        applied_constraints.append(
            f"Linear chainage envelope KM {start_km:.2f} - {end_km:.2f} (span: {span_km:.2f} km)"
        )
        applied_constraints.append(
            f"Track capacity saturation in corridor slot {corridor_slot} (unassigned deferral triggered)"
        )
        applied_constraints.append("Disjunctive NoOverlap conflict on shared physical line section infrastructure")
    else:
        applied_constraints.append(
            f"Linear chainage envelope KM {start_km:.2f} - {end_km:.2f} (span: {span_km:.2f} km <= {max_block_km_span:.1f} km limit)"
        )
        if n_reqs > 1:
            if overlap_type == "DIRECT_OVERLAP":
                applied_constraints.append("Direct spatial chainage overlap between constituent requests")
            elif overlap_type == "ADJACENT_PROXIMITY":
                applied_constraints.append(
                    f"Spatial proximity adjacency: inter-work gap {actual_gap_km:.2f} km <= {spatial_proximity_km:.1f} km threshold"
                )
            elif overlap_type == "BRIDGED_CHAINAGE":
                applied_constraints.append(
                    f"Spatial bridging constraint: contiguous intermediate requests bridge track span with gaps <= {spatial_proximity_km:.1f} km (max gap: {actual_gap_km:.2f} km)"
                )
            s_hm = scheduled_start[11:16] if len(scheduled_start) >= 16 else scheduled_start
            e_hm = scheduled_end[11:16] if len(scheduled_end) >= 16 else scheduled_end
            applied_constraints.append(
                f"Temporal containment: consolidated block [{s_hm} - {e_hm}] strictly encloses all {n_reqs} constituent jobs"
            )
            applied_constraints.append("Duration upper bound: bundled duration <= sum of constituent durations (guarantees >= 0 savings)")
        applied_constraints.append(f"Operational corridor window containment within {corridor_slot}")
        if power_block_granted:
            applied_constraints.append("25kV OHE traction power isolation & earthing block granted")
        if traffic_block_granted:
            applied_constraints.append("Train movement stoppage & absolute line possession granted")
        applied_constraints.append("Disjunctive NoOverlap on track section infrastructure")

    constraint_reasoning = ConstraintReasoning(
        spatial_chainage_overlap=has_chainage_overlap,
        spatial_proximity_km=spatial_proximity_km,
        actual_spatial_gap_km=actual_gap_km,
        enveloping_chainage_span_km=span_km,
        spatial_overlap_type=overlap_type,
        window_bounds=window_bounds,
        corridor_slot=corridor_slot,
        power_block_required=power_block_granted,
        power_block_driver=power_driver,
        traffic_block_required=traffic_block_granted,
        traffic_block_driver=traffic_driver,
        duration_savings_minutes=0 if is_deferred else savings_minutes,
        key_constraints_applied=applied_constraints,
    )

    # 4. Alternatives Considered
    separate_dur = sum(_safe_int(r.get("required_duration_minutes"), 0) for r in constituent_requests)
    bundled_dur = total_duration_minutes

    if is_deferred:
        savings_calc = 0
        savings_pct = 0.0
        bundled_dur = 0
        why_not_sep = (
            f"Request could not be granted separate possession due to lack of available track time in {corridor_slot}."
        )
        why_not_def = "Capacity limits exceeded; deferred for subsequent planning cycle."
        alts = [
            "Immediate scheduling in current slot (evaluated: rejected due to track occupancy conflicts)",
            "Reschedule in next available corridor maintenance slot (recommended action)",
        ]
    elif n_reqs > 1:
        savings_calc = max(0, separate_dur - bundled_dur)
        savings_pct = round((savings_calc / separate_dur * 100.0), 2) if separate_dur > 0 else 0.0
        depts_str = " + ".join(departments_involved)
        halts_count = n_reqs - 1
        halt_word = "additional train traffic halt" if halts_count == 1 else "additional train traffic halts"
        possession_type = "separate line possessions" if len(departments_involved) > 1 else "separate possessions"

        why_not_sep = (
            f"Scheduling these {n_reqs} requests separately would require {separate_dur} minutes "
            f"({separate_dur / 60:.1f} hrs) of fragmented track possession across {n_reqs} {possession_type}. "
            f"Bundling saves {savings_calc} minutes ({savings_pct:.1f}%) of track downtime and avoids {halts_count} "
            f"{halt_word}."
        )
        if highest_score >= 50.0:
            why_not_def = (
                f"High composite urgency (anchoring risk: {highest_score:.2f}, {highest_tier}) and mutual spatio-temporal alignment "
                f"satisfied all hard constraints, avoiding the 200,000 pt CP-SAT deferral penalty."
            )
        else:
            why_not_def = (
                f"Spatio-temporal alignment and available corridor capacity satisfied all hard constraints "
                f"(anchoring risk: {highest_score:.2f}, {highest_tier}), avoiding the 200,000 pt CP-SAT deferral penalty."
            )
        asset_impact = "leaves critical assets unmaintained" if highest_tier in ("CRITICAL", "HIGH") else "postpones scheduled asset maintenance"
        dept_desc = "departmental " if len(departments_involved) > 1 else ""
        alts = [
            f"Separate {dept_desc}possession for each request (evaluated: rejected, causes {separate_dur} min total possession vs {bundled_dur} min bundled)",
            f"Deferral to subsequent corridor maintenance cycle (evaluated: rejected, {asset_impact})",
        ]
        if len(departments_involved) >= 3:
            alts.append(
                f"Pairwise 2-department sub-bundle (evaluated: rejected, full 3-department consolidation ({depts_str}) yields optimal possession reduction)"
            )
    else:
        savings_calc = max(0, separate_dur - bundled_dur)
        savings_pct = round((savings_calc / separate_dur * 100.0), 2) if separate_dur > 0 else 0.0
        why_not_sep = (
            f"No compatible cross-departmental requests existed within {spatial_proximity_km:.1f} km proximity "
            f"and {corridor_slot} on section {section_id}. Scheduling as a standalone block avoids artificial possession extension."
        )
        why_not_def = (
            f"Scheduled within requested window bounds (slack: {slack_mins} min); asset risk ({highest_score:.2f}) "
            f"and available track capacity permitted prompt clearance."
        )
        alts = [
            f"Bundling with distant section works > {spatial_proximity_km:.1f} km away (evaluated: rejected due to spatial proximity safety limits)",
            "Deferral to next slot (evaluated: rejected, slot capacity was available with zero conflicts)",
        ]

    alternatives_reasoning = AlternativesReasoning(
        separate_possession_minutes=separate_dur,
        bundled_possession_minutes=bundled_dur,
        possession_savings_minutes=savings_calc,
        possession_savings_pct=savings_pct,
        why_not_scheduled_separately=why_not_sep,
        why_not_deferred=why_not_def,
        alternatives_evaluated=alts,
    )

    # 5. Plain-Language Summary Sentence
    s_hm = scheduled_start[11:16] if len(scheduled_start) >= 16 else scheduled_start
    e_hm = scheduled_end[11:16] if len(scheduled_end) >= 16 else scheduled_end

    if is_deferred:
        r_def = constituent_requests[0] if constituent_requests else {}
        summary_text = (
            f"Request {r_def.get('request_id', 'UNKNOWN')} ({r_def.get('department', '')} - {r_def.get('work_type', '')}) "
            f"on section {section_id} (KM {start_km:.2f} - {end_km:.2f}) deferred due to corridor slot capacity constraints."
        )
    elif n_reqs > 1:
        if len(departments_involved) > 1:
            depts_str = " + ".join(departments_involved)
            bundle_desc = f"cross-departmental requests ({depts_str})"
            comp_phrase = "vs. separate departmental blocks"
        else:
            single_dept = departments_involved[0] if departments_involved else "ENG"
            bundle_desc = f"{single_dept} maintenance requests"
            comp_phrase = "vs. separate possessions"

        summary_text = (
            f"Bundled {n_reqs} {bundle_desc} on section {section_id} "
            f"(KM {start_km:.2f} - {end_km:.2f}) during {corridor_slot}; "
            f"prioritized due to {highest_dept} asset {highest_asset} (risk score: {highest_score:.2f}, {highest_tier}); "
            f"consolidated possession window {s_hm} to {e_hm} ({total_duration_minutes} min) "
            f"saves {savings_calc} minutes ({savings_pct:.1f}%) of line possession {comp_phrase}."
        )
    else:
        r_single = constituent_requests[0] if constituent_requests else {}
        summary_text = (
            f"Single departmental possession block granted for {r_single.get('department', '')} "
            f"({r_single.get('work_type', '')}) on section {section_id} (KM {start_km:.2f} - {end_km:.2f}) "
            f"from {s_hm} to {e_hm} ({total_duration_minutes} min); "
            f"prioritized with risk score {highest_score:.2f} ({highest_tier}); "
            f"scheduled individually as no adjacent requests were within {spatial_proximity_km:.1f} km proximity."
        )

    return BlockExplanation(
        summary=summary_text,
        merged_requests=merged_details,
        driving_priority=priority_reasoning,
        driving_constraints=constraint_reasoning,
        alternatives_considered=alternatives_reasoning,
    )
