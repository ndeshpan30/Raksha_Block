"""
RAKSHA-BLOCK: Phase 7 Interactive Re-Optimization Test Suite
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination

Verifies:
1. Baseline CP-SAT solve vs Localized Delta Re-optimization contract.
2. Time window shifting (+1h, +2h) with delta_mode=True.
3. Urgency category toggles (LOW -> CRITICAL) triggering LightGBM risk recalculation.
4. Auto-detection of modified request IDs when omitted from payload.
5. Sub-second (< 300-500ms) re-solve latency on full dataset.
6. Visual delta flags (is_modified, delta_type) and updated Phase 5 explanations.
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.optimizer import (
    clear_subproblem_cache,
    optimize_requests,
    OptimizerConfig,
    normalize_request_dict,
)
from app.risk_model import predict_risk_score, get_risk_tier
from tests.test_optimizer_handcrafted import get_handcrafted_test_requests


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_delta_reoptimization_handcrafted():
    """Test localized delta re-optimization on handcrafted test requests."""
    clear_subproblem_cache()
    requests = get_handcrafted_test_requests()

    # 1. Baseline solve (Full fleet)
    cfg_base = OptimizerConfig(delta_mode=False)
    base_result = optimize_requests(requests, cfg_base)
    assert base_result.status == "OPTIMAL"
    assert base_result.reoptimization_mode == "FULL"
    assert len(base_result.blocks) == 4

    # 2. Modify one request (shift time window start by +1 hour)
    modified_reqs = [dict(r) for r in requests]
    # REQ-001 is on SEC-001 in SLOT_NIGHT (00:00 - 04:00)
    target_req = modified_reqs[0]
    target_id = target_req["request_id"]
    target_req["requested_window_start"] = "2026-09-15T01:00:00"
    target_req["requested_window_end"] = "2026-09-15T04:30:00"

    # 3. Delta re-solve
    cfg_delta = OptimizerConfig(delta_mode=True, modified_request_ids=[target_id])
    t0 = time.perf_counter()
    delta_result = optimize_requests(modified_reqs, cfg_delta)
    t1 = time.perf_counter()

    assert delta_result.status == "OPTIMAL"
    assert delta_result.reoptimization_mode == "LOCALIZED_DELTA"
    assert target_id in delta_result.delta_request_ids
    assert delta_result.affected_blocks_count >= 1

    # Check that modified block is flagged
    mod_blocks = [b for b in delta_result.blocks if target_id in b.bundled_request_ids]
    assert len(mod_blocks) == 1
    assert mod_blocks[0].is_modified is True
    assert mod_blocks[0].delta_type == "REOPTIMIZED"

    # Delta solve should be fast (< 200ms for 7 requests)
    assert (t1 - t0) < 0.2


def test_delta_reoptimization_urgency_toggle_and_risk():
    """Verify toggling urgency updates risk score and re-optimizes scheduling."""
    clear_subproblem_cache()
    requests = get_handcrafted_test_requests()

    # Baseline solve
    optimize_requests(requests, OptimizerConfig(delta_mode=False))

    # Toggle urgency on REQ-002 from LOW to CRITICAL
    modified_reqs = [dict(r) for r in requests]
    req2 = modified_reqs[1]
    req2_id = req2["request_id"]
    req2["urgency_category"] = "CRITICAL"
    req2["risk_score"] = None  # Force recompute with LightGBM

    cfg_delta = OptimizerConfig(
        delta_mode=True,
        modified_request_ids=[req2_id],
        recompute_risk=True,
    )
    delta_result = optimize_requests(modified_reqs, cfg_delta)

    assert delta_result.reoptimization_mode == "LOCALIZED_DELTA"
    mod_block = [b for b in delta_result.blocks if req2_id in b.bundled_request_ids][0]
    assert mod_block.is_modified is True

    # Check updated constituent risk
    constituent = [c for c in mod_block.constituent_requests if c["request_id"] == req2_id][0]
    assert constituent["risk_score"] > 0.0


def test_api_optimize_delta_mode_endpoint(client):
    """Verify POST /optimize supports delta_mode and returns visual delta flags."""
    # Fetch all requests from API
    reqs_resp = client.get("/requests")
    assert reqs_resp.status_code == 200
    all_reqs = reqs_resp.json()
    assert len(all_reqs) == 240

    # Ensure baseline is cached
    client.post("/optimize", json={})

    # Pick a request to modify: shift window by +1 hour
    test_req = dict(all_reqs[0])
    test_id = test_req["request_id"]
    test_req["requested_window_start"] = "2026-09-15T02:30:00"
    test_req["requested_window_end"] = "2026-09-15T05:30:00"

    modified_list = [test_req if r["request_id"] == test_id else dict(r) for r in all_reqs]

    payload = {
        "requests": modified_list,
        "delta_mode": True,
        "modified_request_ids": [test_id],
    }

    t0 = time.perf_counter()
    resp = client.post("/optimize", json=payload)
    t1 = time.perf_counter()

    assert resp.status_code == 200
    data = resp.json()

    assert data["reoptimization_mode"] == "LOCALIZED_DELTA"
    assert test_id in data["delta_request_ids"]
    assert data["total_requests_in"] == 240
    assert data["total_blocks_out"] == 177

    # Verify latency: solve_time_seconds must be sub-second (< 0.5s)
    solve_time = data["solve_time_seconds"]
    wall_time = t1 - t0
    assert solve_time < 0.5, f"Solve time {solve_time}s exceeded 0.5s target"
    assert wall_time < 1.0, f"Total wall time {wall_time}s exceeded 1.0s target"

    # Find the block containing the modified request
    mod_block = [b for b in data["blocks"] if test_id in b["bundled_request_ids"]][0]
    assert mod_block["is_modified"] is True
    assert mod_block["delta_type"] == "REOPTIMIZED"


def test_api_optimize_auto_detect_modified_requests(client):
    """Verify POST /optimize auto-detects modified requests when modified_request_ids is omitted."""
    reqs_resp = client.get("/requests")
    assert reqs_resp.status_code == 200
    all_reqs = reqs_resp.json()

    # Ensure baseline cached
    client.post("/optimize", json={})

    # Modify duration on second request
    test_req = dict(all_reqs[1])
    test_id = test_req["request_id"]
    test_req["required_duration_minutes"] = test_req["required_duration_minutes"] + 30

    modified_list = [test_req if r["request_id"] == test_id else dict(r) for r in all_reqs]

    # Send with delta_mode=True but WITHOUT modified_request_ids
    payload = {
        "requests": modified_list,
        "delta_mode": True,
    }

    resp = client.post("/optimize", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["reoptimization_mode"] == "LOCALIZED_DELTA"
    assert test_id in data["delta_request_ids"]

    mod_block = [b for b in data["blocks"] if test_id in b["bundled_request_ids"]][0]
    assert mod_block["is_modified"] is True


def test_full_dataset_latency_benchmark(client):
    """
    Measures and compares full fleet solve (~4.4-8.4s) vs localized delta re-solve (< 100ms)
    on the complete 240-request Indian Railways dataset.
    """
    # 1. Full fleet re-solve
    t0 = time.perf_counter()
    full_resp = client.post("/optimize", json={"delta_mode": False})
    t1 = time.perf_counter()
    assert full_resp.status_code == 200
    full_data = full_resp.json()
    full_solve_time = full_data["solve_time_seconds"]

    # 2. Localized delta re-solve
    all_reqs = client.get("/requests").json()
    mod_req = dict(all_reqs[5])
    mod_id = mod_req["request_id"]
    mod_req["urgency_category"] = "CRITICAL"
    mod_list = [mod_req if r["request_id"] == mod_id else dict(r) for r in all_reqs]

    t2 = time.perf_counter()
    delta_resp = client.post("/optimize", json={
        "requests": mod_list,
        "delta_mode": True,
        "modified_request_ids": [mod_id],
        "recompute_risk": True,
    })
    t3 = time.perf_counter()
    assert delta_resp.status_code == 200
    delta_data = delta_resp.json()
    delta_solve_time = delta_data["solve_time_seconds"]

    print(f"\n[BENCHMARK] Full 240-req Solve Time: {full_solve_time:.4f}s (wall: {t1-t0:.3f}s)")
    print(f"[BENCHMARK] Localized Delta Solve Time: {delta_solve_time:.4f}s (wall: {t3-t2:.3f}s)")
    print(f"[BENCHMARK] Speedup Factor: {full_solve_time / max(delta_solve_time, 0.001):.1f}x")

    # Full solve is around 4-8s; delta solve MUST be < 0.25s (250ms)
    assert delta_solve_time < 0.25
    assert (full_solve_time / max(delta_solve_time, 0.001)) > 10.0
