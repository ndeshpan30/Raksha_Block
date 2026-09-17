"""
RAKSHA-BLOCK: Unit & Integration Tests for Phase 3 ML Risk Scoring
==================================================================
Tests:
  1. LightGBM model artifact integrity & metadata loading
  2. Feature extraction across dictionary, schema, and ORM objects
  3. Single & batch inference bounding [0.0, 100.0]
  4. Monotonicity across degradation factors (condition score, breakdowns, lag, urgency)
  5. Operational risk tier mapping (CRITICAL, HIGH, MEDIUM, LOW)
  6. Heuristic fallback resilience
  7. FastAPI GET /requests response containing valid, non-degenerate risk_score
  8. FastAPI POST /api/v1/risk/score on-demand scoring endpoint
  9. FastAPI GET /api/v1/risk/distribution endpoint
  10. Non-degeneracy statistical verification across canonical dataset
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.database import Base, get_db, DATA_DIR, init_db
from app.models import MaintenanceRequestModel
from app.schemas import MaintenanceRequestResponse, RiskPredictionInput
from app.risk_model import (
    predict_risk_score,
    predict_risk_scores,
    get_risk_tier,
    get_model_metadata,
    extract_features_dict,
    _heuristic_fallback_score,
    JOBLIB_MODEL_FILE,
    TXT_MODEL_FILE,
    METADATA_FILE,
)
from app.main import app


@pytest.fixture(scope="module")
def api_client():
    init_db()
    with TestClient(app) as client:
        yield client


# ==============================================================================
# 1. Model Artifact & Feature Extraction Tests
# ==============================================================================

def test_model_artifacts_exist():
    """Verify that LightGBM model artifacts were trained and saved to models/."""
    assert JOBLIB_MODEL_FILE.exists(), f"Missing {JOBLIB_MODEL_FILE}"
    assert TXT_MODEL_FILE.exists(), f"Missing {TXT_MODEL_FILE}"
    assert METADATA_FILE.exists(), f"Missing {METADATA_FILE}"


def test_model_metadata_content():
    """Verify metadata contains feature columns and expected metrics."""
    meta = get_model_metadata()
    assert meta["algorithm"] == "LightGBM Regressor"
    assert "feature_columns" in meta
    assert len(meta["feature_columns"]) == 6
    assert "condition_score" in meta["feature_columns"]


def test_extract_features_from_dict():
    raw = {
        "asset_age_years": 12.5,
        "last_maintenance_days_ago": 180,
        "past_breakdown_count": 3,
        "gross_million_tonnes": 65.0,
        "condition_score": 4.2,
        "urgency_category": "HIGH",
    }
    extracted = extract_features_dict(raw)
    assert extracted["asset_age_years"] == 12.5
    assert extracted["last_maintenance_days_ago"] == 180.0
    assert extracted["past_breakdown_count"] == 3.0
    assert extracted["gross_million_tonnes"] == 65.0
    assert extracted["condition_score"] == 4.2
    assert extracted["urgency_level"] == 2  # HIGH -> 2


def test_extract_features_from_nested_container():
    raw = {
        "request_id": "REQ-TEST-01",
        "asset_condition_features": {
            "asset_age_years": 8.0,
            "last_maintenance_days_ago": 45,
            "past_breakdown_count": 0,
            "gross_million_tonnes": 30.0,
            "condition_score": 8.5,
            "urgency_category": "LOW",
        }
    }
    extracted = extract_features_dict(raw)
    assert extracted["asset_age_years"] == 8.0
    assert extracted["urgency_level"] == 0  # LOW -> 0


# ==============================================================================
# 2. Risk Inference Bounds & Monotonicity
# ==============================================================================

def test_predict_risk_score_bounds():
    """Test score bounds across multiple edge-case configurations."""
    # Best possible asset
    best_asset = {
        "asset_age_years": 0.5,
        "last_maintenance_days_ago": 5,
        "past_breakdown_count": 0,
        "gross_million_tonnes": 5.0,
        "condition_score": 10.0,
        "urgency_category": "LOW",
    }
    score_best = predict_risk_score(best_asset)
    assert 0.0 <= score_best <= 100.0
    assert score_best < 25.0  # Should be LOW risk

    # Worst possible asset
    worst_asset = {
        "asset_age_years": 30.0,
        "last_maintenance_days_ago": 365,
        "past_breakdown_count": 8,
        "gross_million_tonnes": 150.0,
        "condition_score": 1.0,
        "urgency_category": "CRITICAL",
    }
    score_worst = predict_risk_score(worst_asset)
    assert 0.0 <= score_worst <= 100.0
    assert score_worst > 75.0  # Should be CRITICAL risk


def test_predict_risk_score_monotonicity_condition_score():
    """Lower condition score (worse track) must yield higher risk score."""
    good_track = {
        "asset_age_years": 8.0,
        "last_maintenance_days_ago": 100,
        "past_breakdown_count": 1,
        "gross_million_tonnes": 50.0,
        "condition_score": 9.0,
        "urgency_category": "MEDIUM",
    }
    degraded_track = dict(good_track)
    degraded_track["condition_score"] = 2.5

    score_good = predict_risk_score(good_track)
    score_degraded = predict_risk_score(degraded_track)
    assert score_degraded > score_good


def test_predict_risk_score_monotonicity_past_breakdowns():
    """Higher past breakdown recurrence must yield higher risk score."""
    base = {
        "asset_age_years": 10.0,
        "last_maintenance_days_ago": 150,
        "past_breakdown_count": 0,
        "gross_million_tonnes": 60.0,
        "condition_score": 5.5,
        "urgency_category": "MEDIUM",
    }
    frequent_failure = dict(base)
    frequent_failure["past_breakdown_count"] = 5

    score_base = predict_risk_score(base)
    score_fail = predict_risk_score(frequent_failure)
    assert score_fail > score_base


def test_predict_risk_score_batch_consistency():
    """Batch prediction must equal individual predictions."""
    items = [
        {"asset_age_years": 2.0, "last_maintenance_days_ago": 30, "past_breakdown_count": 0, "gross_million_tonnes": 20.0, "condition_score": 8.5, "urgency_category": "LOW"},
        {"asset_age_years": 15.0, "last_maintenance_days_ago": 280, "past_breakdown_count": 4, "gross_million_tonnes": 90.0, "condition_score": 3.0, "urgency_category": "CRITICAL"},
    ]
    batch_scores = predict_risk_scores(items)
    indiv_scores = [predict_risk_score(it) for it in items]

    assert len(batch_scores) == 2
    for b, i in zip(batch_scores, indiv_scores):
        assert abs(b - i) < 0.01


def test_get_risk_tier_mapping():
    assert get_risk_tier(90.0) == "CRITICAL"
    assert get_risk_tier(75.0) == "CRITICAL"
    assert get_risk_tier(74.9) == "HIGH"
    assert get_risk_tier(50.0) == "HIGH"
    assert get_risk_tier(49.9) == "MEDIUM"
    assert get_risk_tier(25.0) == "MEDIUM"
    assert get_risk_tier(24.9) == "LOW"
    assert get_risk_tier(5.0) == "LOW"


def test_heuristic_fallback_resilience():
    features = {
        "asset_age_years": 10.0,
        "last_maintenance_days_ago": 120.0,
        "past_breakdown_count": 2.0,
        "gross_million_tonnes": 50.0,
        "condition_score": 6.0,
        "urgency_level": 1,
    }
    score = _heuristic_fallback_score(features)
    assert 0.0 <= score <= 100.0


# ==============================================================================
# 3. API Integration & Non-Degeneracy Verification
# ==============================================================================

def test_fastapi_requests_includes_risk_score(api_client):
    """Verify that GET /requests includes risk_score in every response object."""
    response = api_client.get("/requests?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10

    scores = []
    for item in data:
        assert "risk_score" in item
        assert isinstance(item["risk_score"], (int, float))
        assert 0.0 <= item["risk_score"] <= 100.0
        scores.append(item["risk_score"])

    # Confirm non-degeneracy (not all identical)
    assert len(set(scores)) > 1, "Scores should not all be identical!"


def test_fastapi_risk_score_post_endpoint(api_client):
    """Test on-demand scoring via POST /api/v1/risk/score."""
    payload = {
        "asset_age_years": 16.5,
        "last_maintenance_days_ago": 260,
        "past_breakdown_count": 4,
        "gross_million_tonnes": 88.0,
        "condition_score": 3.1,
        "urgency_category": "CRITICAL",
        "request_id": "REQ-TEST-POST-01",
    }
    response = api_client.post("/api/v1/risk/score", json=payload)
    assert response.status_code == 200
    result = response.json()

    assert result["request_id"] == "REQ-TEST-POST-01"
    assert result["risk_score"] >= 75.0
    assert result["risk_tier"] == "CRITICAL"


def test_fastapi_risk_distribution_endpoint(api_client):
    """Test GET /api/v1/risk/distribution returns valid statistical spread."""
    response = api_client.get("/api/v1/risk/distribution")
    assert response.status_code == 200
    dist = response.json()

    assert dist["count"] >= 240
    assert dist["min"] < 15.0
    assert dist["max"] > 80.0
    assert dist["std"] > 15.0
    assert len(dist["ascii_histogram"]) == 10
    assert dist["tier_distribution"]["CRITICAL"] > 0
    assert dist["tier_distribution"]["LOW"] > 0


def test_fastapi_risk_model_info_endpoint(api_client):
    """Test GET /api/v1/risk/model-info."""
    response = api_client.get("/api/v1/risk/model-info")
    assert response.status_code == 200
    info = response.json()
    assert info["algorithm"] == "LightGBM Regressor"
    assert len(info["feature_columns"]) == 6


def test_dataset_score_distribution_non_degenerate():
    """
    Verify across the full canonical 240 maintenance requests that the score
    distribution is healthy, diverse, and spread across all 4 operational tiers.
    """
    csv_file = DATA_DIR / "maintenance_requests.csv"
    assert csv_file.exists()
    df = pd.read_csv(csv_file)

    scores = predict_risk_scores(df.to_dict(orient="records"))
    assert len(scores) == 240

    scores_arr = np.array(scores)
    min_score = np.min(scores_arr)
    max_score = np.max(scores_arr)
    mean_score = np.mean(scores_arr)
    std_score = np.std(scores_arr)

    # Health checks for non-degeneracy
    assert min_score < 10.0, f"Min score should be low, got {min_score}"
    assert max_score > 85.0, f"Max score should be high, got {max_score}"
    assert 25.0 <= mean_score <= 50.0, f"Mean should be in realistic mid-range, got {mean_score}"
    assert std_score >= 20.0, f"Standard deviation should be substantial, got {std_score}"

    # Verify all four tiers are populated
    tiers = [get_risk_tier(s) for s in scores]
    tier_set = set(tiers)
    assert {"CRITICAL", "HIGH", "MEDIUM", "LOW"}.issubset(tier_set)


# ==============================================================================
# 4. Phase 3 Verification & Edge Case Defenses
# ==============================================================================

def test_extract_features_preserves_zero_values():
    """Verify that legitimate 0/0.0 values are not coerced to non-zero defaults."""
    raw = {
        "asset_age_years": 0.0,
        "last_maintenance_days_ago": 0,
        "past_breakdown_count": 0,
        "gross_million_tonnes": 0.0,
        "condition_score": 10.0,
        "urgency_category": "LOW",
    }
    extracted = extract_features_dict(raw)
    assert extracted["asset_age_years"] == 0.0
    assert extracted["last_maintenance_days_ago"] == 0.0
    assert extracted["past_breakdown_count"] == 0.0
    assert extracted["gross_million_tonnes"] == 0.0
    assert extracted["condition_score"] == 10.0
    assert extracted["urgency_level"] == 0

    # Risk score for brand new pristine track must be extremely low (< 5.0)
    score = predict_risk_score(raw)
    assert 0.0 <= score < 5.0


def test_extract_features_none_and_empty():
    """Verify that extract_features_dict safely handles None and empty dicts."""
    feat_none = extract_features_dict(None)
    feat_empty = extract_features_dict({})

    for k in ["asset_age_years", "last_maintenance_days_ago", "past_breakdown_count", "gross_million_tonnes", "condition_score", "urgency_level"]:
        assert k in feat_none
        assert k in feat_empty

    # Batch prediction with None elements must not raise KeyError
    batch_scores = predict_risk_scores([None, {}])
    assert len(batch_scores) == 2
    assert all(0.0 <= s <= 100.0 for s in batch_scores)


def test_extract_features_out_of_distribution_bounds():
    """Verify physical boundary clamping on extreme out-of-distribution values."""
    raw = {
        "asset_age_years": -10.0,
        "last_maintenance_days_ago": -50,
        "past_breakdown_count": -2,
        "gross_million_tonnes": -15.0,
        "condition_score": 15.0,  # exceeds 10.0
        "urgency_level": 99,     # exceeds 3
    }
    extracted = extract_features_dict(raw)
    assert extracted["asset_age_years"] == 0.0
    assert extracted["last_maintenance_days_ago"] == 0.0
    assert extracted["past_breakdown_count"] == 0.0
    assert extracted["gross_million_tonnes"] == 0.0
    assert extracted["condition_score"] == 10.0
    assert extracted["urgency_level"] == 3
    assert extracted["urgency_category"] == "CRITICAL"


def test_maintenance_request_response_accepts_none_risk_score():
    """Verify MaintenanceRequestResponse accepts None risk_score without ValidationError and auto-computes."""
    from datetime import datetime
    obj = {
        "request_id": "REQ-NONE-01",
        "source_system": "TMS",
        "department": "ENG",
        "section_id": "SEC-01",
        "corridor_slot": "SLOT_NIGHT",
        "chainage_start": 0.0,
        "chainage_end": 1.0,
        "requested_window_start": datetime(2026, 9, 15, 1, 0),
        "requested_window_end": datetime(2026, 9, 15, 3, 0),
        "required_duration_minutes": 60,
        "work_type": "Rail Renewal",
        "asset_id": "A-01",
        "asset_type": "Track",
        "asset_age_years": 5.0,
        "last_maintenance_days_ago": 60,
        "past_breakdown_count": 1,
        "gross_million_tonnes": 30.0,
        "condition_score": 7.0,
        "urgency_category": "MEDIUM",
        "requires_power_block": False,
        "requires_traffic_block": True,
        "status": "PENDING",
        "risk_score": None,
    }
    resp = MaintenanceRequestResponse.model_validate(obj)
    assert resp.risk_score is not None
    assert 0.0 <= resp.risk_score <= 100.0

    # Explicit 0.0 should be preserved
    obj["risk_score"] = 0.0
    resp_zero = MaintenanceRequestResponse.model_validate(obj)
    assert resp_zero.risk_score == 0.0


def test_predict_risk_score_fallback_when_files_missing(monkeypatch, tmp_path):
    """Verify predict_risk_score falls back to deterministic heuristic if model files are missing."""
    import app.risk_model as rm
    monkeypatch.setattr(rm, "_CACHED_MODEL", None)
    monkeypatch.setattr(rm, "JOBLIB_MODEL_FILE", tmp_path / "missing.joblib")
    monkeypatch.setattr(rm, "TXT_MODEL_FILE", tmp_path / "missing.txt")

    feat = {
        "asset_age_years": 10.0,
        "last_maintenance_days_ago": 100,
        "past_breakdown_count": 2,
        "gross_million_tonnes": 50.0,
        "condition_score": 5.0,
        "urgency_category": "MEDIUM",
    }
    score = rm.predict_risk_score(feat)
    assert 0.0 <= score <= 100.0


def test_fastapi_risk_route_aliases(api_client):
    """Verify route aliases /risk/distribution and /risk/model-info work."""
    resp_dist = api_client.get("/risk/distribution")
    assert resp_dist.status_code == 200
    assert resp_dist.json()["count"] >= 240

    resp_info = api_client.get("/risk/model-info")
    assert resp_info.status_code == 200
    assert resp_info.json()["algorithm"] == "LightGBM Regressor"


def test_fastapi_risk_score_urgency_normalization_and_features(api_client):
    """Verify POST /api/v1/risk/score normalizes lowercase urgency and outputs urgency_level."""
    payload = {
        "asset_age_years": 8.0,
        "last_maintenance_days_ago": 90,
        "past_breakdown_count": 1,
        "gross_million_tonnes": 45.0,
        "condition_score": 6.0,
        "urgency_category": "high",  # lowercase
        "request_id": "REQ-TEST-NORM",
    }
    response = api_client.post("/api/v1/risk/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "REQ-TEST-NORM"
    assert "urgency_level" in data["features"]
    assert data["features"]["urgency_level"] == 2
    assert data["features"]["urgency_category"] == "HIGH"
    # request_id should not leak into features container
    assert "request_id" not in data["features"]

    # Invalid urgency category should return 422
    payload["urgency_category"] = "SUPER_CRITICAL"
    bad_resp = api_client.post("/api/v1/risk/score", json=payload)
    assert bad_resp.status_code == 422


def test_fastapi_risk_distribution_empty_db():
    """Verify get_risk_distribution returns all expected keys with zero counts on empty DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.main import get_risk_distribution

    mem_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=mem_engine)
    MemSession = sessionmaker(bind=mem_engine)
    session = MemSession()

    res = get_risk_distribution(db=session)
    assert res["count"] == 0
    assert res["min"] == 0.0
    assert res["max"] == 0.0
    assert res["mean"] == 0.0
    assert res["std"] == 0.0
    assert "tier_distribution" in res
    assert "ascii_histogram" in res
    assert res["ascii_histogram"] == []
    assert "message" in res


