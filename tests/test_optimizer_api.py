"""
RAKSHA-BLOCK: Integration Tests for Optimization API Endpoints
SIH26027 — Phase 4 Core Optimizer
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import SectionModel, MaintenanceRequestModel
from app.main import app
from tests.test_optimizer_handcrafted import get_handcrafted_test_requests


@pytest.fixture
def test_db_session(tmp_path):
    """Isolated SQLite database in a temporary directory for tests."""
    db_file = tmp_path / "test_raksha_opt.db"
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


def test_optimize_endpoint_with_custom_payload(client):
    """POST /optimize with explicit request payload should return optimized block plan."""
    requests = get_handcrafted_test_requests()
    payload = {
        "requests": requests,
        "spatial_proximity_km": 2.0,
        "max_block_km_span": 15.0,
    }

    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "OPTIMAL"
    assert data["total_requests_in"] == 7
    assert data["total_blocks_out"] == 4
    assert data["bundled_blocks_count"] == 2
    assert data["single_blocks_count"] == 2
    assert data["total_savings_minutes"] == 250
    assert len(data["blocks"]) == 4

    # Check that constituent_requests is present in each block
    for b in data["blocks"]:
        assert "block_id" in b
        assert "departments_involved" in b
        assert "constituent_requests" in b
        assert len(b["constituent_requests"]) == len(b["bundled_request_ids"])


def test_optimizer_alias_endpoint(client):
    """POST /api/v1/optimizer/plan alias should return identical results."""
    requests = get_handcrafted_test_requests()
    payload = {"requests": requests}

    response = client.post("/api/v1/optimizer/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPTIMAL"
    assert data["total_requests_in"] == 7
    assert data["total_blocks_out"] == 4


def test_optimize_endpoint_empty_db_no_payload(client):
    """POST /optimize with no body and empty database returns empty result."""
    response = client.post("/optimize", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPTIMAL"
    assert data["total_requests_in"] == 0
    assert data["total_blocks_out"] == 0
    assert data["blocks"] == []


def test_optimize_endpoint_with_db_records(client, test_db_session):
    """POST /optimize without body should optimize requests stored in database."""
    # Seed a section and 2 overlapping requests
    from datetime import datetime
    sec = SectionModel(
        section_id="SEC-TEST-01",
        name="Test A - Test B",
        line_type="DOUBLE",
        start_station="STA",
        end_station="STB",
        start_km=0.0,
        end_km=20.0,
        max_speed_kmh=120,
        traffic_density_index=1.5,
    )
    test_db_session.add(sec)
    test_db_session.commit()

    req1 = MaintenanceRequestModel(
        request_id="REQ-DB-01",
        source_system="TMS",
        department="ENG",
        section_id="SEC-TEST-01",
        corridor_slot="SLOT_NIGHT",
        chainage_start=5.0,
        chainage_end=7.0,
        requested_window_start=datetime(2026, 9, 15, 0, 30),
        requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=120,
        work_type="Track Tamping",
        asset_id="ENG-001",
        asset_type="Track",
        asset_age_years=5.0,
        last_maintenance_days_ago=60,
        past_breakdown_count=0,
        gross_million_tonnes=30.0,
        condition_score=8.0,
        urgency_category="LOW",
        risk_score=20.0,
        requires_power_block=False,
        requires_traffic_block=True,
        status="PENDING",
    )
    req2 = MaintenanceRequestModel(
        request_id="REQ-DB-02",
        source_system="TDMS",
        department="TRD",
        section_id="SEC-TEST-01",
        corridor_slot="SLOT_NIGHT",
        chainage_start=5.2,
        chainage_end=6.8,
        requested_window_start=datetime(2026, 9, 15, 0, 30),
        requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=90,
        work_type="OHE Overhaul",
        asset_id="TRD-001",
        asset_type="OHE Wire",
        asset_age_years=7.0,
        last_maintenance_days_ago=120,
        past_breakdown_count=1,
        gross_million_tonnes=30.0,
        condition_score=7.0,
        urgency_category="MEDIUM",
        risk_score=40.0,
        requires_power_block=True,
        requires_traffic_block=True,
        status="PENDING",
    )
    test_db_session.add(req1)
    test_db_session.add(req2)
    test_db_session.commit()

    # Call /optimize without requests payload -> should pull from DB
    response = client.post("/optimize", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests_in"] == 2
    # Both are on SEC-TEST-01 at km 5-7 during night corridor -> 1 bundled block!
    assert data["total_blocks_out"] == 1
    assert data["bundled_blocks_count"] == 1
    b = data["blocks"][0]
    assert set(b["bundled_request_ids"]) == {"REQ-DB-01", "REQ-DB-02"}
    assert set(b["departments_involved"]) == {"ENG", "TRD"}
    assert b["power_block_granted"] is True
    assert b["traffic_block_granted"] is True
    assert b["savings_minutes"] == 90  # (120 + 90) - 120


def test_optimize_endpoint_with_query_filter(client, test_db_session):
    """POST /optimize with section_id filter optimizes only that section."""
    from datetime import datetime
    sec1 = SectionModel(
        section_id="SEC-A", name="A", line_type="DOUBLE", start_station="S1", end_station="S2",
        start_km=0.0, end_km=20.0, max_speed_kmh=120, traffic_density_index=1.0,
    )
    sec2 = SectionModel(
        section_id="SEC-B", name="B", line_type="DOUBLE", start_station="S3", end_station="S4",
        start_km=0.0, end_km=20.0, max_speed_kmh=120, traffic_density_index=1.0,
    )
    test_db_session.add(sec1)
    test_db_session.add(sec2)
    test_db_session.commit()

    r1 = MaintenanceRequestModel(
        request_id="R1", source_system="TMS", department="ENG", section_id="SEC-A",
        corridor_slot="SLOT_NIGHT", chainage_start=1.0, chainage_end=2.0,
        requested_window_start=datetime(2026, 9, 15, 0, 30), requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=60, work_type="Work 1", asset_id="A1", asset_type="T",
        asset_age_years=1.0, last_maintenance_days_ago=10, past_breakdown_count=0, gross_million_tonnes=10.0,
        condition_score=9.0, urgency_category="LOW", risk_score=10.0, requires_power_block=False,
        requires_traffic_block=True, status="PENDING",
    )
    r2 = MaintenanceRequestModel(
        request_id="R2", source_system="TMS", department="ENG", section_id="SEC-B",
        corridor_slot="SLOT_NIGHT", chainage_start=1.0, chainage_end=2.0,
        requested_window_start=datetime(2026, 9, 15, 0, 30), requested_window_end=datetime(2026, 9, 15, 4, 30),
        required_duration_minutes=60, work_type="Work 2", asset_id="A2", asset_type="T",
        asset_age_years=1.0, last_maintenance_days_ago=10, past_breakdown_count=0, gross_million_tonnes=10.0,
        condition_score=9.0, urgency_category="LOW", risk_score=10.0, requires_power_block=False,
        requires_traffic_block=True, status="PENDING",
    )
    test_db_session.add(r1)
    test_db_session.add(r2)
    test_db_session.commit()

    response = client.post("/optimize?section_id=SEC-A")
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests_in"] == 1
    assert data["blocks"][0]["section_id"] == "SEC-A"


def test_optimize_endpoint_negative_proximity_validation(client):
    """POST /optimize with invalid negative spatial_proximity_km returns HTTP 422."""
    payload = {"spatial_proximity_km": -5.0}
    response = client.post("/optimize", json=payload)
    assert response.status_code == 422
