import os
import json
import csv
import random
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Tuple, Optional

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 1. Realistic Track Topology (8 Sections along High-Density Corridors)
SECTIONS = [
    {
        "section_id": "SEC-NDLS-TKJ",
        "name": "New Delhi - Tilak Bridge",
        "line_type": "QUADRUPLE",
        "start_station": "NDLS",
        "end_station": "TKJ",
        "start_km": 0.0,
        "end_km": 3.5,
        "max_speed_kmh": 110,
        "traffic_density_index": 1.85,
    },
    {
        "section_id": "SEC-TKJ-GZB",
        "name": "Tilak Bridge - Ghaziabad Jn",
        "line_type": "DOUBLE",
        "start_station": "TKJ",
        "end_station": "GZB",
        "start_km": 3.5,
        "end_km": 25.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.70,
    },
    {
        "section_id": "SEC-GZB-ALJN",
        "name": "Ghaziabad Jn - Aligarh Jn",
        "line_type": "DOUBLE",
        "start_station": "GZB",
        "end_station": "ALJN",
        "start_km": 25.0,
        "end_km": 131.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.60,
    },
    {
        "section_id": "SEC-ALJN-TDL",
        "name": "Aligarh Jn - Tundla Jn",
        "line_type": "DOUBLE",
        "start_station": "ALJN",
        "end_station": "TDL",
        "start_km": 131.0,
        "end_km": 205.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.55,
    },
    {
        "section_id": "SEC-TDL-CNB",
        "name": "Tundla Jn - Kanpur Central",
        "line_type": "DOUBLE",
        "start_station": "TDL",
        "end_station": "CNB",
        "start_km": 205.0,
        "end_km": 435.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.65,
    },
    {
        "section_id": "SEC-CNB-PRYJ",
        "name": "Kanpur Central - Prayagraj Jn",
        "line_type": "DOUBLE",
        "start_station": "CNB",
        "end_station": "PRYJ",
        "start_km": 435.0,
        "end_km": 629.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.50,
    },
    {
        "section_id": "SEC-PRYJ-DDU",
        "name": "Prayagraj Jn - Pt. Deen Dayal Upadhyaya Jn",
        "line_type": "DOUBLE",
        "start_station": "PRYJ",
        "end_station": "DDU",
        "start_km": 629.0,
        "end_km": 782.0,
        "max_speed_kmh": 130,
        "traffic_density_index": 1.75,
    },
    {
        "section_id": "SEC-GZB-MB",
        "name": "Ghaziabad Jn - Moradabad Jn",
        "line_type": "DOUBLE",
        "start_station": "GZB",
        "end_station": "MB",
        "start_km": 25.0,
        "end_km": 165.0,
        "max_speed_kmh": 120,
        "traffic_density_index": 1.35,
    },
]

# 2. Maintenance Work Types, Asset Categories & Characteristics per Department
DEPT_CONFIGS = {
    "ENG": {
        "legacy_primary": "TMS",
        "legacy_secondary": "COA",
        "work_types": [
            ("Track Tamping (BCM/CSM Machine)", "Ballast & Sleeper Bed", True, False, 150, 210, 1.5, 3.5),
            ("Deep Ballast Screening", "Ballast Cushion", True, True, 180, 240, 1.0, 2.5),
            ("Through Rail Renewal (TRR)", "Continuous Welded Rail", True, True, 150, 210, 1.0, 2.5),
            ("Turnout & Switch Crossing Renewal", "Turnout Assembly", True, True, 120, 180, 0.2, 0.5),
            ("Ultrasonic Flaw Detection (USFD) & Joint Rectification", "Rail Joint / Fishplate", True, False, 90, 150, 0.5, 1.5),
            ("Ballast Regulating & Track Dressing", "Ballast Track", True, False, 90, 150, 1.0, 3.0),
            ("Switch Expansion Joint (SEJ) Maintenance", "SEJ Assembly", True, False, 60, 120, 0.1, 0.3),
        ],
        "asset_prefix": "ENG-TRK",
    },
    "S&T": {
        "legacy_primary": "SMMS",
        "legacy_secondary": "COA",
        "work_types": [
            ("Point Machine Overhaul & Lubrication", "Electric Point Machine", True, False, 60, 120, 0.1, 0.4),
            ("Track Circuit Joint Impedance Bonding", "DC/Audio Track Circuit", True, False, 60, 120, 0.2, 0.8),
            ("Digital Axle Counter (DAC) Sensor Calibration", "Axle Counter Detection Point", True, False, 45, 90, 0.1, 0.3),
            ("Signal Aspect LED Lamp & Mechanism Replacement", "Color Light Signal Post", False, False, 45, 90, 0.1, 0.2),
            ("Electronic Interlocking (EI) Diagnostic & Fail-Safe Test", "Solid State Interlocking Unit", True, False, 90, 150, 0.3, 1.0),
            ("Signaling Cable Meggering & Trench Maintenance", "Underground Signaling Cable", False, False, 60, 120, 0.5, 1.5),
            ("Level Crossing Interlocking Gate Inspection", "Interlocked LC Gate Mechanism", True, False, 60, 90, 0.1, 0.3),
        ],
        "asset_prefix": "SNT-SIG",
    },
    "TRD": {
        "legacy_primary": "TDMS",
        "legacy_secondary": "COA",
        "work_types": [
            ("OHE Annual Overhaul & Contact Wire Inspection", "OHE Contact & Catenary Wire", True, True, 120, 180, 1.5, 4.0),
            ("Cantilever Assembly & Dropper Adjustment", "Cantilever Mast Assembly", True, True, 90, 150, 1.0, 2.5),
            ("OHE Insulator Washing & High-Voltage Testing", "Post & Tension Insulators", True, True, 60, 120, 1.0, 3.0),
            ("Neutral Section & Phase Break Maintenance", "PTFE Neutral Section", True, True, 90, 150, 0.2, 0.5),
            ("Tower Wagon Foot Patrolling & Current Collection Test", "Overhead Traction Line", True, True, 90, 150, 2.0, 5.0),
            ("OHE Catenary Wire Splicing & Tensioning", "Tension Spring / Regulating Equipment", True, True, 120, 180, 1.0, 2.5),
            ("Section Insulator & Isolator Switch Servicing", "OHE Track Section Isolator", True, True, 60, 120, 0.2, 0.5),
        ],
        "asset_prefix": "TRD-OHE",
    },
}

# Standard Operational Block Windows (Indian Railways daily corridor maintenance slots)
DAILY_SLOTS = [
    ("SLOT_NIGHT", 0, 30, 4, 30),     # 00:30 to 04:30 (4.0 hr night corridor, ideal for joint power+traffic block)
    ("SLOT_EARLY_MORN", 4, 30, 8, 0),  # 04:30 to 08:00 (3.5 hr dawn corridor)
    ("SLOT_MIDDAY", 11, 30, 15, 0),    # 11:30 to 15:00 (3.5 hr midday shadow block)
    ("SLOT_AFTERNOON", 15, 0, 18, 30), # 15:00 to 18:30 (3.5 hr afternoon corridor)
]

START_DATE = datetime(2026, 9, 15)
NUM_DAYS = 7

CSV_FIELDS = [
    "request_id",
    "source_system",
    "department",
    "section_id",
    "corridor_slot",
    "chainage_start",
    "chainage_end",
    "requested_window_start",
    "requested_window_end",
    "required_duration_minutes",
    "work_type",
    "asset_id",
    "asset_type",
    "asset_age_years",
    "last_maintenance_days_ago",
    "past_breakdown_count",
    "gross_million_tonnes",
    "condition_score",
    "urgency_category",
    "requires_power_block",
    "requires_traffic_block",
    "status",
]


def classify_corridor_slot(dt: datetime) -> str:
    """
    Classify a datetime into one of the 4 Indian Railways operational maintenance slots.
    Unambiguously maps window start times into designated corridor slots:
    - 00:00 to 03:59 -> SLOT_NIGHT (00:30 - 04:30)
    - 04:00 to 09:59 -> SLOT_EARLY_MORN (04:30 - 08:00)
    - 10:00 to 13:59 -> SLOT_MIDDAY (11:30 - 15:00)
    - 14:00 to 19:59 -> SLOT_AFTERNOON (15:00 - 18:30)
    """
    t = dt.time()
    if t < time(4, 0):
        return "SLOT_NIGHT"
    elif t < time(10, 0):
        return "SLOT_EARLY_MORN"
    elif t < time(14, 0):
        return "SLOT_MIDDAY"
    else:
        return "SLOT_AFTERNOON"


def generate_asset_condition_features(rng: random.Random) -> Dict[str, Any]:
    """
    Generate realistic, correlated asset condition features with high variance.
    These features drive the LightGBM/XGBoost risk scoring model in Phase 2.
    """
    profile_dice = rng.random()
    if profile_dice < 0.15:
        # High risk / Critical
        age_years = round(rng.uniform(14.0, 26.0), 1)
        last_maint_days = rng.randint(220, 365)
        past_breakdowns = rng.randint(3, 6)
        gmt = round(rng.uniform(75.0, 135.0), 1)
        condition_score = round(rng.uniform(1.2, 3.5), 1)
        urgency = "CRITICAL"
    elif profile_dice < 0.50:
        # Medium-High risk
        age_years = round(rng.uniform(7.0, 16.0), 1)
        last_maint_days = rng.randint(120, 240)
        past_breakdowns = rng.randint(1, 3)
        gmt = round(rng.uniform(40.0, 85.0), 1)
        condition_score = round(rng.uniform(3.6, 6.2), 1)
        urgency = "HIGH" if condition_score < 4.8 or past_breakdowns >= 2 else "MEDIUM"
    else:
        # Low risk / Routine
        age_years = round(rng.uniform(0.8, 8.0), 1)
        last_maint_days = rng.randint(15, 120)
        past_breakdowns = 0 if rng.random() > 0.15 else 1
        gmt = round(rng.uniform(12.0, 50.0), 1)
        condition_score = round(rng.uniform(6.3, 9.8), 1)
        urgency = "MEDIUM" if past_breakdowns > 0 or last_maint_days > 90 else "LOW"

    return {
        "asset_age_years": age_years,
        "last_maintenance_days_ago": last_maint_days,
        "past_breakdown_count": past_breakdowns,
        "gross_million_tonnes": gmt,
        "condition_score": condition_score,
        "urgency_category": urgency,
    }


def create_block_request(
    request_id: str,
    department: str,
    section: Dict[str, Any],
    corridor_slot: str,
    chainage_start: float,
    chainage_end: float,
    window_start: datetime,
    window_end: datetime,
    req_duration: int,
    work_type_info: Tuple,
    asset_seq: int,
    source_system: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """Build a unified block request record with strict boundary clamping and feature containers."""
    work_name, asset_type, req_traffic, req_power, _, _, _, _ = work_type_info
    condition = generate_asset_condition_features(rng)
    sec_id_clean = section["section_id"].replace("SEC-", "")
    asset_id = f"{DEPT_CONFIGS[department]['asset_prefix']}-{sec_id_clean}-{asset_seq:04d}"

    actual_power = True if department == "TRD" else (req_power and rng.random() > 0.4)
    actual_traffic = req_traffic

    sec_start = section["start_km"]
    sec_end = section["end_km"]
    c_start = max(sec_start, min(round(chainage_start, 2), sec_end - 0.1))
    c_end = min(sec_end, max(round(chainage_end, 2), c_start + 0.1))

    record = {
        "request_id": request_id,
        "source_system": source_system,
        "department": department,
        "section_id": section["section_id"],
        "corridor_slot": corridor_slot,
        "chainage_start": c_start,
        "chainage_end": c_end,
        "requested_window_start": window_start.isoformat(),
        "requested_window_end": window_end.isoformat(),
        "required_duration_minutes": req_duration,
        "work_type": work_name,
        "asset_id": asset_id,
        "asset_type": asset_type,
        "asset_age_years": condition["asset_age_years"],
        "last_maintenance_days_ago": condition["last_maintenance_days_ago"],
        "past_breakdown_count": condition["past_breakdown_count"],
        "gross_million_tonnes": condition["gross_million_tonnes"],
        "condition_score": condition["condition_score"],
        "urgency_category": condition["urgency_category"],
        "asset_age_or_condition_features": condition,
        "asset_condition_features": condition,
        "requires_power_block": actual_power,
        "requires_traffic_block": actual_traffic,
        "status": "PENDING",
    }
    return record


def generate_synthetic_dataset(
    target_count: int = 240,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate synthetic block requests with deliberate cross-departmental overlaps.
    Uses an isolated random.Random(seed) instance for 100% deterministic reproducibility.
    """
    rng = random.Random(seed)
    raw_records: List[Dict[str, Any]] = []
    asset_counters = {"ENG": 1, "S&T": 1, "TRD": 1}

    # Step 1: Generate Intentional Bundling Candidates (Cross-Department Overlaps)
    candidate_slots = []
    for day_offset in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)
        for sec in SECTIONS:
            for slot_id, sh, sm, eh, em in DAILY_SLOTS:
                candidate_slots.append((sec, current_date, slot_id, sh, sm, eh, em))

    rng.shuffle(candidate_slots)

    num_bundle_slots = 38
    bundle_slots_chosen = candidate_slots[:num_bundle_slots]

    for sec, current_date, slot_id, sh, sm, eh, em in bundle_slots_chosen:
        slot_start = datetime(current_date.year, current_date.month, current_date.day, sh, sm)
        if eh < sh:
            slot_end = datetime(current_date.year, current_date.month, current_date.day, eh, em) + timedelta(days=1)
        else:
            slot_end = datetime(current_date.year, current_date.month, current_date.day, eh, em)

        # 50% 2-dept (ENG+TRD), 25% 2-dept (ENG+S&T), 25% 3-dept (ENG+S&T+TRD)
        p = rng.random()
        if p < 0.50:
            depts_involved = ["ENG", "TRD"]
        elif p < 0.75:
            depts_involved = ["ENG", "S&T"]
        else:
            depts_involved = ["ENG", "S&T", "TRD"]

        sec_len = sec["end_km"] - sec["start_km"]
        max_base = max(sec["start_km"], sec["end_km"] - min(6.0, sec_len * 0.5))
        base_km = round(rng.uniform(sec["start_km"], max_base), 2)

        for dept in depts_involved:
            dept_cfg = DEPT_CONFIGS[dept]
            work_info = rng.choice(dept_cfg["work_types"])
            _, _, _, _, min_dur, max_dur, min_len, max_len = work_info

            km_span = round(rng.uniform(min_len, min(max_len, sec_len)), 2)
            c_start = max(sec["start_km"], round(base_km + rng.uniform(-0.3, 0.5), 2))
            c_end = min(sec["end_km"], round(c_start + km_span, 2))
            if c_end <= c_start:
                c_end = min(sec["end_km"], c_start + 0.2)

            offset_start = rng.choice([0, 15, 30])
            offset_end = rng.choice([0, 15, 30])
            w_start = slot_start + timedelta(minutes=offset_start)
            w_end = slot_end - timedelta(minutes=offset_end)
            if (w_end - w_start).total_seconds() < 7200:  # ensure at least 2h window
                w_start = slot_start
                w_end = slot_end

            total_window_mins = int((w_end - w_start).total_seconds() / 60)
            # Ensure 15-45 minutes of scheduling slack for CP-SAT solver
            max_feasible_dur = min(max_dur, total_window_mins - 15)
            min_feasible_dur = min(min_dur, max_feasible_dur)
            req_dur = rng.randint(min_feasible_dur, max_feasible_dur)

            source = dept_cfg["legacy_primary"] if rng.random() < 0.85 else dept_cfg["legacy_secondary"]

            raw_records.append({
                "department": dept,
                "section": sec,
                "corridor_slot": slot_id,
                "chainage_start": c_start,
                "chainage_end": c_end,
                "window_start": w_start,
                "window_end": w_end,
                "req_duration": req_dur,
                "work_type_info": work_info,
                "asset_seq": asset_counters[dept],
                "source_system": source,
            })
            asset_counters[dept] += 1

    # Step 2: Generate Independent Requests to reach target_count
    remaining_count = target_count - len(raw_records)
    for _ in range(remaining_count):
        sec = rng.choice(SECTIONS)
        dept = rng.choice(["ENG", "S&T", "TRD"])
        dept_cfg = DEPT_CONFIGS[dept]
        work_info = rng.choice(dept_cfg["work_types"])
        _, _, _, _, min_dur, max_dur, min_len, max_len = work_info

        day_offset = rng.randint(0, NUM_DAYS - 1)
        current_date = START_DATE + timedelta(days=day_offset)
        slot_id, sh, sm, eh, em = rng.choice(DAILY_SLOTS)

        slot_start = datetime(current_date.year, current_date.month, current_date.day, sh, sm)
        if eh < sh:
            slot_end = datetime(current_date.year, current_date.month, current_date.day, eh, em) + timedelta(days=1)
        else:
            slot_end = datetime(current_date.year, current_date.month, current_date.day, eh, em)

        sec_len = sec["end_km"] - sec["start_km"]
        km_span = round(rng.uniform(min_len, min(max_len, sec_len)), 2)
        c_start = round(rng.uniform(sec["start_km"], max(sec["start_km"], sec["end_km"] - km_span)), 2)
        c_end = min(sec["end_km"], round(c_start + km_span, 2))
        if c_end <= c_start:
            c_end = min(sec["end_km"], c_start + 0.2)

        offset_start = rng.choice([0, 15, 30])
        offset_end = rng.choice([0, 15, 30])
        w_start = slot_start + timedelta(minutes=offset_start)
        w_end = slot_end - timedelta(minutes=offset_end)
        if (w_end - w_start).total_seconds() < 7200:
            w_start = slot_start
            w_end = slot_end

        total_window_mins = int((w_end - w_start).total_seconds() / 60)
        max_feasible_dur = min(max_dur, total_window_mins - 15)
        min_feasible_dur = min(min_dur, max_feasible_dur)
        req_dur = rng.randint(min_feasible_dur, max_feasible_dur)

        source = dept_cfg["legacy_primary"] if rng.random() < 0.85 else dept_cfg["legacy_secondary"]

        raw_records.append({
            "department": dept,
            "section": sec,
            "corridor_slot": slot_id,
            "chainage_start": c_start,
            "chainage_end": c_end,
            "window_start": w_start,
            "window_end": w_end,
            "req_duration": req_dur,
            "work_type_info": work_info,
            "asset_seq": asset_counters[dept],
            "source_system": source,
        })
        asset_counters[dept] += 1

    # Step 3: Sort chronologically, then assign sequential request IDs
    raw_records.sort(key=lambda x: (x["window_start"], x["section"]["section_id"], x["chainage_start"]))

    requests: List[Dict[str, Any]] = []
    dept_seq_counters = {"ENG": 1, "S&T": 1, "TRD": 1}
    for item in raw_records:
        dept = item["department"]
        dept_tag = dept.replace("&", "")
        dt_str = item["window_start"].strftime("%Y%m%d")
        req_id = f"REQ-{dt_str}-{dept_tag}-{dept_seq_counters[dept]:04d}"
        dept_seq_counters[dept] += 1

        rec = create_block_request(
            request_id=req_id,
            department=dept,
            section=item["section"],
            corridor_slot=item["corridor_slot"],
            chainage_start=item["chainage_start"],
            chainage_end=item["chainage_end"],
            window_start=item["window_start"],
            window_end=item["window_end"],
            req_duration=item["req_duration"],
            work_type_info=item["work_type_info"],
            asset_seq=item["asset_seq"],
            source_system=item["source_system"],
            rng=rng,
        )
        requests.append(rec)

    analytics = compute_overlap_metrics(requests)
    return requests, analytics


def compute_overlap_metrics(requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute rigorous overlap metrics:
    1. Multi-department section+time-window slots.
    2. Pairwise temporal overlap across departments on the same section.
    3. Pairwise spatio-temporal overlaps (strict and proximity).
    4. Duration slack statistics for CP-SAT feasibility.
    """
    parsed = []
    slacks = []
    for r in requests:
        ws = datetime.fromisoformat(r["requested_window_start"])
        we = datetime.fromisoformat(r["requested_window_end"])
        window_mins = (we - ws).total_seconds() / 60
        slacks.append(window_mins - r["required_duration_minutes"])
        parsed.append({
            "record": r,
            "section_id": r["section_id"],
            "dept": r["department"],
            "ws": ws,
            "we": we,
            "cs": r["chainage_start"],
            "ce": r["chainage_end"],
            "slot": r.get("corridor_slot", classify_corridor_slot(ws)),
        })

    pairwise_temporal_overlaps = 0
    pairwise_spatiotemporal_strict = 0
    pairwise_spatiotemporal_prox = 0

    n = len(parsed)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = parsed[i], parsed[j]
            if a["section_id"] == b["section_id"] and a["dept"] != b["dept"]:
                overlap_start = max(a["ws"], b["ws"])
                overlap_end = min(a["we"], b["we"])
                if overlap_start < overlap_end:
                    pairwise_temporal_overlaps += 1
                    spatial_overlap_start = max(a["cs"], b["cs"])
                    spatial_overlap_end = min(a["ce"], b["ce"])
                    if spatial_overlap_start < spatial_overlap_end:
                        pairwise_spatiotemporal_strict += 1
                    if spatial_overlap_start <= spatial_overlap_end + 1.0:
                        pairwise_spatiotemporal_prox += 1

    slot_clusters: Dict[Tuple[str, str, str], set] = {}
    for p in parsed:
        ws = p["ws"]
        date_str = ws.strftime("%Y-%m-%d")
        slot_name = p["slot"]
        key = (p["section_id"], date_str, slot_name)
        if key not in slot_clusters:
            slot_clusters[key] = set()
        slot_clusters[key].add(p["dept"])

    multi_dept_slots_count = sum(1 for depts in slot_clusters.values() if len(depts) >= 2)
    three_dept_slots_count = sum(1 for depts in slot_clusters.values() if len(depts) == 3)

    dept_counts = {}
    for r in requests:
        dept_counts[r["department"]] = dept_counts.get(r["department"], 0) + 1

    source_counts = {}
    for r in requests:
        source_counts[r["source_system"]] = source_counts.get(r["source_system"], 0) + 1

    urgency_counts = {}
    for r in requests:
        urgency_counts[r["urgency_category"]] = urgency_counts.get(r["urgency_category"], 0) + 1

    return {
        "total_requests": len(requests),
        "multi_dept_section_time_slots": multi_dept_slots_count,
        "three_dept_section_time_slots": three_dept_slots_count,
        "total_active_slots_evaluated": len(slot_clusters),
        "pairwise_temporal_overlaps": pairwise_temporal_overlaps,
        "pairwise_spatiotemporal_strict": pairwise_spatiotemporal_strict,
        "pairwise_spatiotemporal_prox": pairwise_spatiotemporal_prox,
        "department_distribution": dept_counts,
        "source_distribution": source_counts,
        "urgency_distribution": urgency_counts,
        "avg_scheduling_slack_mins": round(sum(slacks) / len(slacks), 1) if slacks else 0.0,
        "min_scheduling_slack_mins": min(slacks) if slacks else 0.0,
        "zero_slack_count": sum(1 for s in slacks if s <= 0.0),
    }


def save_datasets(
    requests: List[Dict[str, Any]],
    output_dir: str = OUTPUT_DIR,
) -> Tuple[str, str, str, str]:
    """Save generated requests and sections to CSV and JSON in specified output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    requests_csv = os.path.join(output_dir, "maintenance_requests.csv")
    requests_json = os.path.join(output_dir, "maintenance_requests.json")
    sections_csv = os.path.join(output_dir, "sections.csv")
    sections_json = os.path.join(output_dir, "sections.json")

    # Save CSV with flat columns
    if requests:
        with open(requests_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for r in requests:
                row = {col: r[col] for col in CSV_FIELDS}
                writer.writerow(row)

    # Save JSON with nested feature container objects
    with open(requests_json, mode="w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2)

    # Save Sections
    with open(sections_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(SECTIONS[0].keys()))
        writer.writeheader()
        writer.writerows(SECTIONS)

    with open(sections_json, mode="w", encoding="utf-8") as f:
        json.dump(SECTIONS, f, indent=2)

    return requests_csv, requests_json, sections_csv, sections_json


def main():
    print("================================================================================")
    print("  RAKSHA-BLOCK: Phase 1 Synthetic Data Generation")
    print("  AI-Powered Indian Railways Maintenance Block Coordination (SIH26027)")
    print("================================================================================\n")

    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    req_csv, req_json, sec_csv, sec_json = save_datasets(requests)

    print(f"[*] Generated {metrics['total_requests']} Maintenance Block Requests across {len(SECTIONS)} Track Sections.")
    print(f"[*] Output files saved successfully to: {OUTPUT_DIR}")
    print(f"    - Requests CSV:  {req_csv}")
    print(f"    - Requests JSON: {req_json}")
    print(f"    - Sections CSV:  {sec_csv}")
    print(f"    - Sections JSON: {sec_json}\n")

    print("--------------------------------------------------------------------------------")
    print("  DATASET VERIFICATION & OVERLAP SUMMARY")
    print("--------------------------------------------------------------------------------")
    print(f"  [+] Total Requests Generated:                  {metrics['total_requests']}")
    print(f"  [+] Section + Time-Window Slots with 2+ Depts: {metrics['multi_dept_section_time_slots']} slots")
    print(f"      (Triple-Department Bundles [ENG+S&T+TRD]:  {metrics['three_dept_section_time_slots']} slots)")
    print(f"  [+] Total Active Corridor Slots Evaluated:     {metrics['total_active_slots_evaluated']} slots")
    print(f"  [+] Pairwise Temporal Overlaps (cross-dept):   {metrics['pairwise_temporal_overlaps']} pairs")
    print(f"  [+] Spatio-Temporal Overlaps (strict inters):  {metrics['pairwise_spatiotemporal_strict']} pairs")
    print(f"  [+] Spatio-Temporal Overlaps (1km proximity):  {metrics['pairwise_spatiotemporal_prox']} pairs")
    print(f"  [+] Average Scheduling Slack per Request:      {metrics['avg_scheduling_slack_mins']} minutes")
    print(f"  [+] Requests with Zero Scheduling Slack:       {metrics['zero_slack_count']}\n")

    print("  Department Distribution:")
    for dept, count in metrics["department_distribution"].items():
        print(f"    - {dept:6s}: {count:3d} ({count / metrics['total_requests'] * 100:.1f}%)")

    print("\n  Legacy System Mapping Distribution:")
    for src, count in metrics["source_distribution"].items():
        print(f"    - {src:6s}: {count:3d} ({count / metrics['total_requests'] * 100:.1f}%)")

    print("\n  Asset Urgency / Risk Tier Distribution:")
    for urg, count in metrics["urgency_distribution"].items():
        print(f"    - {urg:8s}: {count:3d} ({count / metrics['total_requests'] * 100:.1f}%)")

    print("\n--------------------------------------------------------------------------------")
    print("  SAMPLE 10 ROWS (Normalized Unified Schema)")
    print("--------------------------------------------------------------------------------")
    sample_indices = [0, 1, 2, 10, 11, 25, 50, 75, 100, 150]
    sample_rows = [requests[i] for i in sample_indices if i < len(requests)]

    header_fmt = "{:<22} {:<6} {:<5} {:<13} {:<12} {:<20} {:<10} {:<32} {:<8}"
    row_fmt    = "{:<22} {:<6} {:<5} {:<13} {:<12} {:<20} {:<10} {:<32} {:<8}"
    print(header_fmt.format("Request ID", "Source", "Dept", "Section", "Chainage", "Window Start", "Duration", "Work Type", "Urgency"))
    print("-" * 135)
    for r in sample_rows:
        chainage_str = f"{r['chainage_start']:.1f}-{r['chainage_end']:.1f}"
        w_start_str = r['requested_window_start'].replace("T", " ")
        dur_str = f"{r['required_duration_minutes']} min"
        work_str = r['work_type'][:31]
        print(row_fmt.format(
            r["request_id"],
            r["source_system"],
            r["department"],
            r["section_id"].replace("SEC-", ""),
            chainage_str,
            w_start_str,
            dur_str,
            work_str,
            r["urgency_category"],
        ))

    print("================================================================================\n")
    return requests, metrics


if __name__ == "__main__":
    main()

