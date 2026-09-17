"""
RAKSHA-BLOCK: Phase 5 Automated Test Suite for Explainability Engine
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination

Verifies:
1. Structured BlockExplanation object generation and Pydantic validation.
2. Accuracy of merged requests details, driving risk factors, and driving constraints.
3. Calculation of alternatives considered and possession savings.
4. Backward compatibility of explanation_text and explanation_detail / explanation alias.
5. End-to-end integration with optimizer and FastAPI REST endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import SectionModel, MaintenanceRequestModel
from app.main import app
from app.optimizer import optimize_requests, OptimizerConfig
from app.explainer import (
    generate_block_explanation,
    BlockExplanation,
    MergedRequestDetail,
    PriorityReasoning,
    ConstraintReasoning,
    AlternativesReasoning,
    WindowBounds,
)
from tests.test_optimizer_handcrafted import get_handcrafted_test_requests


@pytest.fixture
def test_db_session(tmp_path):
    """Isolated SQLite database for test session."""
    db_file = tmp_path / "test_raksha_explain.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# Unit Tests for generate_block_explanation
# ==============================================================================

def test_generate_block_explanation_triple_bundle():
    """Verify explanation generation for a 3-department bundled block."""
    reqs = [
        {
            "request_id": "REQ-01",
            "department": "ENG",
            "work_type": "Track Tamping",
            "asset_id": "ENG-ASSET-01",
            "asset_type": "Ballast Track",
            "chainage_start": 10.0,
            "chainage_end": 12.0,
            "requested_window_start": "2026-09-15T01:00:00",
            "requested_window_end": "2026-09-15T05:00:00",
            "required_duration_minutes": 120,
            "scheduled_start": "2026-09-15T01:00:00",
            "scheduled_end": "2026-09-15T03:00:00",
            "risk_score": 85.5,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "REQ-02",
            "department": "S&T",
            "work_type": "Point Machine Overhaul",
            "asset_id": "ST-ASSET-01",
            "asset_type": "Point Machine",
            "chainage_start": 10.5,
            "chainage_end": 11.0,
            "requested_window_start": "2026-09-15T01:00:00",
            "requested_window_end": "2026-09-15T05:00:00",
            "required_duration_minutes": 60,
            "scheduled_start": "2026-09-15T01:00:00",
            "scheduled_end": "2026-09-15T02:00:00",
            "risk_score": 62.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "REQ-03",
            "department": "TRD",
            "work_type": "OHE Wire Inspection",
            "asset_id": "TRD-ASSET-01",
            "asset_type": "OHE Wire",
            "chainage_start": 9.8,
            "chainage_end": 12.2,
            "requested_window_start": "2026-09-15T01:00:00",
            "requested_window_end": "2026-09-15T05:00:00",
            "required_duration_minutes": 90,
            "scheduled_start": "2026-09-15T01:00:00",
            "scheduled_end": "2026-09-15T02:30:00",
            "risk_score": 45.0,
            "requires_power_block": True,
            "requires_traffic_block": True,
        },
    ]

    expl: BlockExplanation = generate_block_explanation(
        section_id="SEC-TEST-01",
        corridor_slot="SLOT_NIGHT",
        start_km=9.8,
        end_km=12.2,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T03:00:00",
        total_duration_minutes=120,
        departments_involved=["ENG", "S&T", "TRD"],
        power_block_granted=True,
        traffic_block_granted=True,
        savings_minutes=150,
        constituent_requests=reqs,
        spatial_proximity_km=2.0,
        max_block_km_span=15.0,
        is_deferred=False,
    )

    # 1. Verify summary
    assert "Bundled 3 cross-departmental requests (ENG + S&T + TRD)" in expl.summary
    assert "SEC-TEST-01" in expl.summary
    assert "KM 9.80 - 12.20" in expl.summary
    assert "saves 150 minutes" in expl.summary
    assert "ENG-ASSET-01" in expl.summary
    assert "85.50" in expl.summary

    # 2. Verify merged_requests
    assert len(expl.merged_requests) == 3
    req_map = {r.request_id: r for r in expl.merged_requests}
    assert req_map["REQ-01"].risk_score == 85.5
    assert req_map["REQ-01"].urgency_tier == "CRITICAL"
    assert req_map["REQ-02"].urgency_tier == "HIGH"
    assert req_map["REQ-03"].urgency_tier == "MEDIUM"
    assert req_map["REQ-03"].requires_power_block is True

    # 3. Verify driving_priority
    assert expl.driving_priority.highest_risk_request_id == "REQ-01"
    assert expl.driving_priority.highest_risk_asset_id == "ENG-ASSET-01"
    assert expl.driving_priority.highest_risk_score == 85.5
    assert expl.driving_priority.highest_risk_department == "ENG"
    assert expl.driving_priority.risk_tier == "CRITICAL"
    assert "ENG-ASSET-01" in expl.driving_priority.anchoring_reason
    assert expl.driving_priority.average_risk_score == pytest.approx(64.17, abs=0.1)
    assert expl.driving_priority.risk_spread == pytest.approx(40.5, abs=0.1)

    # 4. Verify driving_constraints
    assert expl.driving_constraints.spatial_chainage_overlap is True
    assert expl.driving_constraints.spatial_overlap_type == "DIRECT_OVERLAP"
    assert expl.driving_constraints.enveloping_chainage_span_km == 2.4
    assert expl.driving_constraints.power_block_required is True
    assert "REQ-03" in expl.driving_constraints.power_block_driver
    assert expl.driving_constraints.traffic_block_required is True
    assert expl.driving_constraints.duration_savings_minutes == 150
    assert len(expl.driving_constraints.key_constraints_applied) >= 4

    # 5. Verify alternatives_considered
    assert expl.alternatives_considered.separate_possession_minutes == 270  # 120 + 60 + 90
    assert expl.alternatives_considered.bundled_possession_minutes == 120
    assert expl.alternatives_considered.possession_savings_minutes == 150
    assert expl.alternatives_considered.possession_savings_pct == pytest.approx(55.56, abs=0.1)
    assert "saving 150 minutes" in expl.alternatives_considered.why_not_scheduled_separately or "saves 150 minutes" in expl.alternatives_considered.why_not_scheduled_separately
    assert len(expl.alternatives_considered.alternatives_evaluated) >= 2


def test_generate_block_explanation_single_block():
    """Verify explanation generation for a single standalone block."""
    reqs = [
        {
            "request_id": "REQ-SOLO",
            "department": "ENG",
            "work_type": "Rail Grinding",
            "asset_id": "ENG-ASSET-99",
            "asset_type": "Continuous Welded Rail",
            "chainage_start": 40.0,
            "chainage_end": 42.5,
            "requested_window_start": "2026-09-15T12:00:00",
            "requested_window_end": "2026-09-15T14:30:00",
            "required_duration_minutes": 75,
            "scheduled_start": "2026-09-15T12:00:00",
            "scheduled_end": "2026-09-15T13:15:00",
            "risk_score": 30.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        }
    ]

    expl: BlockExplanation = generate_block_explanation(
        section_id="SEC-TEST-02",
        corridor_slot="SLOT_MIDDAY",
        start_km=40.0,
        end_km=42.5,
        scheduled_start="2026-09-15T12:00:00",
        scheduled_end="2026-09-15T13:15:00",
        total_duration_minutes=75,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=True,
        savings_minutes=0,
        constituent_requests=reqs,
        spatial_proximity_km=2.0,
        max_block_km_span=15.0,
        is_deferred=False,
    )

    assert "Single departmental possession block granted for ENG" in expl.summary
    assert "SEC-TEST-02" in expl.summary
    assert expl.driving_constraints.spatial_overlap_type == "SINGLE_ISOLATED"
    assert expl.alternatives_considered.possession_savings_minutes == 0
    assert expl.driving_constraints.power_block_required is False
    assert "No 25kV OHE power isolation required" in expl.driving_constraints.power_block_driver


def test_generate_block_explanation_deferred():
    """Verify explanation generation for a deferred block."""
    reqs = [
        {
            "request_id": "REQ-DEF",
            "department": "ENG",
            "work_type": "Switch Renewal",
            "asset_id": "ENG-SW-01",
            "asset_type": "Turnout",
            "chainage_start": 5.0,
            "chainage_end": 5.5,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 180,
            "risk_score": 92.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        }
    ]

    expl: BlockExplanation = generate_block_explanation(
        section_id="SEC-TEST-03",
        corridor_slot="SLOT_NIGHT",
        start_km=5.0,
        end_km=5.5,
        scheduled_start="2026-09-15T00:30:00",
        scheduled_end="2026-09-15T04:30:00",
        total_duration_minutes=0,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=False,
        savings_minutes=0,
        constituent_requests=reqs,
        is_deferred=True,
    )

    assert "deferred due to corridor slot capacity constraints" in expl.summary
    assert expl.driving_priority.risk_tier == "CRITICAL"
    assert "capacity" in expl.driving_priority.anchoring_reason.lower()


# ==============================================================================
# Functional Tests on Optimizer with Handcrafted Dataset
# ==============================================================================

def test_handcrafted_optimizer_explanation_outputs():
    """Verify that optimizer output blocks include full Phase 5 structured explanations."""
    requests = get_handcrafted_test_requests()
    config = OptimizerConfig(spatial_proximity_km=2.0)
    result = optimize_requests(requests, config)

    assert result.status == "OPTIMAL"
    assert len(result.blocks) == 4

    for b in result.blocks:
        # Backward compatibility check
        assert isinstance(b.explanation_text, str)
        assert len(b.explanation_text) > 20

        # Structured explanation detail check
        assert isinstance(b.explanation_detail, dict)
        assert "summary" in b.explanation_detail
        assert "merged_requests" in b.explanation_detail
        assert "driving_priority" in b.explanation_detail
        assert "driving_constraints" in b.explanation_detail
        assert "alternatives_considered" in b.explanation_detail

        # Explanation alias check
        assert b.explanation == b.explanation_detail

        # Validate with Pydantic model
        validated = BlockExplanation.model_validate(b.explanation_detail)
        assert validated.summary == b.explanation_text

    # Specifically check Block 1 (Triple bundle)
    b1 = next(b for b in result.blocks if "TEST-REQ-001" in b.bundled_request_ids)
    assert len(b1.explanation_detail["merged_requests"]) == 3
    assert b1.explanation_detail["driving_priority"]["highest_risk_request_id"] == "TEST-REQ-001"
    assert b1.explanation_detail["driving_priority"]["highest_risk_score"] == 85.0
    assert b1.explanation_detail["driving_constraints"]["duration_savings_minutes"] == 150
    assert b1.explanation_detail["driving_constraints"]["power_block_required"] is True
    assert b1.explanation_detail["driving_constraints"]["traffic_block_required"] is True

    # Specifically check Block 2 (Double bundle)
    b2 = next(b for b in result.blocks if "TEST-REQ-004" in b.bundled_request_ids)
    assert len(b2.explanation_detail["merged_requests"]) == 2
    assert b2.explanation_detail["driving_priority"]["highest_risk_request_id"] == "TEST-REQ-004"
    assert b2.explanation_detail["driving_priority"]["highest_risk_score"] == 90.0
    assert b2.explanation_detail["driving_constraints"]["duration_savings_minutes"] == 100


# ==============================================================================
# API Integration Tests for Phase 5 Endpoints
# ==============================================================================

def test_api_optimize_returns_structured_explanations(client):
    """POST /optimize response must include explanation_detail and explanation in every block."""
    payload = {
        "requests": get_handcrafted_test_requests(),
        "spatial_proximity_km": 2.0,
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "OPTIMAL"
    assert len(data["blocks"]) == 4

    for b in data["blocks"]:
        assert "explanation_text" in b
        assert "explanation_detail" in b
        assert "explanation" in b
        assert b["explanation"] == b["explanation_detail"]

        detail = b["explanation_detail"]
        assert "summary" in detail
        assert "merged_requests" in detail
        assert "driving_priority" in detail
        assert "driving_constraints" in detail
        assert "alternatives_considered" in detail

        # Priority assertions
        dp = detail["driving_priority"]
        assert "highest_risk_score" in dp
        assert "anchoring_reason" in dp

        # Constraint assertions
        dc = detail["driving_constraints"]
        assert "spatial_overlap_type" in dc
        assert "window_bounds" in dc
        assert "key_constraints_applied" in dc

        # Alternatives assertions
        ac = detail["alternatives_considered"]
        assert "why_not_scheduled_separately" in ac
        assert "possession_savings_pct" in ac


def test_api_blocks_endpoint(client, test_db_session):
    """GET /api/v1/blocks returns all optimized blocks with structured explanations."""
    sec = SectionModel(
        section_id="SEC-EXPLAIN-01", name="Exp Track", line_type="DOUBLE",
        start_station="A", end_station="B", start_km=0.0, end_km=30.0,
        max_speed_kmh=120, traffic_density_index=1.0,
    )
    test_db_session.add(sec)
    test_db_session.commit()

    r1 = MaintenanceRequestModel(
        request_id="R-EX-1", source_system="TMS", department="ENG", section_id="SEC-EXPLAIN-01",
        corridor_slot="SLOT_NIGHT", chainage_start=5.0, chainage_end=7.0,
        requested_window_start=datetime(2026, 9, 15, 0, 30), requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=120, work_type="Track Renewal", asset_id="A-1", asset_type="Track",
        asset_age_years=5.0, last_maintenance_days_ago=60, past_breakdown_count=0, gross_million_tonnes=30.0,
        condition_score=8.0, urgency_category="LOW", risk_score=25.0, requires_power_block=False,
        requires_traffic_block=True, status="PENDING",
    )
    test_db_session.add(r1)
    test_db_session.commit()

    response = client.get("/api/v1/blocks")
    assert response.status_code == 200
    blocks = response.json()
    assert len(blocks) == 1
    assert "explanation_detail" in blocks[0]
    assert blocks[0]["explanation_detail"]["driving_priority"]["highest_risk_asset_id"] == "A-1"


def test_api_block_explain_endpoint(client, test_db_session):
    """GET /api/v1/blocks/{block_id}/explain returns detailed rationale for the specified block."""
    sec = SectionModel(
        section_id="SEC-EXPLAIN-02", name="Exp Track 2", line_type="DOUBLE",
        start_station="C", end_station="D", start_km=0.0, end_km=30.0,
        max_speed_kmh=120, traffic_density_index=1.0,
    )
    test_db_session.add(sec)
    test_db_session.commit()

    r1 = MaintenanceRequestModel(
        request_id="R-EX-2", source_system="TMS", department="TRD", section_id="SEC-EXPLAIN-02",
        corridor_slot="SLOT_NIGHT", chainage_start=12.0, chainage_end=14.0,
        requested_window_start=datetime(2026, 9, 15, 0, 30), requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=90, work_type="OHE Inspection", asset_id="A-TRD-2", asset_type="OHE",
        asset_age_years=3.0, last_maintenance_days_ago=30, past_breakdown_count=0, gross_million_tonnes=20.0,
        condition_score=9.0, urgency_category="LOW", risk_score=15.0, requires_power_block=True,
        requires_traffic_block=True, status="PENDING",
    )
    test_db_session.add(r1)
    test_db_session.commit()

    # Get block ID
    blocks_res = client.get("/api/v1/blocks")
    assert blocks_res.status_code == 200
    target_block_id = blocks_res.json()[0]["block_id"]

    # Call explain endpoint
    explain_res = client.get(f"/api/v1/blocks/{target_block_id}/explain")
    assert explain_res.status_code == 200
    explain_data = explain_res.json()

    assert explain_data["block_id"] == target_block_id
    assert "explanation_text" in explain_data
    assert "explanation_detail" in explain_data
    assert explain_data["explanation_detail"]["driving_constraints"]["power_block_required"] is True

    # 404 for non-existent block
    nf_res = client.get("/api/v1/blocks/BLK-NONEXISTENT/explain")
    assert nf_res.status_code == 404


def test_api_controller_action_endpoint(client):
    """POST /api/v1/blocks/{block_id}/action allows Controller approve/reject decisions."""
    # Test APPROVE
    res_approve = client.post(
        "/api/v1/blocks/BLK-20260915-0001/action",
        json={"action": "APPROVE", "controller_notes": "Possession granted per slot schedule."},
    )
    assert res_approve.status_code == 200
    data_app = res_approve.json()
    assert data_app["action"] == "APPROVE"
    assert data_app["status"] == "APPROVED_BY_CONTROLLER"
    assert "Notes: Possession granted" in data_app["message"]

    # Test REJECT
    res_reject = client.post(
        "/api/v1/blocks/BLK-20260915-0001/action",
        json={"action": "REJECT", "controller_notes": "VIP train movement priority conflict."},
    )
    assert res_reject.status_code == 200
    data_rej = res_reject.json()
    assert data_rej["status"] == "REJECTED_BY_CONTROLLER"

    # Test Invalid Action
    res_inv = client.post(
        "/api/v1/blocks/BLK-20260915-0001/action",
        json={"action": "INVALID_ACTION"},
    )
    assert res_inv.status_code == 400


def test_api_health_endpoint(client):
    """GET /api/v1/health returns system operational status."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert res.json()["service"] == "RAKSHA-BLOCK"


# ==============================================================================
# Edge-Case & Defect Regression Tests
# ==============================================================================

def test_explainer_resilience_to_null_and_missing_fields():
    """Verify explainer does not crash when request fields are None or empty."""
    reqs = [
        {
            "request_id": "REQ-NULL-01",
            "department": None,
            "work_type": None,
            "asset_id": None,
            "asset_type": None,
            "chainage_start": None,
            "chainage_end": None,
            "requested_window_start": None,
            "requested_window_end": None,
            "required_duration_minutes": None,
            "scheduled_start": None,
            "scheduled_end": None,
            "risk_score": None,
            "requires_power_block": None,
            "requires_traffic_block": None,
        }
    ]

    expl = generate_block_explanation(
        section_id="SEC-NULL",
        corridor_slot="SLOT_NIGHT",
        start_km=0.0,
        end_km=1.0,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T02:00:00",
        total_duration_minutes=60,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=True,
        savings_minutes=0,
        constituent_requests=reqs,
    )

    assert expl.summary is not None
    assert len(expl.merged_requests) == 1
    assert expl.merged_requests[0].risk_score == 0.0
    assert expl.driving_priority.highest_risk_score == 0.0
    assert expl.driving_constraints.actual_spatial_gap_km == 0.0


def test_explainer_nested_intervals_gap_zero():
    """Verify that an enclosing interval with nested sub-intervals yields actual_gap_km == 0.0."""
    reqs = [
        {"request_id": "R1", "chainage_start": 10.0, "chainage_end": 20.0, "required_duration_minutes": 60, "risk_score": 50.0},
        {"request_id": "R2", "chainage_start": 12.0, "chainage_end": 14.0, "required_duration_minutes": 60, "risk_score": 40.0},
        {"request_id": "R3", "chainage_start": 16.0, "chainage_end": 18.0, "required_duration_minutes": 60, "risk_score": 30.0},
    ]

    expl = generate_block_explanation(
        section_id="SEC-NESTED",
        corridor_slot="SLOT_NIGHT",
        start_km=10.0,
        end_km=20.0,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T03:00:00",
        total_duration_minutes=120,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=True,
        savings_minutes=60,
        constituent_requests=reqs,
    )

    assert expl.driving_constraints.actual_spatial_gap_km == 0.0
    assert expl.driving_constraints.spatial_overlap_type == "DIRECT_OVERLAP"


def test_explainer_bridged_chainage_classification():
    """Verify that 3 non-overlapping requests with gaps <= 2.0 km are classified as BRIDGED_CHAINAGE."""
    reqs = [
        {"request_id": "B1", "chainage_start": 10.0, "chainage_end": 11.0, "required_duration_minutes": 60, "risk_score": 40.0},
        {"request_id": "B2", "chainage_start": 12.0, "chainage_end": 13.0, "required_duration_minutes": 60, "risk_score": 50.0},
        {"request_id": "B3", "chainage_start": 14.0, "chainage_end": 15.0, "required_duration_minutes": 60, "risk_score": 30.0},
    ]

    expl = generate_block_explanation(
        section_id="SEC-BRIDGE",
        corridor_slot="SLOT_NIGHT",
        start_km=10.0,
        end_km=15.0,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T03:00:00",
        total_duration_minutes=120,
        departments_involved=["ENG", "TRD"],
        power_block_granted=True,
        traffic_block_granted=True,
        savings_minutes=60,
        constituent_requests=reqs,
        spatial_proximity_km=2.0,
    )

    assert expl.driving_constraints.actual_spatial_gap_km == 1.0
    assert expl.driving_constraints.spatial_overlap_type == "BRIDGED_CHAINAGE"
    assert any("Spatial bridging constraint" in c for c in expl.driving_constraints.key_constraints_applied)


def test_explainer_deferred_block_zero_savings():
    """Verify that deferred blocks have 0 savings and no contradictory duration claims."""
    reqs = [
        {"request_id": "DEF-01", "department": "ENG", "work_type": "Switch Fix", "chainage_start": 5.0, "chainage_end": 6.0, "required_duration_minutes": 120, "risk_score": 88.0}
    ]

    expl = generate_block_explanation(
        section_id="SEC-DEF",
        corridor_slot="SLOT_NIGHT",
        start_km=5.0,
        end_km=6.0,
        scheduled_start="2026-09-15T00:30:00",
        scheduled_end="2026-09-15T02:30:00",
        total_duration_minutes=0,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=False,
        savings_minutes=0,
        constituent_requests=reqs,
        is_deferred=True,
    )

    assert expl.alternatives_considered.possession_savings_minutes == 0
    assert expl.alternatives_considered.possession_savings_pct == 0.0
    assert expl.driving_constraints.duration_savings_minutes == 0
    assert any("Track capacity saturation" in c for c in expl.driving_constraints.key_constraints_applied)


def test_explainer_single_department_multi_request_bundle():
    """Verify that a bundle from a single department does not say 'cross-departmental'."""
    reqs = [
        {"request_id": "ENG-1", "department": "ENG", "work_type": "Rail Fix", "chainage_start": 1.0, "chainage_end": 2.0, "required_duration_minutes": 60, "risk_score": 60.0},
        {"request_id": "ENG-2", "department": "ENG", "work_type": "Sleeper Fix", "chainage_start": 1.5, "chainage_end": 2.5, "required_duration_minutes": 60, "risk_score": 40.0},
    ]

    expl = generate_block_explanation(
        section_id="SEC-ENG-ONLY",
        corridor_slot="SLOT_NIGHT",
        start_km=1.0,
        end_km=2.5,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T02:30:00",
        total_duration_minutes=90,
        departments_involved=["ENG"],
        power_block_granted=False,
        traffic_block_granted=True,
        savings_minutes=30,
        constituent_requests=reqs,
    )

    assert "cross-departmental" not in expl.summary.lower()
    assert "ENG maintenance requests" in expl.summary


def test_explainer_low_risk_block_reasoning():
    """Verify that a low-risk block does not claim 'High composite urgency'."""
    reqs = [
        {"request_id": "LOW-1", "department": "TRD", "work_type": "Inspection", "chainage_start": 1.0, "chainage_end": 2.0, "required_duration_minutes": 60, "risk_score": 12.5},
        {"request_id": "LOW-2", "department": "ENG", "work_type": "Patrol", "chainage_start": 1.2, "chainage_end": 1.8, "required_duration_minutes": 60, "risk_score": 8.0},
    ]

    expl = generate_block_explanation(
        section_id="SEC-LOW",
        corridor_slot="SLOT_NIGHT",
        start_km=1.0,
        end_km=2.0,
        scheduled_start="2026-09-15T01:00:00",
        scheduled_end="2026-09-15T02:00:00",
        total_duration_minutes=60,
        departments_involved=["ENG", "TRD"],
        power_block_granted=False,
        traffic_block_granted=True,
        savings_minutes=60,
        constituent_requests=reqs,
    )

    assert "High composite urgency" not in expl.alternatives_considered.why_not_deferred
    assert "anchoring risk: 12.50" in expl.alternatives_considered.why_not_deferred


def test_api_explain_cached_custom_payload_block(client):
    """Verify that GET /api/v1/blocks/{block_id}/explain resolves blocks generated from custom payload."""
    payload = {
        "requests": get_handcrafted_test_requests(),
        "spatial_proximity_km": 2.0,
    }
    opt_res = client.post("/optimize", json=payload)
    assert opt_res.status_code == 200
    target_b_id = opt_res.json()["blocks"][0]["block_id"]

    # Explain target block - should hit cache and resolve immediately
    exp_res = client.get(f"/api/v1/blocks/{target_b_id}/explain")
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert exp_data["block_id"] == target_b_id
    assert "explanation_detail" in exp_data
    assert exp_data["explanation_detail"]["driving_priority"]["highest_risk_score"] > 0

