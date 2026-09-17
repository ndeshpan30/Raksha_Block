"""
RAKSHA-BLOCK: Phase 2 Ingestion Execution & Verification Script
Reads synthetic datasets, runs validation, persists records to SQLite DB,
and prints verification outputs.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database import init_db, SessionLocal, DEFAULT_DB_FILE
from app.models import SectionModel, MaintenanceRequestModel
from app.ingestion import ingest_from_files


def main():
    print("=" * 80)
    print("  RAKSHA-BLOCK: Phase 2 Ingestion & Normalization Pipeline")
    print("  AI-Powered Indian Railways Maintenance Block Coordination (SIH26027)")
    print("=" * 80)

    # Initialize / verify database tables
    print(f"\n[*] Target Database: {DEFAULT_DB_FILE}")
    init_db()

    # Ingest synthetic datasets
    print("[*] Running ingestion from canonical synthetic data files...")
    result = ingest_from_files()

    print("\n" + "-" * 80)
    print("  INGESTION SUMMARY & INTEGRITY METRICS")
    print("-" * 80)
    print(f"  [+] Track Sections Ingested:          {result.sections_ingested}")
    print(f"  [+] Requests Ingested into Database:  {result.requests_ingested} / {result.total_evaluated}")
    print(f"  [+] Requests Rejected by Validation:  {result.requests_rejected}")
    print(f"  [+] Validation Error Count:           {len(result.validation_errors)}")

    # Verify directly from Database
    with SessionLocal() as db:
        sec_count = db.query(SectionModel).count()
        req_count = db.query(MaintenanceRequestModel).count()
        print(f"\n  [+] Verification: Database sections count = {sec_count}")
        print(f"  [+] Verification: Database requests count = {req_count}")

        # Check department distribution in DB
        from sqlalchemy import func
        dept_dist = (
            db.query(MaintenanceRequestModel.department, func.count(MaintenanceRequestModel.request_id))
            .group_by(MaintenanceRequestModel.department)
            .all()
        )
        print("\n  Ingested Department Distribution:")
        for dept, count in dept_dist:
            print(f"    - {dept:6s}: {count:3d} ({count / req_count * 100:.1f}%)")

        # Check source system distribution in DB
        source_dist = (
            db.query(MaintenanceRequestModel.source_system, func.count(MaintenanceRequestModel.request_id))
            .group_by(MaintenanceRequestModel.source_system)
            .all()
        )
        print("\n  Ingested Source System Distribution:")
        for src, count in source_dist:
            print(f"    - {src:6s}: {count:3d} ({count / req_count * 100:.1f}%)")

    print("\n" + "=" * 80)
    print("  Phase 2 Ingestion Pipeline successfully completed and verified.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
