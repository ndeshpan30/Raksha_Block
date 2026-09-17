import os
import csv
import json
import pytest
from datetime import datetime
from scripts.generate_synthetic_data import (
    generate_synthetic_dataset,
    save_datasets,
    classify_corridor_slot,
    SECTIONS,
    OUTPUT_DIR,
)


def test_sections_integrity():
    assert 5 <= len(SECTIONS) <= 10
    for s in SECTIONS:
        assert "section_id" in s
        assert "start_km" in s
        assert "end_km" in s
        assert s["start_km"] < s["end_km"]
        assert s["max_speed_kmh"] > 0
        assert s["traffic_density_index"] > 0


def test_dataset_generation_row_count():
    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    assert len(requests) == 240
    assert metrics["total_requests"] == 240
    assert 150 <= len(requests) <= 300


def test_deterministic_reproducibility():
    reqs_1, metrics_1 = generate_synthetic_dataset(target_count=60, seed=123)
    reqs_2, metrics_2 = generate_synthetic_dataset(target_count=60, seed=123)
    assert reqs_1 == reqs_2
    assert metrics_1 == metrics_2


def test_unified_schema_fields_present():
    requests, _ = generate_synthetic_dataset(target_count=50, seed=42)
    required_fields = [
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
        "asset_age_or_condition_features",
        "asset_condition_features",
        "requires_power_block",
        "requires_traffic_block",
        "status",
    ]
    for r in requests:
        for field in required_fields:
            assert field in r, f"Field {field} missing from request {r.get('request_id')}"

        # Verify condition feature container dictionary
        cond = r["asset_age_or_condition_features"]
        assert isinstance(cond, dict)
        assert "asset_age_years" in cond
        assert "condition_score" in cond
        assert "urgency_category" in cond


def test_departments_and_sources():
    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    valid_depts = {"ENG", "S&T", "TRD"}
    valid_sources = {"TMS", "SMMS", "TDMS", "COA"}

    for r in requests:
        assert r["department"] in valid_depts
        assert r["source_system"] in valid_sources

    # Confirm all 3 departments and all 4 legacy sources are present
    assert set(metrics["department_distribution"].keys()) == valid_depts
    assert set(metrics["source_distribution"].keys()) == valid_sources


def test_slot_classification_logic():
    # Verify accurate binning without boundary regressions
    night_dt = datetime(2026, 9, 15, 0, 30)
    early_dt_1 = datetime(2026, 9, 15, 4, 30)
    early_dt_2 = datetime(2026, 9, 15, 4, 45)
    early_dt_3 = datetime(2026, 9, 15, 5, 15)
    midday_dt = datetime(2026, 9, 15, 11, 30)
    afternoon_dt = datetime(2026, 9, 15, 15, 15)

    assert classify_corridor_slot(night_dt) == "SLOT_NIGHT"
    assert classify_corridor_slot(early_dt_1) == "SLOT_EARLY_MORN"
    assert classify_corridor_slot(early_dt_2) == "SLOT_EARLY_MORN"
    assert classify_corridor_slot(early_dt_3) == "SLOT_EARLY_MORN"
    assert classify_corridor_slot(midday_dt) == "SLOT_MIDDAY"
    assert classify_corridor_slot(afternoon_dt) == "SLOT_AFTERNOON"


def test_overlaps_detected():
    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    # Confirm deliberate overlap between departments exists
    assert metrics["multi_dept_section_time_slots"] > 0
    assert metrics["pairwise_temporal_overlaps"] > 0
    assert metrics["pairwise_spatiotemporal_strict"] > 0
    assert metrics["pairwise_spatiotemporal_prox"] > 0
    assert metrics["three_dept_section_time_slots"] > 0


def test_time_and_chainage_validity():
    sec_map = {s["section_id"]: s for s in SECTIONS}
    requests, _ = generate_synthetic_dataset(target_count=240, seed=42)
    for r in requests:
        ws = datetime.fromisoformat(r["requested_window_start"])
        we = datetime.fromisoformat(r["requested_window_end"])
        assert ws < we, f"Window start {ws} must precede window end {we}"

        # Strict chainage bounds: start < end and within section bounds
        sec = sec_map[r["section_id"]]
        assert sec["start_km"] <= r["chainage_start"], f"Chainage start {r['chainage_start']} < section start {sec['start_km']}"
        assert r["chainage_start"] < r["chainage_end"], f"Chainage start {r['chainage_start']} >= end {r['chainage_end']}"
        assert r["chainage_end"] <= sec["end_km"], f"Chainage end {r['chainage_end']} > section end {sec['end_km']}"

        # Duration within window and positive
        assert r["required_duration_minutes"] > 0
        window_mins = (we - ws).total_seconds() / 60
        assert r["required_duration_minutes"] <= window_mins, "Required duration exceeds requested window"


def test_scheduling_slack_for_cpsat():
    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    assert metrics["zero_slack_count"] == 0
    assert metrics["avg_scheduling_slack_mins"] >= 15.0


def test_asset_condition_variance():
    requests, metrics = generate_synthetic_dataset(target_count=240, seed=42)
    urgency_cats = set(metrics["urgency_distribution"].keys())
    assert {"CRITICAL", "HIGH", "MEDIUM", "LOW"}.issubset(urgency_cats)

    ages = [r["asset_age_years"] for r in requests]
    assert min(ages) < 5.0
    assert max(ages) > 15.0

    scores = [r["condition_score"] for r in requests]
    assert min(scores) < 4.0
    assert max(scores) > 7.0


def test_file_persistence_non_destructive(tmp_path):
    # Test saving to a temporary directory so tests don't overwrite production data
    requests, _ = generate_synthetic_dataset(target_count=240, seed=42)
    req_csv, req_json, sec_csv, sec_json = save_datasets(requests, output_dir=str(tmp_path))

    assert os.path.exists(req_csv)
    assert os.path.exists(req_json)
    assert os.path.exists(sec_csv)
    assert os.path.exists(sec_json)

    with open(req_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
        assert len(csv_rows) == 240
        assert "corridor_slot" in csv_rows[0]

    with open(req_json, mode="r", encoding="utf-8") as f:
        json_data = json.load(f)
        assert len(json_data) == 240
        assert "asset_age_or_condition_features" in json_data[0]
        assert "asset_condition_features" in json_data[0]


def test_canonical_data_files_intact():
    # Verify canonical data directory holds expected files
    canonical_csv = os.path.join(OUTPUT_DIR, "maintenance_requests.csv")
    canonical_json = os.path.join(OUTPUT_DIR, "maintenance_requests.json")
    canonical_sec_csv = os.path.join(OUTPUT_DIR, "sections.csv")
    canonical_sec_json = os.path.join(OUTPUT_DIR, "sections.json")

    assert os.path.exists(canonical_csv)
    assert os.path.exists(canonical_json)
    assert os.path.exists(canonical_sec_csv)
    assert os.path.exists(canonical_sec_json)

    with open(canonical_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 240

    with open(canonical_json, mode="r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 240

