"""
RAKSHA-BLOCK: Tabular Risk & Priority Inference Module (Phase 3)
===============================================================
Wraps the LightGBM regression model trained on asset condition features.
Callable from FastAPI endpoints, ingestion pipelines, and block scheduling optimizers.

Features evaluated (6 Tabular Attributes):
  1. asset_age_years: float (Age of physical asset in years)
  2. last_maintenance_days_ago: int/float (Days elapsed since previous POH/IOH/inspection)
  3. past_breakdown_count: int/float (Defect/breakdown count in past 12 months)
  4. gross_million_tonnes: float (Cumulative dynamic traffic tonnage load)
  5. condition_score: float (Physical inspection index, 1.0 degraded to 10.0 pristine)
  6. urgency_level: int (0=LOW, 1=MEDIUM, 2=HIGH, 3=CRITICAL)

Output:
  risk_score: float bounded between 0.0 (pristine/routine) and 100.0 (critical failure risk)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import numpy as np

logger = logging.getLogger("raksha.risk_model")

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
JOBLIB_MODEL_FILE = MODELS_DIR / "risk_model.joblib"
TXT_MODEL_FILE = MODELS_DIR / "risk_model.txt"
METADATA_FILE = MODELS_DIR / "risk_model_meta.json"

URGENCY_MAP: Dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}

FEATURE_COLUMNS = [
    "asset_age_years",
    "last_maintenance_days_ago",
    "past_breakdown_count",
    "gross_million_tonnes",
    "condition_score",
    "urgency_level",
]

_CACHED_MODEL = None
_CACHED_METADATA = None


def load_model():
    """
    Load and cache the trained LightGBM model.
    Prioritizes the joblib bundle, then falls back to native text format.
    """
    global _CACHED_MODEL, _CACHED_METADATA

    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    # Option 1: Joblib bundle
    if JOBLIB_MODEL_FILE.exists():
        try:
            import joblib
            bundle = joblib.load(JOBLIB_MODEL_FILE)
            if isinstance(bundle, dict) and "model" in bundle:
                _CACHED_MODEL = bundle["model"]
                _CACHED_METADATA = bundle
            else:
                _CACHED_MODEL = bundle
            logger.info(f"Loaded LightGBM risk model bundle from {JOBLIB_MODEL_FILE}")
            return _CACHED_MODEL
        except Exception as e:
            logger.warning(f"Failed to load joblib model from {JOBLIB_MODEL_FILE}: {e}")

    # Option 2: Native LightGBM text model
    if TXT_MODEL_FILE.exists():
        try:
            import lightgbm as lgb
            booster = lgb.Booster(model_file=str(TXT_MODEL_FILE))
            _CACHED_MODEL = booster
            logger.info(f"Loaded native LightGBM text booster from {TXT_MODEL_FILE}")
            return _CACHED_MODEL
        except Exception as e:
            logger.warning(f"Failed to load text booster from {TXT_MODEL_FILE}: {e}")

    logger.warning("No saved model artifact found on disk. Falling back to heuristic scorer.")
    return None


def _safe_float(val: Any, default: float) -> float:
    """Safely convert value to float, handling None, empty strings, and NaN."""
    if val is None or val == "":
        return default
    try:
        f = float(val)
        return default if np.isnan(f) else f
    except (ValueError, TypeError):
        return default


def extract_features_dict(item: Any) -> Dict[str, Any]:
    """
    Safely extract and sanitize the 6 asset condition features from any dictionary,
    Pydantic schema, SQLAlchemy model, or nested container.
    Guarantees physical bounds:
      - asset_age_years >= 0.0
      - last_maintenance_days_ago >= 0.0
      - past_breakdown_count >= 0.0
      - gross_million_tonnes >= 0.0
      - 1.0 <= condition_score <= 10.0
      - 0 <= urgency_level <= 3
    """
    if item is None:
        data = {}
    # Case 1: Pydantic model
    elif hasattr(item, "model_dump"):
        data = item.model_dump()
    # Case 2: SQLAlchemy model or object with __dict__
    elif hasattr(item, "__table__"):
        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    # Case 3: Object with to_dict
    elif hasattr(item, "to_dict") and callable(item.to_dict):
        data = item.to_dict()
    # Case 4: Plain dict
    elif isinstance(item, dict):
        data = item
    else:
        try:
            data = vars(item)
        except TypeError:
            data = {}

    # Check for nested condition container if present
    cond_nested = data.get("asset_age_or_condition_features") or data.get("asset_condition_features")
    if isinstance(cond_nested, dict):
        # Nested container provides defaults; top-level non-null attributes override
        merged = dict(cond_nested)
        merged.update({k: v for k, v in data.items() if v is not None and k not in ("asset_age_or_condition_features", "asset_condition_features")})
        data = merged

    # Extract individual attributes with explicit None checks to preserve 0 / 0.0
    age = max(0.0, _safe_float(data.get("asset_age_years"), 5.0))
    last_maint = max(0.0, _safe_float(data.get("last_maintenance_days_ago"), 90.0))
    breakdowns = max(0.0, _safe_float(data.get("past_breakdown_count"), 0.0))
    gmt = max(0.0, _safe_float(data.get("gross_million_tonnes"), 40.0))
    condition = float(np.clip(_safe_float(data.get("condition_score"), 5.0), 1.0, 10.0))

    raw_urgency = data.get("urgency_category")
    if raw_urgency is not None:
        if isinstance(raw_urgency, str):
            urgency_code = URGENCY_MAP.get(raw_urgency.strip().upper(), 1)
        elif isinstance(raw_urgency, (int, float)):
            urgency_code = int(raw_urgency)
        else:
            urgency_code = 1
    elif "urgency_level" in data:
        try:
            urgency_code = int(data["urgency_level"])
        except (ValueError, TypeError):
            urgency_code = 1
    else:
        urgency_code = 1

    urgency_code = max(0, min(3, urgency_code))
    reverse_map = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}
    return {
        "asset_age_years": age,
        "last_maintenance_days_ago": last_maint,
        "past_breakdown_count": breakdowns,
        "gross_million_tonnes": gmt,
        "condition_score": condition,
        "urgency_level": urgency_code,
        "urgency_category": reverse_map.get(urgency_code, "MEDIUM"),
    }


def _heuristic_fallback_score(features: Dict[str, Any]) -> float:
    """
    Deterministic domain-grounded fallback score if ML weights are unavailable.
    Guarantees that the service never fails even in degraded environments.
    """
    c_def = np.clip((10.0 - features["condition_score"]) / 9.0, 0.0, 1.0)
    b_past = np.clip(features["past_breakdown_count"] / 5.0, 0.0, 1.0)
    g_wear = np.clip(features["gross_million_tonnes"] / 120.0, 0.0, 1.0)
    m_lag = np.clip(features["last_maintenance_days_ago"] / 300.0, 0.0, 1.0)
    a_age = np.clip(features["asset_age_years"] / 25.0, 0.0, 1.0)

    urgency_val = features["urgency_level"]
    urgency_deltas = {3: 0.05, 2: 0.02, 1: 0.0, 0: -0.03}
    u_mod = urgency_deltas.get(urgency_val, 0.0)

    score = (
        0.30 * c_def +
        0.25 * b_past +
        0.15 * g_wear +
        0.15 * m_lag +
        0.10 * a_age +
        u_mod
    )
    return round(float(np.clip(score, 0.01, 0.99) * 100.0), 2)


def predict_risk_score(item: Any = None, **kwargs) -> float:
    """
    Predict the operational failure risk / scheduling priority score (0.0 - 100.0)
    for a given maintenance request or asset condition feature dictionary.

    Callable from:
      - FastAPI endpoints
      - Ingestion pipelines
      - CP-SAT optimization model builders

    Returns:
      float: Risk score bounded in [0.0, 100.0], rounded to 2 decimal places.
    """
    if item is not None and not kwargs:
        feat_dict = extract_features_dict(item)
    elif item is None:
        feat_dict = extract_features_dict(kwargs)
    else:
        merged = extract_features_dict(item)
        merged.update(kwargs)
        feat_dict = extract_features_dict(merged)

    model = load_model()

    if model is None:
        return _heuristic_fallback_score(feat_dict)

    # Prepare DataFrame with feature names for inference
    import pandas as pd
    row = [feat_dict[col] for col in FEATURE_COLUMNS]
    X = pd.DataFrame([row], columns=FEATURE_COLUMNS)

    try:
        pred = model.predict(X)[0]
        bounded_pred = float(np.clip(pred, 0.0, 100.0))
        return round(bounded_pred, 2)
    except Exception as err:
        logger.error(f"Inference error with model: {err}. Using heuristic fallback.")
        return _heuristic_fallback_score(feat_dict)


def predict_risk_scores(items: List[Any]) -> List[float]:
    """
    Batch predict risk scores across an iterable of maintenance requests or dictionaries.
    """
    if not items:
        return []

    model = load_model()
    if model is None:
        return [predict_risk_score(item) for item in items]

    import pandas as pd
    feature_rows = []
    for it in items:
        f = extract_features_dict(it)
        feature_rows.append([f[col] for col in FEATURE_COLUMNS])

    X = pd.DataFrame(feature_rows, columns=FEATURE_COLUMNS)
    try:
        preds = model.predict(X)
        bounded = np.clip(preds, 0.0, 100.0)
        return [round(float(p), 2) for p in bounded]
    except Exception as err:
        logger.error(f"Batch inference failed: {err}. Falling back to element-wise prediction.")
        return [predict_risk_score(item) for item in items]


def get_risk_tier(score: float) -> str:
    """
    Map continuous risk score (0.0 to 100.0) to operational risk tiers:
      - CRITICAL : >= 75.0
      - HIGH     : >= 50.0 and < 75.0
      - MEDIUM   : >= 25.0 and < 50.0
      - LOW      : < 25.0
    """
    if score >= 75.0:
        return "CRITICAL"
    elif score >= 50.0:
        return "HIGH"
    elif score >= 25.0:
        return "MEDIUM"
    else:
        return "LOW"


def get_model_metadata() -> Dict[str, Any]:
    """Return model training metadata, hyperparameters, and feature configuration."""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "algorithm": "LightGBM Regressor",
        "target": "Operational Failure Risk & Priority Score (0-100)",
        "feature_columns": FEATURE_COLUMNS,
        "urgency_encoding": URGENCY_MAP,
        "status": "ready" if (JOBLIB_MODEL_FILE.exists() or TXT_MODEL_FILE.exists()) else "uninitialized",
    }
