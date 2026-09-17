"""
RAKSHA-BLOCK: Phase 3 ML Risk/Priority Scoring Model Training Script
===================================================================
Trains a LightGBM regressor on synthetic asset condition features to predict
an operational failure risk and maintenance priority score (0.0 to 100.0).

Synthetic Ground-Truth Failure Risk Formulation:
------------------------------------------------
Because historical field failure logs are synthetic in this hackathon setting,
the target failure risk label is derived using a transparent, domain-grounded
heuristic reflecting Indian Railways permanent way & OHE degradation physics:
  - Condition Deficit (30% weight): (10 - condition_score) / 9.0
  - Past Breakdown Recurrence (25% weight): min(past_breakdowns / 5.0, 1.0)
  - Cumulative Traffic Fatigue (15% weight): min(gross_million_tonnes / 120.0, 1.0)
  - Maintenance Interval Lag (15% weight): min(last_maintenance_days_ago / 300.0, 1.0)
  - Asset Age Aging Factor (10% weight): min(asset_age_years / 25.0, 1.0)
  - Operational Urgency Modifier: CRITICAL (+0.05), HIGH (+0.02), MEDIUM (0.00), LOW (-0.03)
  - Environmental Disturbance: Gaussian noise N(0, 0.02^2) clamped to [0.01, 0.99]
  - Target Scale: 0.0 to 100.0

Artifacts Saved:
  - models/risk_model.joblib (LightGBM model object + metadata dictionary)
  - models/risk_model.txt (native LightGBM text model representation)
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("raksha.train_risk_model")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE = DATA_DIR / "maintenance_requests.csv"
JOBLIB_MODEL_FILE = MODELS_DIR / "risk_model.joblib"
TXT_MODEL_FILE = MODELS_DIR / "risk_model.txt"
METADATA_FILE = MODELS_DIR / "risk_model_meta.json"

URGENCY_ENCODING: Dict[str, int] = {
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


def compute_synthetic_ground_truth_risk(
    row: pd.Series,
    rng: np.random.RandomState,
) -> float:
    """
    Transparent domain-grounded failure risk formulation for Indian Railways assets.
    Outputs a score in range [0.0, 100.0].
    """
    # 1. Condition deficit: 10 is pristine, 1 is critical failure threshold
    cond_score = float(row.get("condition_score", 5.0))
    c_def = np.clip((10.0 - cond_score) / 9.0, 0.0, 1.0)

    # 2. Past breakdown recurrence in last 12 months (0 to 6+)
    breakdowns = float(row.get("past_breakdown_count", 0))
    b_past = np.clip(breakdowns / 5.0, 0.0, 1.0)

    # 3. Cumulative Gross Million Tonnes (GMT) wear (up to 120 GMT)
    gmt = float(row.get("gross_million_tonnes", 40.0))
    g_wear = np.clip(gmt / 120.0, 0.0, 1.0)

    # 4. Overhaul / maintenance lag in days (up to 300 days)
    maint_days = float(row.get("last_maintenance_days_ago", 90))
    m_lag = np.clip(maint_days / 300.0, 0.0, 1.0)

    # 5. Asset age in years (up to 25 years design life)
    age = float(row.get("asset_age_years", 5.0))
    a_age = np.clip(age / 25.0, 0.0, 1.0)

    # 6. Operational urgency tier adjustment
    urgency_str = str(row.get("urgency_category", "MEDIUM")).upper()
    urgency_deltas = {
        "CRITICAL": 0.05,
        "HIGH": 0.02,
        "MEDIUM": 0.00,
        "LOW": -0.03,
    }
    u_mod = urgency_deltas.get(urgency_str, 0.0)

    # Composite weighted risk index
    base_risk = (
        0.30 * c_def +
        0.25 * b_past +
        0.15 * g_wear +
        0.15 * m_lag +
        0.10 * a_age +
        u_mod
    )

    # Small stochastic field variance (unobserved environmental/track vibrations)
    noise = rng.normal(0.0, 0.02)
    clamped_risk = np.clip(base_risk + noise, 0.01, 0.99)
    return round(float(clamped_risk * 100.0), 2)


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Extract and encode the 6 tabular asset condition features."""
    X = pd.DataFrame(index=df.index)
    X["asset_age_years"] = df["asset_age_years"].astype(float)
    X["last_maintenance_days_ago"] = df["last_maintenance_days_ago"].astype(float)
    X["past_breakdown_count"] = df["past_breakdown_count"].astype(float)
    X["gross_million_tonnes"] = df["gross_million_tonnes"].astype(float)
    X["condition_score"] = df["condition_score"].astype(float)
    X["urgency_level"] = df["urgency_category"].str.upper().map(URGENCY_ENCODING).fillna(1).astype(int)

    y = df["target_risk_score"].astype(float)
    return X, y


def train_and_evaluate(
    X: pd.DataFrame,
    y: pd.Series,
    random_seed: int = 42,
) -> Tuple[lgb.LGBMRegressor, Dict[str, Any]]:
    """
    Perform 5-fold cross-validation and fit the final production model.
    """
    logger.info("Executing 5-fold cross validation for LightGBM regressor...")
    kf = KFold(n_splits=5, shuffle=True, random_state=random_seed)

    cv_maes = []
    cv_rmses = []
    cv_r2s = []

    for fold, (train_idx, val_idx) in enumerate(kf.split(X), 1):
        X_tr, X_va = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_va = y.iloc[train_idx], y.iloc[val_idx]

        fold_model = lgb.LGBMRegressor(
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=5,
            random_state=random_seed,
            verbosity=-1,
        )
        fold_model.fit(X_tr, y_tr)
        val_preds = fold_model.predict(X_va)

        mae = mean_absolute_error(y_va, val_preds)
        rmse = np.sqrt(mean_squared_error(y_va, val_preds))
        r2 = r2_score(y_va, val_preds)

        cv_maes.append(mae)
        cv_rmses.append(rmse)
        cv_r2s.append(r2)
        logger.info(f"  Fold {fold}: MAE={mae:.3f}, RMSE={rmse:.3f}, R^2={r2:.4f}")

    mean_mae = float(np.mean(cv_maes))
    mean_rmse = float(np.mean(cv_rmses))
    mean_r2 = float(np.mean(cv_r2s))
    logger.info(f"5-Fold CV Aggregate: MAE={mean_mae:.3f}, RMSE={mean_rmse:.3f}, R^2={mean_r2:.4f}")

    # Train production model on entire dataset
    logger.info("Training final production LightGBM model on full dataset (240 records)...")
    final_model = lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=5,
        random_state=random_seed,
        verbosity=-1,
    )
    final_model.fit(X, y)

    full_preds = np.clip(final_model.predict(X), 0.0, 100.0)
    full_mae = float(mean_absolute_error(y, full_preds))
    full_rmse = float(np.sqrt(mean_squared_error(y, full_preds)))
    full_r2 = float(r2_score(y, full_preds))

    feature_importances = dict(zip(FEATURE_COLUMNS, [int(imp) for imp in final_model.feature_importances_]))

    metrics = {
        "cv_5fold": {
            "mean_mae": mean_mae,
            "mean_rmse": mean_rmse,
            "mean_r2": mean_r2,
            "maes": [round(m, 3) for m in cv_maes],
            "r2s": [round(r, 4) for r in cv_r2s],
        },
        "full_dataset": {
            "mae": full_mae,
            "rmse": full_rmse,
            "r2": full_r2,
        },
        "feature_importances": feature_importances,
    }

    return final_model, metrics


def compute_distribution_summary(preds: np.ndarray) -> Dict[str, Any]:
    """Compute rich distribution metrics and ASCII histogram."""
    preds_clean = np.round(np.clip(preds, 0.0, 100.0), 2)
    counts, bin_edges = np.histogram(preds_clean, bins=10, range=(0.0, 100.0))

    ascii_bars = []
    for i in range(len(counts)):
        bar = "#" * int(counts[i] // 2)
        ascii_bars.append(f"[{bin_edges[i]:5.1f} - {bin_edges[i+1]:5.1f}]: {counts[i]:3d} | {bar}")

    summary = {
        "count": int(len(preds_clean)),
        "min": float(np.min(preds_clean)),
        "max": float(np.max(preds_clean)),
        "mean": float(np.mean(preds_clean)),
        "std": float(np.std(preds_clean)),
        "p10": float(np.percentile(preds_clean, 10)),
        "p25": float(np.percentile(preds_clean, 25)),
        "p50_median": float(np.median(preds_clean)),
        "p75": float(np.percentile(preds_clean, 75)),
        "p90": float(np.percentile(preds_clean, 90)),
        "bin_counts": [int(c) for c in counts],
        "bin_edges": [float(b) for b in bin_edges],
        "ascii_histogram": ascii_bars,
    }
    return summary


def main():
    logger.info("=" * 80)
    logger.info("  RAKSHA-BLOCK: Phase 3 ML Risk/Priority Model Training")
    logger.info("=" * 80)

    if not CSV_FILE.exists():
        logger.error(f"Input CSV not found at {CSV_FILE}")
        sys.exit(1)

    df = pd.read_csv(CSV_FILE)
    logger.info(f"Loaded {len(df)} requests from {CSV_FILE}")

    # Generate synthetic target label
    rng = np.random.RandomState(42)
    df["target_risk_score"] = [compute_synthetic_ground_truth_risk(row, rng) for _, row in df.iterrows()]

    X, y = prepare_features(df)
    model, metrics = train_and_evaluate(X, y)

    # Predictions across dataset
    preds = model.predict(X)
    dist_summary = compute_distribution_summary(preds)

    # Save artifacts
    logger.info(f"Saving model artifacts to {MODELS_DIR}...")

    # 1. Joblib bundle (booster + feature mapping + metadata)
    bundle = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "urgency_encoding": URGENCY_ENCODING,
        "metrics": metrics,
        "distribution": dist_summary,
        "target_scale": "0-100",
        "version": "1.0.0",
    }
    joblib.dump(bundle, JOBLIB_MODEL_FILE)
    logger.info(f"  [+] Saved joblib bundle to {JOBLIB_MODEL_FILE}")

    # 2. Native LightGBM text format
    model.booster_.save_model(str(TXT_MODEL_FILE))
    logger.info(f"  [+] Saved native LightGBM text model to {TXT_MODEL_FILE}")

    # 3. JSON metadata
    meta = {
        "algorithm": "LightGBM Regressor",
        "target": "Operational Failure Risk & Priority Score (0-100)",
        "feature_columns": FEATURE_COLUMNS,
        "urgency_encoding": URGENCY_ENCODING,
        "metrics": metrics,
        "distribution_summary": {
            k: v for k, v in dist_summary.items() if k != "ascii_histogram"
        },
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"  [+] Saved metadata JSON to {METADATA_FILE}")

    # Print distribution report to stdout
    print("\n" + "=" * 80)
    print("  RAKSHA-BLOCK: ML RISK SCORE DISTRIBUTION REPORT (N=240)")
    print("=" * 80)
    print(f"  Count:          {dist_summary['count']}")
    print(f"  Minimum Score:  {dist_summary['min']:.2f}")
    print(f"  Maximum Score:  {dist_summary['max']:.2f}")
    print(f"  Mean Score:     {dist_summary['mean']:.2f}")
    print(f"  Std Deviation:  {dist_summary['std']:.2f}")
    print(f"  10th %ile:      {dist_summary['p10']:.2f}")
    print(f"  25th %ile:      {dist_summary['p25']:.2f}")
    print(f"  Median (50th):  {dist_summary['p50_median']:.2f}")
    print(f"  75th %ile:      {dist_summary['p75']:.2f}")
    print(f"  90th %ile:      {dist_summary['p90']:.2f}")
    print("\n  ASCII Distribution Histogram (0 to 100 Risk Scale):")
    for bar_line in dist_summary["ascii_histogram"]:
        print(f"    {bar_line}")

    print("\n  Feature Importance Breakdown:")
    for feat, imp in metrics["feature_importances"].items():
        print(f"    - {feat:<28}: {imp:4d} splits")

    print(f"\n  Cross-Validation Performance (5-Fold CV):")
    print(f"    - Mean Absolute Error (MAE):  {metrics['cv_5fold']['mean_mae']:.3f}")
    print(f"    - Root Mean Squared Error:    {metrics['cv_5fold']['mean_rmse']:.3f}")
    print(f"    - Coefficient of Determ (R^2): {metrics['cv_5fold']['mean_r2']:.4f}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
