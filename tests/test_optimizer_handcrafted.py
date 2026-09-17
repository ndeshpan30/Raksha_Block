"""
RAKSHA-BLOCK: Unit & Functional Tests for CP-SAT Optimizer Handcrafted Example
SIH26027 — Phase 4 Core Optimizer
"""

import pytest
from datetime import datetime
from app.optimizer import (
    optimize_requests,
    OptimizerConfig,
    OptimizationResult,
    BundledBlock,
)


def get_handcrafted_test_requests():
    """
    Constructs a known, deterministic set of 7 maintenance requests:
    - Group A (Req 1, 2, 3): 3-department bundle on SEC-NDLS-TKJ (km 0.9-2.6) during SLOT_NIGHT.
    - Group B (Req 4, 5): 2-department bundle on SEC-TKJ-GZB (km 10.0-11.5) during SLOT_NIGHT.
    - Group C (Req 6): S&T single block on SEC-NDLS-TKJ in SLOT_AFTERNOON (temporal separation).
    - Group D (Req 7): ENG single block on SEC-TKJ-GZB at km 24.0 (spatial separation from Group B).
    """
    return [
        # Group A: Triple-Department Bundle on SEC-NDLS-TKJ
        {
            "request_id": "TEST-REQ-001",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.0,
            "chainage_end": 2.5,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 120,
            "work_type": "Track Tamping (BCM Machine)",
            "asset_id": "ENG-TRK-NDLS-001",
            "asset_type": "Ballast Track",
            "risk_score": 85.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "TEST-REQ-002",
            "department": "S&T",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.2,
            "chainage_end": 1.5,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 60,
            "work_type": "Point Machine Overhaul",
            "asset_id": "SNT-SIG-NDLS-001",
            "asset_type": "Electric Point Machine",
            "risk_score": 70.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "TEST-REQ-003",
            "department": "TRD",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 0.9,
            "chainage_end": 2.6,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 90,
            "work_type": "OHE Contact Wire Inspection",
            "asset_id": "TRD-OHE-NDLS-001",
            "asset_type": "OHE Contact Wire",
            "risk_score": 60.0,
            "requires_power_block": True,
            "requires_traffic_block": True,
        },
        # Group B: 2-Department Bundle on SEC-TKJ-GZB
        {
            "request_id": "TEST-REQ-004",
            "department": "ENG",
            "section_id": "SEC-TKJ-GZB",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 10.0,
            "chainage_end": 11.5,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 150,
            "work_type": "Through Rail Renewal (TRR)",
            "asset_id": "ENG-TRK-TKJ-001",
            "asset_type": "Continuous Welded Rail",
            "risk_score": 90.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "TEST-REQ-005",
            "department": "TRD",
            "section_id": "SEC-TKJ-GZB",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 10.2,
            "chainage_end": 11.0,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 100,
            "work_type": "Cantilever Dropper Adjustment",
            "asset_id": "TRD-OHE-TKJ-001",
            "asset_type": "Cantilever Mast Assembly",
            "risk_score": 40.0,
            "requires_power_block": True,
            "requires_traffic_block": True,
        },
        # Group C: Single S&T block in SLOT_AFTERNOON on SEC-NDLS-TKJ
        {
            "request_id": "TEST-REQ-006",
            "department": "S&T",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_AFTERNOON",
            "chainage_start": 1.2,
            "chainage_end": 1.5,
            "requested_window_start": "2026-09-15T15:00:00",
            "requested_window_end": "2026-09-15T18:30:00",
            "required_duration_minutes": 60,
            "work_type": "Digital Axle Counter Calibration",
            "asset_id": "SNT-SIG-NDLS-002",
            "asset_type": "Axle Counter Detection Point",
            "risk_score": 35.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        # Group D: Single ENG block on SEC-TKJ-GZB at km 24 (separated by 12.5 km from Group B)
        {
            "request_id": "TEST-REQ-007",
            "department": "ENG",
            "section_id": "SEC-TKJ-GZB",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 24.0,
            "chainage_end": 24.8,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T04:30:00",
            "required_duration_minutes": 75,
            "work_type": "Turnout Renewal",
            "asset_id": "ENG-TRK-TKJ-002",
            "asset_type": "Turnout Assembly",
            "risk_score": 50.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
    ]


def test_handcrafted_bundling_outcome():
    """Verify that the handcrafted example bundles exactly according to engineering logic."""
    requests = get_handcrafted_test_requests()
    config = OptimizerConfig(spatial_proximity_km=2.0)
    result: OptimizationResult = optimize_requests(requests, config)

    assert result.status == "OPTIMAL"
    assert result.total_requests_in == 7
    # 7 requests must consolidate into exactly 4 blocks: 2 bundled + 2 single
    assert result.total_blocks_out == 4
    assert result.bundled_blocks_count == 2
    assert result.single_blocks_count == 2

    # Verify duration metrics
    # Original: 120 + 60 + 90 + 150 + 100 + 60 + 75 = 655
    assert result.total_original_duration_minutes == 655
    # Bundled: max(120,60,90)=120, max(150,100)=150, 60, 75 = 405
    assert result.total_bundled_duration_minutes == 405
    assert result.total_savings_minutes == 250
    assert result.savings_percentage == pytest.approx(38.17, abs=0.1)

    # Verify Bundle 1 (Group A: REQ-001, REQ-002, REQ-003)
    b1 = next(b for b in result.blocks if "TEST-REQ-001" in b.bundled_request_ids)
    assert set(b1.bundled_request_ids) == {"TEST-REQ-001", "TEST-REQ-002", "TEST-REQ-003"}
    assert set(b1.departments_involved) == {"ENG", "S&T", "TRD"}
    assert b1.section_id == "SEC-NDLS-TKJ"
    assert b1.corridor_slot == "SLOT_NIGHT"
    assert b1.start_km == 0.9
    assert b1.end_km == 2.6
    assert b1.total_duration_minutes == 120
    assert b1.power_block_granted is True
    assert b1.traffic_block_granted is True
    assert b1.savings_minutes == 150  # (120 + 60 + 90) - 120

    # Verify Bundle 2 (Group B: REQ-004, REQ-005)
    b2 = next(b for b in result.blocks if "TEST-REQ-004" in b.bundled_request_ids)
    assert set(b2.bundled_request_ids) == {"TEST-REQ-004", "TEST-REQ-005"}
    assert set(b2.departments_involved) == {"ENG", "TRD"}
    assert b2.section_id == "SEC-TKJ-GZB"
    assert b2.start_km == 10.0
    assert b2.end_km == 11.5
    assert b2.total_duration_minutes == 150
    assert b2.power_block_granted is True
    assert b2.traffic_block_granted is True
    assert b2.savings_minutes == 100  # (150 + 100) - 150

    # Verify Single Block 1 (Group C: REQ-006)
    b3 = next(b for b in result.blocks if "TEST-REQ-006" in b.bundled_request_ids)
    assert b3.bundled_request_ids == ["TEST-REQ-006"]
    assert b3.departments_involved == ["S&T"]
    assert b3.corridor_slot == "SLOT_AFTERNOON"
    assert b3.total_duration_minutes == 60
    assert b3.savings_minutes == 0

    # Verify Single Block 2 (Group D: REQ-007)
    b4 = next(b for b in result.blocks if "TEST-REQ-007" in b.bundled_request_ids)
    assert b4.bundled_request_ids == ["TEST-REQ-007"]
    assert b4.departments_involved == ["ENG"]
    assert b4.start_km == 24.0
    assert b4.end_km == 24.8
    assert b4.total_duration_minutes == 75
    assert b4.savings_minutes == 0


def test_optimizer_empty_input():
    """Verify optimizer safely handles empty requests list."""
    result = optimize_requests([])
    assert result.status == "OPTIMAL"
    assert result.total_requests_in == 0
    assert result.total_blocks_out == 0
    assert result.total_savings_minutes == 0
    assert len(result.blocks) == 0


def test_optimizer_single_request():
    """Verify optimizer correctly formats a single request."""
    req = [{
        "request_id": "REQ-SOLO-01",
        "department": "ENG",
        "section_id": "SEC-GZB-ALJN",
        "corridor_slot": "SLOT_MIDDAY",
        "chainage_start": 30.0,
        "chainage_end": 32.0,
        "requested_window_start": "2026-09-16T11:30:00",
        "requested_window_end": "2026-09-16T15:00:00",
        "required_duration_minutes": 90,
        "work_type": "Ballast Regulating",
        "asset_id": "ENG-TRK-001",
        "asset_type": "Ballast",
        "risk_score": 45.0,
        "requires_power_block": False,
        "requires_traffic_block": True,
    }]
    result = optimize_requests(req)
    assert result.total_requests_in == 1
    assert result.total_blocks_out == 1
    assert result.bundled_blocks_count == 0
    assert result.single_blocks_count == 1
    assert result.total_savings_minutes == 0
    b = result.blocks[0]
    assert b.bundled_request_ids == ["REQ-SOLO-01"]
    assert b.total_duration_minutes == 90


def test_temporally_disjoint_requests_not_bundled():
    """
    Verify that requests with non-overlapping requested windows on the same section
    are NOT bundled into a bloated continuous block with dead track possession time.
    """
    reqs = [
        {
            "request_id": "REQ-DISJOINT-1",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.0,
            "chainage_end": 2.0,
            "requested_window_start": "2026-09-15T00:00:00",
            "requested_window_end": "2026-09-15T01:00:00",
            "required_duration_minutes": 60,
            "work_type": "Track Maintenance",
            "asset_id": "ASSET-1",
            "risk_score": 50.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "REQ-DISJOINT-2",
            "department": "TRD",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.0,
            "chainage_end": 2.0,
            "requested_window_start": "2026-09-15T04:00:00",
            "requested_window_end": "2026-09-15T05:00:00",
            "required_duration_minutes": 60,
            "work_type": "OHE Inspection",
            "asset_id": "ASSET-2",
            "risk_score": 50.0,
            "requires_power_block": True,
            "requires_traffic_block": True,
        },
    ]
    result = optimize_requests(reqs)
    assert result.total_requests_in == 2
    # Must produce 2 separate blocks, not 1 bloated 300-minute block
    assert result.total_blocks_out == 2
    assert result.bundled_blocks_count == 0
    assert result.single_blocks_count == 2
    assert result.total_bundled_duration_minutes == 120  # 60 + 60, not 300!
    assert result.blocks[0].total_duration_minutes == 60
    assert result.blocks[1].total_duration_minutes == 60


def test_chained_spatial_requests_no_double_booking():
    """
    Verify that 4 requests forming a spatial chain on a section (where endpoints
    have gap > proximity but are bridged by overlapping work) are co-optimized
    without track double-booking or solver infeasibility.
    """
    reqs = [
        {
            "request_id": "CHAIN-01",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_MIDDAY",
            "chainage_start": 0.41,
            "chainage_end": 3.50,
            "requested_window_start": "2026-09-15T11:30:00",
            "requested_window_end": "2026-09-15T14:45:00",
            "required_duration_minutes": 165,
            "work_type": "Track Tamping",
            "asset_id": "ASSET-C1",
            "risk_score": 55.0,
        },
        {
            "request_id": "CHAIN-02",
            "department": "S&T",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_MIDDAY",
            "chainage_start": 0.00,
            "chainage_end": 0.18,
            "requested_window_start": "2026-09-15T11:45:00",
            "requested_window_end": "2026-09-15T15:00:00",
            "required_duration_minutes": 72,
            "work_type": "Gate Inspection",
            "asset_id": "ASSET-C2",
            "risk_score": 25.0,
        },
        {
            "request_id": "CHAIN-03",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_MIDDAY",
            "chainage_start": 0.54,
            "chainage_end": 3.34,
            "requested_window_start": "2026-09-15T11:45:00",
            "requested_window_end": "2026-09-15T14:30:00",
            "required_duration_minutes": 150,
            "work_type": "Track Dressing",
            "asset_id": "ASSET-C3",
            "risk_score": 45.0,
        },
        {
            "request_id": "CHAIN-04",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_MIDDAY",
            "chainage_start": 2.45,
            "chainage_end": 2.77,
            "requested_window_start": "2026-09-15T12:00:00",
            "requested_window_end": "2026-09-15T14:30:00",
            "required_duration_minutes": 133,
            "work_type": "Turnout Renewal",
            "asset_id": "ASSET-C4",
            "risk_score": 60.0,
        },
    ]
    result = optimize_requests(reqs)
    assert result.status == "OPTIMAL"
    assert result.total_requests_in == 4
    # All 4 bundle into 1 consolidated block
    assert result.total_blocks_out == 1
    assert result.bundled_blocks_count == 1
    b = result.blocks[0]
    assert set(b.bundled_request_ids) == {"CHAIN-01", "CHAIN-02", "CHAIN-03", "CHAIN-04"}
    assert b.start_km == 0.0
    assert b.end_km == 3.5
    assert b.savings_minutes == (165 + 72 + 150 + 133) - b.total_duration_minutes
    assert b.savings_minutes > 0


def test_over_constrained_slot_defers_lower_risk():
    """
    Verify that when two conflicting requests on the same track exceed window capacity,
    the higher-risk request is scheduled and the lower-risk request is deferred.
    """
    reqs = [
        {
            "request_id": "REQ-HIGH-RISK",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.0,
            "chainage_end": 2.0,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T02:30:00",
            "required_duration_minutes": 90,
            "work_type": "Critical Rail Fix",
            "asset_id": "ASSET-HIGH",
            "risk_score": 90.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
        {
            "request_id": "REQ-LOW-RISK",
            "department": "ENG",
            "section_id": "SEC-NDLS-TKJ",
            "corridor_slot": "SLOT_NIGHT",
            "chainage_start": 1.0,
            "chainage_end": 2.0,
            "requested_window_start": "2026-09-15T00:30:00",
            "requested_window_end": "2026-09-15T02:30:00",
            "required_duration_minutes": 90,
            "work_type": "Routine Inspection",
            "asset_id": "ASSET-LOW",
            "risk_score": 10.0,
            "requires_power_block": False,
            "requires_traffic_block": True,
        },
    ]
    # Set span limit so they cannot be bundled together, forcing sequential scheduling
    cfg = OptimizerConfig(max_block_km_span=0.5)
    result = optimize_requests(reqs, cfg)
    # 90 + 90 = 180 min > 120 min window. One must be deferred.
    assert result.status == "FEASIBLE"
    # The scheduled block must be for the high risk request
    scheduled_blocks = [b for b in result.blocks if b.approval_status == "PROPOSED"]
    assert len(scheduled_blocks) == 1
    assert scheduled_blocks[0].bundled_request_ids == ["REQ-HIGH-RISK"]
    deferred_blocks = [b for b in result.blocks if b.approval_status == "DEFERRED"]
    assert len(deferred_blocks) == 1
    assert deferred_blocks[0].bundled_request_ids == ["REQ-LOW-RISK"]

