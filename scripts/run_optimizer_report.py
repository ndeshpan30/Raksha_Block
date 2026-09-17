"""
RAKSHA-BLOCK: Phase 4 Optimizer Execution Script & Dataset Verification Report
SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.optimizer import optimize_requests, OptimizerConfig

def run_report():
    with open("data/maintenance_requests.json", "r") as f:
        reqs = json.load(f)

    cfg = OptimizerConfig(spatial_proximity_km=2.0)
    result = optimize_requests(reqs, cfg)

    print("=" * 80)
    print("  RAKSHA-BLOCK: Phase 4 CP-SAT Full Synthetic Dataset Report (N=240)")
    print("=" * 80)
    print(f"Solver Status:                   {result.status}")
    print(f"Total Requests In:               {result.total_requests_in}")
    print(f"Total Blocks Out:                {result.total_blocks_out}")
    print(f"Bundled Blocks Count:            {result.bundled_blocks_count}")
    print(f"Single Blocks Count:             {result.single_blocks_count}")
    print(f"Original Line Possession:        {result.total_original_duration_minutes:,} mins ({result.total_original_duration_minutes/60:.1f} hrs)")
    print(f"Optimized Possession:            {result.total_bundled_duration_minutes:,} mins ({result.total_bundled_duration_minutes/60:.1f} hrs)")
    print(f"Total Possession Hours Saved:    {result.total_savings_minutes:,} mins ({result.total_savings_minutes/60:.1f} hrs)")
    print(f"Possession Reduction Percentage: {result.savings_percentage}%")
    print(f"Total Solve Time:                {result.solve_time_seconds:.3f} s")
    print("-" * 80)

    # 3 Example Bundled Blocks
    multi_blocks = [b for b in result.blocks if len(b.bundled_request_ids) > 1]
    triple_blocks = [b for b in multi_blocks if len(b.departments_involved) == 3]
    double_blocks = [b for b in multi_blocks if len(b.departments_involved) == 2]

    sample_blocks = triple_blocks[:1] + double_blocks[:2]

    for idx, b in enumerate(sample_blocks, 1):
        depts_str = " + ".join(b.departments_involved)
        print(f"\n--- Example Bundled Block #{idx}: {b.block_id} ---")
        print(f"  Section:              {b.section_id}")
        print(f"  Corridor Slot:        {b.corridor_slot}")
        print(f"  Enveloping Chainage:  KM {b.start_km:.2f} to KM {b.end_km:.2f} (span: {b.end_km - b.start_km:.2f} km)")
        print(f"  Scheduled Window:     {b.scheduled_start} to {b.scheduled_end} ({b.total_duration_minutes} min)")
        print(f"  Departments Involved: {depts_str}")
        print(f"  Block Types Granted:  PowerBlock={b.power_block_granted}, TrafficBlock={b.traffic_block_granted}")
        print(f"  Possession Savings:   {b.savings_minutes} minutes saved")
        print(f"  Constituent Requests ({len(b.constituent_requests)}):")
        for cr in b.constituent_requests:
            s_time = cr['scheduled_start'][11:16]
            e_time = cr['scheduled_end'][11:16]
            print(f"    * [{cr['request_id']}] Dept: {cr['department']:3s} | Type: {cr['work_type']} | Asset: {cr['asset_id']} | KM {cr['chainage_start']}-{cr['chainage_end']} | Net Work: {cr['required_duration_minutes']}m | Sched: {s_time}-{e_time} | Risk: {cr['risk_score']}")
        print(f"  Plain-Language Why:   {b.explanation_text}")
        print(f"  Structured Explanation Detail:")
        print(json.dumps(b.explanation_detail, indent=4))

    print("=" * 80)

if __name__ == "__main__":
    run_report()
