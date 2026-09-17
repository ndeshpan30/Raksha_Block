import os
import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, DATA_DIR
from app.models import SectionModel, MaintenanceRequestModel
from app.schemas import MaintenanceRequestResponse
from app.validation import validate_section, validate_maintenance_request
from app.ingestion import ingest_sections, ingest_requests, ingest_from_files
from app.main import app


@pytest.fixture
def test_db_session(tmp_path):
    """Isolated SQLite database in a temporary directory for tests."""
    db_file = tmp_path / "test_raksha.db"
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
def sample_section_data():
    return {
        "section_id": "SEC-TEST-01",
        "name": "Test Station A - Test Station B",
        "line_type": "DOUBLE",
        "start_station": "STA",
        "end_station": "STB",
        "start_km": 10.0,
        "end_km": 50.0,
        "max_speed_kmh": 120,
        "traffic_density_index": 1.5,
    }


@pytest.fixture
def sample_request_data():
    return {
        "request_id": "REQ-20260915-ENG-9999",
        "source_system": "TMS",
        "department": "ENG",
        "section_id": "SEC-TEST-01",
        "corridor_slot": "SLOT_NIGHT",
        "chainage_start": 15.0,
        "chainage_end": 18.0,
        "requested_window_start": "2026-09-15T01:00:00",
        "requested_window_end": "2026-09-15T04:00:00",
        "required_duration_minutes": 120,
        "work_type": "Track Tamping (BCM/CSM Machine)",
        "asset_id": "ENG-TRK-TEST-9999",
        "asset_type": "Ballast & Sleeper Bed",
        "asset_age_years": 4.5,
        "last_maintenance_days_ago": 90,
        "past_breakdown_count": 1,
        "gross_million_tonnes": 25.0,
        "condition_score": 6.5,
        "urgency_category": "MEDIUM",
        "requires_power_block": True,
        "requires_traffic_block": True,
        "status": "PENDING",
    }


# ==============================================================================
# 1. Basic Validation Unit Tests
# ==============================================================================

def test_validate_section_valid(sample_section_data):
    is_valid, errs, normalized = validate_section(sample_section_data)
    assert is_valid is True
    assert len(errs) == 0
    assert normalized["section_id"] == "SEC-TEST-01"
    assert normalized["start_km"] == 10.0


def test_validate_section_missing_fields():
    broken = {"section_id": "SEC-INCOMPLETE"}
    is_valid, errs, _ = validate_section(broken)
    assert is_valid is False
    assert any("Missing required field" in e for e in errs)


def test_validate_section_invalid_km(sample_section_data):
    bad = dict(sample_section_data)
    bad["start_km"] = 60.0
    bad["end_km"] = 50.0  # start >= end
    is_valid, errs, _ = validate_section(bad)
    assert is_valid is False
    assert any("strictly less than" in e for e in errs)


def test_validate_request_valid(sample_request_data):
    is_valid, errs, normalized = validate_maintenance_request(
        sample_request_data,
        known_section_ids={"SEC-TEST-01"},
    )
    assert is_valid is True
    assert len(errs) == 0
    assert normalized["request_id"] == "REQ-20260915-ENG-9999"
    assert isinstance(normalized["requested_window_start"], datetime)
    assert "asset_age_or_condition_features" in normalized


def test_validate_request_missing_fields():
    broken = {"request_id": "REQ-BROKEN"}
    is_valid, errs, _ = validate_maintenance_request(broken)
    assert is_valid is False
    assert len(errs) > 0
    assert any("Missing required field" in e for e in errs)


def test_validate_request_invalid_department(sample_request_data):
    bad = dict(sample_request_data)
    bad["department"] = "FINANCE"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("Invalid department" in e for e in errs)


def test_validate_request_invalid_source_system(sample_request_data):
    bad = dict(sample_request_data)
    bad["source_system"] = "EXCEL_SHEET"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("Invalid source_system" in e for e in errs)


def test_validate_request_inverted_chainage(sample_request_data):
    bad = dict(sample_request_data)
    bad["chainage_start"] = 25.0
    bad["chainage_end"] = 20.0
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("strictly less than" in e for e in errs)


def test_validate_request_inverted_window(sample_request_data):
    bad = dict(sample_request_data)
    bad["requested_window_start"] = "2026-09-15T05:00:00"
    bad["requested_window_end"] = "2026-09-15T03:00:00"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("must precede" in e for e in errs)


def test_validate_request_duration_exceeds_window(sample_request_data):
    bad = dict(sample_request_data)
    # Window is 3 hours (180 mins), duration is 240 mins
    bad["required_duration_minutes"] = 240
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("exceeds requested window" in e for e in errs)


def test_validate_request_unknown_section(sample_request_data):
    is_valid, errs, _ = validate_maintenance_request(
        sample_request_data,
        known_section_ids={"SEC-DIFFERENT-01"},
    )
    assert is_valid is False
    assert any("does not exist in track topology" in e for e in errs)


# ==============================================================================
# 2. Ingestion Pipeline & Persistence Tests
# ==============================================================================

def test_ingest_from_json_files(test_db_session):
    req_path = str(DATA_DIR / "maintenance_requests.json")
    sec_path = str(DATA_DIR / "sections.json")

    result = ingest_from_files(
        db=test_db_session,
        requests_path=req_path,
        sections_path=sec_path,
    )

    assert result.sections_ingested == 8
    assert result.requests_ingested == 240
    assert result.requests_rejected == 0
    assert len(result.validation_errors) == 0

    # Verify directly in SQLite DB
    sec_count = test_db_session.query(SectionModel).count()
    req_count = test_db_session.query(MaintenanceRequestModel).count()
    assert sec_count == 8
    assert req_count == 240


def test_ingest_from_csv_files(test_db_session):
    req_csv = str(DATA_DIR / "maintenance_requests.csv")
    sec_csv = str(DATA_DIR / "sections.csv")

    result = ingest_from_files(
        db=test_db_session,
        requests_path=req_csv,
        sections_path=sec_csv,
    )

    assert result.sections_ingested == 8
    assert result.requests_ingested == 240
    assert result.requests_rejected == 0


def test_ingestion_idempotency(test_db_session):
    req_path = str(DATA_DIR / "maintenance_requests.json")
    sec_path = str(DATA_DIR / "sections.json")

    # Run 1
    res1 = ingest_from_files(db=test_db_session, requests_path=req_path, sections_path=sec_path)
    assert res1.requests_ingested == 240

    # Run 2 (re-ingesting should upsert without duplicate primary key crash)
    res2 = ingest_from_files(db=test_db_session, requests_path=req_path, sections_path=sec_path)
    assert res2.requests_ingested == 240

    # Total row count should remain exactly 240
    assert test_db_session.query(MaintenanceRequestModel).count() == 240


def test_ingestion_rejects_malformed_records(test_db_session, sample_section_data, sample_request_data):
    # Ingest 1 section
    ingest_sections(test_db_session, [sample_section_data])

    good_req = dict(sample_request_data)
    bad_req_1 = dict(sample_request_data)
    bad_req_1["request_id"] = "REQ-BAD-01"
    bad_req_1["chainage_start"] = 999.0
    bad_req_1["chainage_end"] = 100.0  # inverted

    bad_req_2 = {"request_id": "REQ-BAD-02"}  # missing fields

    ingested, rejected, errors = ingest_requests(
        test_db_session,
        [good_req, bad_req_1, bad_req_2],
        known_section_ids={"SEC-TEST-01"},
    )

    assert ingested == 1
    assert rejected == 2
    assert len(errors) == 2
    assert test_db_session.query(MaintenanceRequestModel).count() == 1


# ==============================================================================
# 3. FastAPI GET /requests Endpoint Integration Tests
# ==============================================================================

@pytest.fixture
def api_client(test_db_session):
    # Ingest canonical data into test session
    ingest_from_files(
        db=test_db_session,
        requests_path=str(DATA_DIR / "maintenance_requests.json"),
        sections_path=str(DATA_DIR / "sections.json"),
    )

    # Override get_db dependency to use isolated test session
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_fastapi_get_requests_all(api_client):
    response = api_client.get("/requests")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 240

    # Verify first record fields match ARCHITECTURE.md specification
    first = data[0]
    expected_fields = [
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
        "risk_score",
        "requires_power_block",
        "requires_traffic_block",
        "status",
    ]
    for field in expected_fields:
        assert field in first, f"Field '{field}' missing from API response JSON"

    assert isinstance(first["asset_age_or_condition_features"], dict)
    assert first["status"] == "PENDING"


def test_fastapi_get_requests_filtering(api_client):
    # Department filter
    resp_eng = api_client.get("/requests?department=ENG")
    assert resp_eng.status_code == 200
    eng_records = resp_eng.json()
    assert len(eng_records) == 85
    assert all(r["department"] == "ENG" for r in eng_records)

    # Section ID filter
    resp_sec = api_client.get("/requests?section_id=SEC-NDLS-TKJ")
    assert resp_sec.status_code == 200
    sec_records = resp_sec.json()
    assert len(sec_records) > 0
    assert all(r["section_id"] == "SEC-NDLS-TKJ" for r in sec_records)

    # Limit and offset pagination
    resp_lim = api_client.get("/requests?limit=10&offset=5")
    assert resp_lim.status_code == 200
    lim_records = resp_lim.json()
    assert len(lim_records) == 10


def test_fastapi_alias_endpoint(api_client):
    # /api/v1/requests matches ARCHITECTURE.md endpoint table
    response = api_client.get("/api/v1/requests?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_validate_section_invalid_line_type(sample_section_data):
    bad = dict(sample_section_data)
    bad["line_type"] = "HEXADECIMAL"
    is_valid, errs, _ = validate_section(bad)
    assert is_valid is False
    assert any("Invalid line_type" in e for e in errs)


def test_validate_request_invalid_corridor_slot(sample_request_data):
    bad = dict(sample_request_data)
    bad["corridor_slot"] = "SLOT_MIDNIGHT"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("Invalid corridor_slot" in e for e in errs)


def test_validate_request_invalid_status(sample_request_data):
    bad = dict(sample_request_data)
    bad["status"] = "NON_EXISTENT_STATUS"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("Invalid status" in e for e in errs)


def test_validate_request_invalid_boolean_string(sample_request_data):
    bad = dict(sample_request_data)
    bad["requires_power_block"] = "maybe"
    is_valid, errs, _ = validate_maintenance_request(bad)
    assert is_valid is False
    assert any("Invalid boolean value" in e for e in errs)


def test_validate_request_chainage_out_of_section_bounds(sample_request_data):
    # Section is 10.0 to 50.0 km
    known_sections = {
        "SEC-TEST-01": {"start_km": 10.0, "end_km": 50.0}
    }

    # Test chainage_start before section start_km
    bad_start = dict(sample_request_data)
    bad_start["chainage_start"] = 5.0
    bad_start["chainage_end"] = 15.0
    is_valid, errs, _ = validate_maintenance_request(bad_start, known_sections=known_sections)
    assert is_valid is False
    assert any("before section start_km" in e for e in errs)

    # Test chainage_end beyond section end_km
    bad_end = dict(sample_request_data)
    bad_end["chainage_start"] = 45.0
    bad_end["chainage_end"] = 55.0
    is_valid, errs, _ = validate_maintenance_request(bad_end, known_sections=known_sections)
    assert is_valid is False
    assert any("exceeds section end_km" in e for e in errs)


def test_validate_request_string_float_integers(sample_request_data):
    # CSVs or serialized data may represent integers as "120.0"
    data = dict(sample_request_data)
    data["required_duration_minutes"] = "120.0"
    data["last_maintenance_days_ago"] = "90.0"
    data["past_breakdown_count"] = "1.0"
    is_valid, errs, normalized = validate_maintenance_request(data)
    assert is_valid is True
    assert len(errs) == 0
    assert normalized["required_duration_minutes"] == 120
    assert normalized["last_maintenance_days_ago"] == 90
    assert normalized["past_breakdown_count"] == 1


def test_fastapi_get_requests_limit_zero(api_client):
    # Querying limit=0 must return an empty list, NOT all 240 records
    response = api_client.get("/requests?limit=0")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_fastapi_get_requests_validation_errors(api_client):
    # Negative limit must return HTTP 422 Unprocessable Entity
    resp_bad_limit = api_client.get("/requests?limit=-1")
    assert resp_bad_limit.status_code == 422

    # Negative offset must return HTTP 422 Unprocessable Entity
    resp_bad_offset = api_client.get("/requests?offset=-5")
    assert resp_bad_offset.status_code == 422


def test_fastapi_get_requests_offset_exceeds_total(api_client):
    response = api_client.get("/requests?offset=99999")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_ingestion_empty_csv_file(test_db_session, tmp_path):
    empty_csv = tmp_path / "empty_requests.csv"
    empty_csv.write_text("request_id,source_system\n", encoding="utf-8")
    sec_json = str(DATA_DIR / "sections.json")

    res = ingest_from_files(
        db=test_db_session,
        requests_path=str(empty_csv),
        sections_path=sec_json,
    )
    assert res.requests_ingested == 0
    assert res.requests_rejected == 0
    assert len(res.validation_errors) == 0


def test_schema_feature_container_auto_population_when_db_null():
    raw_dict = {
        "request_id": "REQ-TEST-SCHEMA",
        "source_system": "TMS",
        "department": "ENG",
        "section_id": "SEC-TEST-01",
        "corridor_slot": "SLOT_NIGHT",
        "chainage_start": 10.0,
        "chainage_end": 12.0,
        "requested_window_start": datetime.now(),
        "requested_window_end": datetime.now(),
        "required_duration_minutes": 60,
        "work_type": "Track Tamping",
        "asset_id": "ENG-TRK-TEST",
        "asset_type": "Ballast",
        "asset_age_years": 3.0,
        "last_maintenance_days_ago": 45,
        "past_breakdown_count": 1,
        "gross_million_tonnes": 20.0,
        "condition_score": 7.5,
        "urgency_category": "MEDIUM",
        "asset_age_or_condition_features": None,
        "asset_condition_features": None,
        "requires_power_block": False,
        "requires_traffic_block": True,
        "status": "PENDING",
    }
    resp = MaintenanceRequestResponse.model_validate(raw_dict)
    assert isinstance(resp.asset_age_or_condition_features, dict)
    assert isinstance(resp.asset_condition_features, dict)
    assert resp.asset_age_or_condition_features["asset_age_years"] == 3.0
    assert resp.asset_condition_features["condition_score"] == 7.5
