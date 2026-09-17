from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Set

VALID_DEPARTMENTS: Set[str] = {"ENG", "S&T", "TRD"}
VALID_SOURCES: Set[str] = {"TMS", "SMMS", "TDMS", "COA"}
VALID_URGENCIES: Set[str] = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_CORRIDOR_SLOTS: Set[str] = {
    "SLOT_NIGHT",
    "SLOT_EARLY_MORN",
    "SLOT_MIDDAY",
    "SLOT_AFTERNOON",
}
VALID_STATUSES: Set[str] = {
    "PENDING",
    "BUNDLED",
    "SCHEDULED",
    "REJECTED",
    "COMPLETED",
}
VALID_LINE_TYPES: Set[str] = {
    "UP",
    "DOWN",
    "SINGLE",
    "COMMON",
    "DOUBLE",
    "TRIPLE",
    "QUADRUPLE",
}

REQUIRED_REQUEST_FIELDS = [
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
]

REQUIRED_SECTION_FIELDS = [
    "section_id",
    "name",
    "line_type",
    "start_station",
    "end_station",
    "start_km",
    "end_km",
    "max_speed_kmh",
    "traffic_density_index",
]


def _parse_bool(val: Any) -> Tuple[bool, bool]:
    """
    Parse a boolean value.
    Returns (is_valid, parsed_bool).
    """
    if isinstance(val, bool):
        return True, val
    if isinstance(val, (int, float)):
        if val in (0, 1):
            return True, bool(val)
        return False, False
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in {"true", "1", "yes", "t"}:
            return True, True
        if cleaned in {"false", "0", "no", "f"}:
            return True, False
    return False, False


def _parse_int(val: Any) -> int:
    """Safely parse integer from int, float, or string (including '120.0')."""
    return int(float(val))


def _parse_datetime(val: Any) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val_clean = val.strip().replace("Z", "")
        try:
            return datetime.fromisoformat(val_clean)
        except ValueError:
            return None
    return None


def validate_section(raw: Dict[str, Any]) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
    """Validate and normalize a track topology section row."""
    errors: List[str] = []

    # 1. Missing required fields
    for field in REQUIRED_SECTION_FIELDS:
        val = raw.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return False, errors, None

    line_type = str(raw["line_type"]).strip().upper()
    if line_type not in VALID_LINE_TYPES:
        errors.append(f"Invalid line_type '{line_type}'. Expected one of {sorted(VALID_LINE_TYPES)}")

    try:
        start_km = float(raw["start_km"])
        end_km = float(raw["end_km"])
        max_speed = _parse_int(raw["max_speed_kmh"])
        traffic_idx = float(raw["traffic_density_index"])
    except (ValueError, TypeError) as e:
        errors.append(f"Numeric type parsing error in section: {e}")
        return False, errors, None

    if start_km < 0:
        errors.append(f"start_km ({start_km}) cannot be negative")
    if start_km >= end_km:
        errors.append(f"start_km ({start_km}) must be strictly less than end_km ({end_km})")
    if max_speed <= 0:
        errors.append(f"max_speed_kmh ({max_speed}) must be positive")
    if traffic_idx <= 0:
        errors.append(f"traffic_density_index ({traffic_idx}) must be positive")

    if errors:
        return False, errors, None

    normalized = {
        "section_id": str(raw["section_id"]).strip(),
        "name": str(raw["name"]).strip(),
        "line_type": line_type,
        "start_station": str(raw["start_station"]).strip(),
        "end_station": str(raw["end_station"]).strip(),
        "start_km": start_km,
        "end_km": end_km,
        "max_speed_kmh": max_speed,
        "traffic_density_index": traffic_idx,
    }
    return True, [], normalized


def validate_maintenance_request(
    raw: Dict[str, Any],
    known_section_ids: Optional[Set[str]] = None,
    known_sections: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
    """
    Validate and normalize a maintenance block request row.
    Catches missing required fields and obviously broken synthetic records.
    """
    errors: List[str] = []

    # 1. Check missing or blank required fields
    for field in REQUIRED_REQUEST_FIELDS:
        val = raw.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return False, errors, None

    # 2. Check categorical domains
    dept = str(raw.get("department", "")).strip()
    if dept not in VALID_DEPARTMENTS:
        errors.append(f"Invalid department '{dept}'. Expected one of {sorted(VALID_DEPARTMENTS)}")

    src = str(raw.get("source_system", "")).strip()
    if src not in VALID_SOURCES:
        errors.append(f"Invalid source_system '{src}'. Expected one of {sorted(VALID_SOURCES)}")

    urgency = str(raw.get("urgency_category", "")).strip()
    if urgency not in VALID_URGENCIES:
        errors.append(f"Invalid urgency_category '{urgency}'. Expected one of {sorted(VALID_URGENCIES)}")

    slot = str(raw.get("corridor_slot", "")).strip()
    if slot not in VALID_CORRIDOR_SLOTS:
        errors.append(f"Invalid corridor_slot '{slot}'. Expected one of {sorted(VALID_CORRIDOR_SLOTS)}")

    status_raw = raw.get("status", "PENDING")
    status_val = str(status_raw).strip() if status_raw is not None else "PENDING"
    if not status_val:
        status_val = "PENDING"
    if status_val not in VALID_STATUSES:
        errors.append(f"Invalid status '{status_val}'. Expected one of {sorted(VALID_STATUSES)}")

    # Check booleans
    valid_pb, pb_val = _parse_bool(raw.get("requires_power_block"))
    if not valid_pb:
        errors.append(f"Invalid boolean value for 'requires_power_block': '{raw.get('requires_power_block')}'")

    valid_tb, tb_val = _parse_bool(raw.get("requires_traffic_block"))
    if not valid_tb:
        errors.append(f"Invalid boolean value for 'requires_traffic_block': '{raw.get('requires_traffic_block')}'")

    sec_id = str(raw.get("section_id", "")).strip()
    target_known_ids = None
    if known_sections is not None:
        target_known_ids = set(known_sections.keys())
    elif known_section_ids is not None:
        target_known_ids = known_section_ids

    if target_known_ids is not None and sec_id not in target_known_ids:
        errors.append(f"Referenced section_id '{sec_id}' does not exist in track topology")

    # 3. Numeric parsing & sanity
    try:
        c_start = float(raw["chainage_start"])
        c_end = float(raw["chainage_end"])
        duration = _parse_int(raw["required_duration_minutes"])
        age = float(raw["asset_age_years"])
        last_maint = _parse_int(raw["last_maintenance_days_ago"])
        breakdowns = _parse_int(raw["past_breakdown_count"])
        gmt = float(raw["gross_million_tonnes"])
        cond_score = float(raw["condition_score"])
    except (ValueError, TypeError) as e:
        errors.append(f"Numeric field type conversion error: {e}")
        return False, errors, None

    if c_start < 0:
        errors.append(f"chainage_start ({c_start}) cannot be negative")
    if c_start >= c_end:
        errors.append(f"chainage_start ({c_start}) must be strictly less than chainage_end ({c_end})")
    if duration <= 0:
        errors.append(f"required_duration_minutes ({duration}) must be positive")
    if age < 0:
        errors.append(f"asset_age_years ({age}) cannot be negative")
    if last_maint < 0:
        errors.append(f"last_maintenance_days_ago ({last_maint}) cannot be negative")
    if breakdowns < 0:
        errors.append(f"past_breakdown_count ({breakdowns}) cannot be negative")
    if gmt < 0:
        errors.append(f"gross_million_tonnes ({gmt}) cannot be negative")
    if cond_score < 1.0 or cond_score > 10.0:
        errors.append(f"condition_score ({cond_score}) must be between 1.0 and 10.0")

    # Section boundary check if section topology details are provided
    if known_sections is not None and sec_id in known_sections:
        sec_info = known_sections[sec_id]
        sec_start = getattr(sec_info, "start_km", None)
        if sec_start is None and isinstance(sec_info, dict):
            sec_start = sec_info.get("start_km")
        sec_end = getattr(sec_info, "end_km", None)
        if sec_end is None and isinstance(sec_info, dict):
            sec_end = sec_info.get("end_km")

        if sec_start is not None and c_start < float(sec_start):
            errors.append(f"chainage_start ({c_start}) is before section start_km ({sec_start})")
        if sec_end is not None and c_end > float(sec_end):
            errors.append(f"chainage_end ({c_end}) exceeds section end_km ({sec_end})")

    # 4. Datetime parsing & window validation
    w_start = _parse_datetime(raw.get("requested_window_start"))
    w_end = _parse_datetime(raw.get("requested_window_end"))

    if not w_start:
        errors.append(f"Invalid or unparseable requested_window_start: {raw.get('requested_window_start')}")
    if not w_end:
        errors.append(f"Invalid or unparseable requested_window_end: {raw.get('requested_window_end')}")

    if w_start and w_end:
        dt_start = w_start.replace(tzinfo=None) if w_start.tzinfo else w_start
        dt_end = w_end.replace(tzinfo=None) if w_end.tzinfo else w_end
        if dt_start >= dt_end:
            errors.append(f"requested_window_start ({w_start}) must precede requested_window_end ({w_end})")
        else:
            total_window_mins = (dt_end - dt_start).total_seconds() / 60.0
            if duration > total_window_mins:
                errors.append(
                    f"required_duration_minutes ({duration}) exceeds requested window ({total_window_mins:.1f} mins)"
                )

    # Optional risk_score parsing
    raw_risk = raw.get("risk_score")
    parsed_risk = None
    if raw_risk is not None and str(raw_risk).strip() != "":
        try:
            parsed_risk = round(float(raw_risk), 2)
            if parsed_risk < 0.0 or parsed_risk > 100.0:
                errors.append(f"risk_score ({parsed_risk}) must be between 0.0 and 100.0")
        except ValueError:
            errors.append(f"Invalid risk_score value: {raw_risk}")

    if errors:
        return False, errors, None

    # 5. Build canonical feature container
    cond_features = raw.get("asset_age_or_condition_features")
    if not isinstance(cond_features, dict):
        cond_features = raw.get("asset_condition_features")
    if not isinstance(cond_features, dict):
        cond_features = {
            "asset_age_years": age,
            "last_maintenance_days_ago": last_maint,
            "past_breakdown_count": breakdowns,
            "gross_million_tonnes": gmt,
            "condition_score": cond_score,
            "urgency_category": urgency,
        }
    else:
        cond_features = {
            "asset_age_years": float(cond_features.get("asset_age_years", age)),
            "last_maintenance_days_ago": _parse_int(cond_features.get("last_maintenance_days_ago", last_maint)),
            "past_breakdown_count": _parse_int(cond_features.get("past_breakdown_count", breakdowns)),
            "gross_million_tonnes": float(cond_features.get("gross_million_tonnes", gmt)),
            "condition_score": float(cond_features.get("condition_score", cond_score)),
            "urgency_category": str(cond_features.get("urgency_category", urgency)),
        }

    normalized = {
        "request_id": str(raw["request_id"]).strip(),
        "source_system": src,
        "department": dept,
        "section_id": sec_id,
        "corridor_slot": slot,
        "chainage_start": round(c_start, 2),
        "chainage_end": round(c_end, 2),
        "requested_window_start": w_start,
        "requested_window_end": w_end,
        "required_duration_minutes": duration,
        "work_type": str(raw["work_type"]).strip(),
        "asset_id": str(raw["asset_id"]).strip(),
        "asset_type": str(raw["asset_type"]).strip(),
        "asset_age_years": age,
        "last_maintenance_days_ago": last_maint,
        "past_breakdown_count": breakdowns,
        "gross_million_tonnes": gmt,
        "condition_score": cond_score,
        "urgency_category": urgency,
        "asset_age_or_condition_features": cond_features,
        "asset_condition_features": cond_features,
        "risk_score": parsed_risk,
        "requires_power_block": pb_val,
        "requires_traffic_block": tb_val,
        "status": status_val,
    }

    return True, [], normalized
