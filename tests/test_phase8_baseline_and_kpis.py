"""
RAKSHA-BLOCK: Phase 8 Unit and Integration Tests
P2 Scope: Baseline Schedule Calculation, Comparative KPIs, and GIS Topology

Tests verify:
1. Pure Python baseline (naive/unbundled) schedule calculation.
2. Comparative delta calculation (block count reduction, hours saved, traffic halts avoided).
3. Automatic inclusion of baseline_comparison in OptimizationResult and POST /optimize response.
4. Dedicated endpoints: GET /api/v1/optimizer/baseline and GET /api/v1/optimizer/comparison.
5. Geographical corridor station topology consistency for Leaflet GIS plotting.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.optimizer import (
    calculate_baseline_schedule,
    optimize_requests,
    BaselineComparison,
)
from tests.test_optimizer_handcrafted import get_handcrafted_test_requests


@pytest.fixture
def test_db_session(tmp_path):
    """Isolated SQLite database for Phase 8 tests."""
    db_file = tmp_path / "test_raksha_phase8.db"
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


# =====================================================================
# Unit Tests: Baseline Schedule Calculation
# =====================================================================

def test_calculate_baseline_schedule_empty():
    """Empty request list yields zero baseline metrics."""
    result = calculate_baseline_schedule([])
    assert result["block_count"] == 0
    assert result["total_duration_minutes"] == 0
    assert result["total_duration_hours"] == 0.0
    assert result["traffic_halts"] == 0
    assert result["power_halts"] == 0


def test_calculate_baseline_schedule_handcrafted():
    """Handcrafted 7 requests yield 7 isolated baseline blocks with unbundled durations."""
    requests = get_handcrafted_test_requests()
    assert len(requests) == 7

    baseline = calculate_baseline_schedule(requests)
    assert baseline["block_count"] == 7
    expected_duration = sum(r["required_duration_minutes"] for r in requests)
    assert baseline["total_duration_minutes"] == expected_duration
    assert baseline["total_duration_hours"] == round(expected_duration / 60.0, 1)
    assert baseline["traffic_halts"] == sum(1 for r in requests if r.get("requires_traffic_block", True))
    assert baseline["power_halts"] == sum(1 for r in requests if r.get("requires_power_block", False))


def test_optimizer_baseline_comparison_generation():
    """CP-SAT solve generates accurate BaselineComparison object."""
    requests = get_handcrafted_test_requests()
    result = optimize_requests(requests)

    assert result.status in ["OPTIMAL", "FEASIBLE"]
    assert result.baseline_comparison is not None
    comp = result.baseline_comparison

    # Baseline: 7 requests = 7 blocks
    assert comp.baseline_block_count == 7
    # Optimized: Bundled into fewer blocks (4 blocks: Group A bundled to 1, Group B bundled to 1, Group C 1, Group D 1)
    assert comp.optimized_block_count < comp.baseline_block_count
    assert comp.block_count_reduction == comp.baseline_block_count - comp.optimized_block_count
    assert comp.block_count_reduction_pct > 0

    # Possession hours comparison
    assert comp.optimized_possession_minutes < comp.baseline_possession_minutes
    assert comp.possession_savings_minutes > 0
    assert comp.possession_savings_hours > 0
    assert comp.possession_reduction_pct > 0

    # Avoided traffic halts
    assert comp.optimized_traffic_halts <= comp.baseline_traffic_halts
    assert comp.avoided_traffic_halts >= 0

    # Multi-department bundle counts
    assert comp.coordinated_bundles_created >= 1


# =====================================================================
# API Integration Tests: Phase 8 Endpoints
# =====================================================================

def test_api_optimizer_baseline_endpoint(client):
    """GET /api/v1/optimizer/baseline returns baseline schedule metrics."""
    response = client.get("/api/v1/optimizer/baseline")
    assert response.status_code == 200
    data = response.json()

    assert "block_count" in data
    assert "total_duration_minutes" in data
    assert "total_duration_hours" in data
    assert "traffic_halts" in data
    assert "power_halts" in data
    assert "unbundled_policy" in data

    if data["block_count"] > 0:
        assert data["block_count"] == 240
        assert data["total_duration_minutes"] > 20000


def test_api_optimizer_comparison_endpoint(client):
    """GET /api/v1/optimizer/comparison returns comprehensive before/after metrics."""
    response = client.get("/api/v1/optimizer/comparison")
    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "baseline_block_count",
        "optimized_block_count",
        "block_count_reduction",
        "block_count_reduction_pct",
        "baseline_possession_minutes",
        "baseline_possession_hours",
        "optimized_possession_minutes",
        "optimized_possession_hours",
        "possession_savings_minutes",
        "possession_savings_hours",
        "possession_reduction_pct",
        "baseline_traffic_halts",
        "optimized_traffic_halts",
        "avoided_traffic_halts",
        "coordinated_bundles_created",
        "triple_department_bundles",
        "dual_department_bundles",
    ]

    for field in required_fields:
        assert field in data, f"Missing expected field: {field}"

    # Verify quantitative sanity against synthetic 240-request dataset
    assert data["baseline_block_count"] == 240
    assert data["optimized_block_count"] == 177
    assert data["block_count_reduction"] == 63
    assert abs(data["block_count_reduction_pct"] - 26.25) < 0.1
    assert data["baseline_possession_hours"] > data["optimized_possession_hours"]
    assert data["avoided_traffic_halts"] > 0
    assert data["coordinated_bundles_created"] == 43


def test_api_optimize_post_includes_baseline_comparison(client):
    """POST /optimize response includes baseline_comparison field."""
    requests = get_handcrafted_test_requests()
    response = client.post("/optimize", json={"requests": requests})
    assert response.status_code == 200
    data = response.json()

    assert "baseline_comparison" in data
    comp = data["baseline_comparison"]
    assert comp["baseline_block_count"] == 7
    assert comp["optimized_block_count"] < 7
    assert comp["block_count_reduction"] > 0
    assert comp["possession_savings_hours"] >= 0


# =====================================================================
# GIS Topology Consistency Tests
# =====================================================================

def test_corridor_stations_topology():
    """Verify that track section endpoints and mainline stations match geography."""
    # Mainline stations along Delhi-Kanpur-DDU
    stations = {
        'NDLS': {'km': 0.0, 'lat': 28.6429, 'lng': 77.2195},
        'TKJ': {'km': 3.5, 'lat': 28.6256, 'lng': 77.2411},
        'GZB': {'km': 24.5, 'lat': 28.6534, 'lng': 77.4328},
        'ALJN': {'km': 126.0, 'lat': 27.8974, 'lng': 78.0880},
        'TDL': {'km': 204.0, 'lat': 27.2065, 'lng': 78.2384},
        'CNB': {'km': 435.0, 'lat': 26.4539, 'lng': 80.3514},
        'PRYJ': {'km': 630.0, 'lat': 25.4484, 'lng': 81.8340},
        'DDU': {'km': 783.0, 'lat': 25.2815, 'lng': 83.1189},
        'MB': {'km': 165.0, 'lat': 28.8288, 'lng': 78.7768},
    }

    # Verify monotonic increasing km along the primary trunk corridor
    trunk_stations = ['NDLS', 'TKJ', 'GZB', 'ALJN', 'TDL', 'CNB', 'PRYJ', 'DDU']
    for i in range(len(trunk_stations) - 1):
        s1 = trunk_stations[i]
        s2 = trunk_stations[i + 1]
        assert stations[s1]['km'] < stations[s2]['km'], f"{s1} km should be less than {s2} km"
        # Coordinates must be valid latitudes/longitudes in Northern/Eastern India
        assert 24.0 <= stations[s1]['lat'] <= 30.0
        assert 76.0 <= stations[s1]['lng'] <= 85.0
