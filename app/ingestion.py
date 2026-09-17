import os
import json
import csv
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db, DATA_DIR
from app.models import SectionModel, MaintenanceRequestModel
from app.schemas import IngestionResult, IngestionErrorDetail
from app.validation import validate_section, validate_maintenance_request

logger = logging.getLogger("raksha.ingestion")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")


def _read_data_file(file_path: Path) -> List[Dict[str, Any]]:
    """Read data records from either JSON or CSV format."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".json":
        with open(file_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            raise ValueError(f"Expected JSON array in {file_path}, got {type(data)}")
    elif suffix == ".csv":
        with open(file_path, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return [row for row in reader if any(val and str(val).strip() for val in row.values())]
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Supported: .json, .csv")


def ingest_sections(
    db: Session,
    sections_raw: List[Dict[str, Any]],
) -> Tuple[int, Set[str], List[Dict[str, Any]]]:
    """
    Validate and ingest section topology into the database.
    Returns (ingested_count, valid_section_ids, errors).
    """
    valid_ids: Set[str] = set()
    errors: List[Dict[str, Any]] = []
    ingested_count = 0

    for idx, raw in enumerate(sections_raw):
        is_valid, errs, normalized = validate_section(raw)
        if not is_valid:
            sec_id = raw.get("section_id", f"INDEX-{idx}")
            errors.append({"record_id": sec_id, "errors": errs})
            logger.warning(f"Section validation failed for {sec_id}: {errs}")
            continue

        section = SectionModel(**normalized)
        db.merge(section)
        valid_ids.add(normalized["section_id"])
        ingested_count += 1

    db.commit()
    return ingested_count, valid_ids, errors


def ingest_requests(
    db: Session,
    requests_raw: List[Dict[str, Any]],
    known_section_ids: Optional[Set[str]] = None,
    known_sections: Optional[Dict[str, Any]] = None,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Validate and ingest maintenance requests into the database.
    Catches missing fields and invalid records, rejecting them and saving valid ones.
    Returns (ingested_count, rejected_count, errors).
    """
    ingested_count = 0
    rejected_count = 0
    errors: List[Dict[str, Any]] = []

    # If known_sections / known_section_ids is not supplied, populate from database
    if known_sections is None and known_section_ids is None:
        db_sections = db.query(SectionModel).all()
        known_sections = {
            s.section_id: {"start_km": s.start_km, "end_km": s.end_km}
            for s in db_sections
        }

    for idx, raw in enumerate(requests_raw):
        is_valid, errs, normalized = validate_maintenance_request(
            raw,
            known_section_ids=known_section_ids,
            known_sections=known_sections,
        )
        req_id = raw.get("request_id", f"ROW-{idx}")

        if not is_valid:
            rejected_count += 1
            errors.append({"record_id": req_id, "errors": errs})
            logger.warning(f"Rejected request {req_id}: {errs}")
            continue

        # Auto-compute predictive risk_score using LightGBM model if missing
        if normalized.get("risk_score") is None:
            try:
                from app.risk_model import predict_risk_score
                normalized["risk_score"] = predict_risk_score(normalized)
            except Exception as e:
                logger.warning(f"Could not compute risk_score for {req_id}: {e}")
                normalized["risk_score"] = 0.0

        req_model = MaintenanceRequestModel(**normalized)
        db.merge(req_model)
        ingested_count += 1

    db.commit()
    return ingested_count, rejected_count, errors


def ingest_from_files(
    db: Optional[Session] = None,
    requests_path: Optional[str] = None,
    sections_path: Optional[str] = None,
) -> IngestionResult:
    """
    Main entrypoint for Phase 2 data ingestion pipeline.
    Reads synthetic datasets (JSON or CSV), validates, and loads into database.
    """
    if not requests_path:
        if (DATA_DIR / "maintenance_requests.json").exists():
            req_file = DATA_DIR / "maintenance_requests.json"
        elif (DATA_DIR / "maintenance_requests.csv").exists():
            req_file = DATA_DIR / "maintenance_requests.csv"
        else:
            req_file = DATA_DIR / "maintenance_requests.json"
    else:
        req_file = Path(requests_path)

    if not sections_path:
        if (DATA_DIR / "sections.json").exists():
            sec_file = DATA_DIR / "sections.json"
        elif (DATA_DIR / "sections.csv").exists():
            sec_file = DATA_DIR / "sections.csv"
        else:
            sec_file = DATA_DIR / "sections.json"
    else:
        sec_file = Path(sections_path)

    should_close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        should_close_db = True

    try:
        # 1. Ingest Track Topology Sections
        logger.info(f"Ingesting sections from: {sec_file}")
        sections_raw = _read_data_file(sec_file)
        sec_ingested, valid_sec_ids, sec_errors = ingest_sections(db, sections_raw)

        # 2. Build full map of known sections with boundary ranges from DB
        db_sections = db.query(SectionModel).all()
        known_sections_map = {
            s.section_id: {"start_km": s.start_km, "end_km": s.end_km}
            for s in db_sections
        }

        # 3. Ingest Maintenance Requests
        logger.info(f"Ingesting requests from: {req_file}")
        requests_raw = _read_data_file(req_file)
        req_ingested, req_rejected, req_errors = ingest_requests(
            db, requests_raw, known_sections=known_sections_map
        )

        all_errors = [
            IngestionErrorDetail(record_id=e["record_id"], errors=e["errors"])
            for e in (sec_errors + req_errors)
        ]

        result = IngestionResult(
            sections_ingested=sec_ingested,
            requests_ingested=req_ingested,
            requests_rejected=req_rejected,
            total_evaluated=len(requests_raw),
            validation_errors=all_errors,
        )

        logger.info(
            f"Ingestion complete: {sec_ingested} sections, "
            f"{req_ingested} requests ingested, {req_rejected} rejected."
        )
        return result

    finally:
        if should_close_db:
            db.close()


if __name__ == "__main__":
    result = ingest_from_files()
    print("\n" + "=" * 80)
    print("  RAKSHA-BLOCK: Phase 2 Ingestion Execution Summary")
    print("=" * 80)
    print(f"  Sections Ingested:    {result.sections_ingested}")
    print(f"  Requests Ingested:    {result.requests_ingested} / {result.total_evaluated}")
    print(f"  Requests Rejected:    {result.requests_rejected}")
    if result.validation_errors:
        print(f"  Validation Errors:    {len(result.validation_errors)}")
        for err in result.validation_errors[:5]:
            print(f"    - [{err.record_id}]: {', '.join(err.errors)}")
    else:
        print("  Validation Errors:    0 (All rows valid)")
    print("=" * 80 + "\n")
