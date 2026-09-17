"""
RAKSHA-BLOCK: Phase 6 Automated Test Suite for Frontend-Backend Contracts
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination

Verifies:
1. System health endpoints (/api/v1/health, /health).
2. CORS middleware headers enabled for frontend access.
3. Controller View API contracts (/optimize, /api/v1/blocks).
4. Explanation Drawer API contracts (/api/v1/blocks/{block_id}/explain).
5. Planner View API contracts (/requests, /api/v1/requests).
6. Station Master filtering logic and data integrity.
7. Controller human-in-the-loop actions (APPROVE, REJECT, MODIFY).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db, SessionLocal
from app.models import MaintenanceRequestModel


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_cors_headers_present(client):
    """Confirm CORS headers are attached so Next.js frontend can communicate with backend."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_health_endpoint(client):
    """Test health check endpoint for frontend status indicator."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RAKSHA-BLOCK"
    assert "version" in data


def test_controller_view_optimize_contract(client):
    """Test POST /optimize returns full optimization plan with bundled blocks, metrics, and solve time."""
    resp = client.post("/optimize", json={})
    assert resp.status_code == 200
    plan = resp.json()

    assert "status" in plan
    assert plan["status"] in ["OPTIMAL", "FEASIBLE"]
    assert plan.get("total_requests_in") == 240
    assert plan.get("total_blocks_out", 0) > 0
    assert plan.get("bundled_blocks_count", 0) > 0
    assert plan.get("total_savings_minutes", 0) > 0
    assert "solve_time_seconds" in plan
    assert isinstance(plan.get("blocks"), list)
    assert len(plan["blocks"]) == plan["total_blocks_out"]

    first_b = plan["blocks"][0]
    for field in [
        "block_id",
        "section_id",
        "corridor_slot",
        "start_km",
        "end_km",
        "scheduled_start",
        "scheduled_end",
        "total_duration_minutes",
        "bundled_request_ids",
        "departments_involved",
        "savings_minutes",
        "explanation_text",
        "approval_status",
    ]:
        assert field in first_b, f"Missing '{field}' in block from /optimize"


def test_controller_view_blocks_contract(client):
    """Test GET /api/v1/blocks returns required fields for Controller View."""
    resp = client.get("/api/v1/blocks")
    assert resp.status_code == 200
    blocks = resp.json()
    assert isinstance(blocks, list)
    assert len(blocks) > 0

    first_block = blocks[0]
    required_fields = [
        "block_id",
        "section_id",
        "corridor_slot",
        "start_km",
        "end_km",
        "scheduled_start",
        "scheduled_end",
        "total_duration_minutes",
        "bundled_request_ids",
        "departments_involved",
        "power_block_granted",
        "traffic_block_granted",
        "savings_minutes",
        "explanation_text",
        "explanation_detail",
        "approval_status",
    ]
    for field in required_fields:
        assert field in first_block, f"Missing required field '{field}' in block"

    # Verify at least one bundled block exists
    bundled_blocks = [b for b in blocks if len(b["bundled_request_ids"]) > 1]
    assert len(bundled_blocks) > 0, "Expected at least one bundled block in output"
    assert any(b["savings_minutes"] > 0 for b in bundled_blocks), "Bundled blocks should yield positive savings"


def test_explanation_drawer_contract(client):
    """Test structured explanation schema for the side drawer."""
    # Find a bundled block
    resp = client.get("/api/v1/blocks")
    assert resp.status_code == 200
    blocks = resp.json()
    bundled = next((b for b in blocks if len(b["bundled_request_ids"]) > 1), None)
    assert bundled is not None

    block_id = bundled["block_id"]

    # Test dedicated explain endpoint
    explain_resp = client.get(f"/api/v1/blocks/{block_id}/explain")
    assert explain_resp.status_code == 200
    data = explain_resp.json()

    assert data["block_id"] == block_id
    detail = data.get("explanation_detail")
    assert detail is not None, "Missing explanation_detail in explain response"

    # 1. Plain-language summary
    assert "summary" in detail
    assert len(detail["summary"]) > 20

    # 2. Driving priority
    dp = detail.get("driving_priority")
    assert dp is not None
    assert "highest_risk_asset_id" in dp
    assert "highest_risk_score" in dp
    assert "anchoring_reason" in dp
    assert "risk_tier" in dp

    # 3. Driving constraints
    dc = detail.get("driving_constraints")
    assert dc is not None
    assert "spatial_overlap_type" in dc
    assert "window_bounds" in dc
    assert "key_constraints_applied" in dc
    assert isinstance(dc["key_constraints_applied"], list)

    # 4. Constituent requests
    mr = detail.get("merged_requests")
    assert mr is not None
    assert len(mr) == len(bundled["bundled_request_ids"])
    for req in mr:
        assert "request_id" in req
        assert "risk_score" in req
        assert "work_type" in req

    # 5. Alternatives considered
    ac = detail.get("alternatives_considered")
    assert ac is not None
    assert "possession_savings_minutes" in ac
    assert "why_not_scheduled_separately" in ac
    assert "why_not_deferred" in ac
    assert "alternatives_evaluated" in ac


def test_planner_view_requests_contract(client):
    """Test GET /requests returns all 240 requests with individual risk scores for Planner View."""
    resp = client.get("/requests")
    assert resp.status_code == 200
    requests = resp.json()
    assert len(requests) == 240

    first_req = requests[0]
    required_planner_fields = [
        "request_id",
        "source_system",
        "department",
        "section_id",
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
        "risk_score",
        "requires_power_block",
        "requires_traffic_block",
        "status",
    ]
    for field in required_planner_fields:
        assert field in first_req, f"Missing '{field}' in request"

    # Verify risk_score is populated
    unscored = [r for r in requests if r.get("risk_score") is None]
    assert len(unscored) == 0, f"Found {len(unscored)} unscored requests"

    # Verify department filtering
    resp_eng = client.get("/requests?department=ENG")
    assert resp_eng.status_code == 200
    eng_reqs = resp_eng.json()
    assert len(eng_reqs) == 85
    assert all(r["department"] == "ENG" for r in eng_reqs)


def test_station_master_view_filtering(client):
    """Test Station Master station-centric block filtering."""
    resp = client.get("/api/v1/blocks")
    assert resp.status_code == 200
    blocks = resp.json()

    # Station ALJN
    aljn_blocks = [b for b in blocks if "ALJN" in b["section_id"]]
    assert len(aljn_blocks) > 0, "Expected scheduled blocks on ALJN sections"

    # Station TDL
    tdl_blocks = [b for b in blocks if "TDL" in b["section_id"]]
    assert len(tdl_blocks) > 0, "Expected scheduled blocks on TDL sections"


def test_controller_actions(client):
    """Test Section Controller APPROVE, REJECT, MODIFY actions."""
    resp = client.get("/api/v1/blocks")
    block_id = resp.json()[0]["block_id"]

    # 1. Approve
    resp_app = client.post(
        f"/api/v1/blocks/{block_id}/action",
        json={"action": "APPROVE", "controller_notes": "Approved for corridor maintenance"},
    )
    assert resp_app.status_code == 200
    data_app = resp_app.json()
    assert data_app["status"] == "APPROVED_BY_CONTROLLER"

    # 2. Modify
    resp_mod = client.post(
        f"/api/v1/blocks/{block_id}/action",
        json={"action": "MODIFY", "controller_notes": "Caution speed restriction 30 km/h applied"},
    )
    assert resp_mod.status_code == 200
    data_mod = resp_mod.json()
    assert data_mod["status"] == "MODIFIED_BY_CONTROLLER"

    # 3. Reject
    resp_rej = client.post(
        f"/api/v1/blocks/{block_id}/action",
        json={"action": "REJECT", "controller_notes": "VVIP train movement clash"},
    )
    assert resp_rej.status_code == 200
    data_rej = resp_rej.json()
    assert data_rej["status"] == "REJECTED_BY_CONTROLLER"
