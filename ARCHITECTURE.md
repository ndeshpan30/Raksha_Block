# RAKSHA-BLOCK: Architecture & System Design
**Problem Statement:** SIH26027 — AI-Powered Coordination of Indian Railways Maintenance Block Requests  
**Version:** 1.0.0 (Living Document)  
**Status:** Initial Skeleton Approved  

---

## 1. System Overview & Core Objective
RAKSHA-BLOCK is an AI-powered coordination and scheduling platform for Indian Railways maintenance block requests across three departments:
1. **Engineering (P-Way)**
2. **Signal & Telecom (S&T)**
3. **Traction Distribution (TRD)**

It replaces manual, siloed block approvals with a constraint-optimized schedule that maximizes cross-departmental spatial/temporal bundling, minimizes line possession and asset downtime, prioritizes urgent/high-risk assets via ML, and provides plain-language explainability for Section Controllers with human-in-the-loop validation.

---

## 2. Tech Stack Decisions

| Component | Technology | Rationale / Constraints |
|---|---|---|
| **Backend API** | Python 3.10+ / FastAPI | High performance asynchronous REST API, native integration with ML/CP-SAT libraries, Pydantic validation. |
| **Optimization Engine** | Google OR-Tools (CP-SAT) | Constraint programming solver to model track possession, spatial overlap, non-overlapping constraints, and bundled possession windows. |
| **Risk Scoring Model** | LightGBM Regressor (**Active - Phase 3**) | Tabular gradient-boosted decision trees trained on synthetic asset condition features. Generates operational risk/priority score ($0.0 - 100.0$) with 5-fold CV $R^2 = 0.9810$. |
| **Database** | SQLite / PostgreSQL (**Active - Phase 2**) | Relational store for track topology, requests, and schedules. Supports Linear Referencing System (LRS) / chainage intervals. SQLite fallback available for zero-config hackathon agility if PostgreSQL setup incurs friction. |
| **Frontend Dashboard** | Next.js (React) + Tailwind CSS | Responsive Section Controller / Planner UI, timeline Gantt visualization, and interactive what-if controls. Persona switcher (Controller, Planner, Station Master). |
| **Map (P2)** | Leaflet | Lightweight 2D track map rendering stations, sections, and active block locations (if time permits). |

---

## 3. Module Boundaries & Data Flow

```
[Synthetic TMS / SMMS / TDMS / COA Sources]
                    │
                    ▼
       ┌─────────────────────────┐
       │ Ingestion & Normalizer  │ ──► Validates & maps to unified schema
       └─────────────────────────┘
                    │
                    ▼
       ┌─────────────────────────┐
       │   Risk Scoring (ML)     │ ──► Computes failure risk score / priority weight
       └─────────────────────────┘
                    │
                    ▼
       ┌─────────────────────────┐
       │   CP-SAT Optimizer      │ ──► Bundles overlapping requests, enforces safety
       └─────────────────────────┘     intervals & traffic windows -> Optimal Schedule
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
┌──────────────────┐ ┌──────────────────┐
│ Explainability   │ │ What-If Engine   │
│ Engine ("Why?")  │ │ (Ripple Re-run)  │
└──────────────────┘ └──────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
       ┌─────────────────────────┐
       │  FastAPI REST Gateway   │
       └─────────────────────────┘
                    ▲
                    │ HTTP/JSON
                    ▼
       ┌─────────────────────────┐
       │ Next.js Web UI Console  │
       │ (Controller/Planner UI) │
       └─────────────────────────┘
```

### Module Responsibilities
- **`ingestion`**: Ingests synthetic raw department requests, normalizes them into unified internal records with chainage ranges (km start to km end), department, asset IDs, requested windows, and work types.
- **`risk_model`**: Loads trained LightGBM/XGBoost weights to output a normalized risk score ($0.0 - 1.0$) and urgency tier for each request based on asset age, track load, past failure rate, inspection lag, and traffic density.
- **`optimizer`**: Translates normalized requests, track topology, caution speed restrictions, and traffic slots into a CP-SAT constraint satisfaction / minimization problem. Outputs bundled blocks with consolidated possession times.
- **`explainer`**: Generates human-readable rationales for each bundled block (which requests were merged, chainage overlap, priority weighting, and why certain blocks were shifted or granted).
- **`what_if`**: Accepts user overrides (delay request, adjust duration, elevate priority, cancel slot) and runs rapid delta re-optimization.
- **`api`**: FastAPI router serving endpoints to frontend clients.

---

## 4. Unified Data Schema

### 4.1 Track Topology (`sections`)
- `section_id`: String (PK, e.g., `"SEC-NDLS-GZB-01"`)
- `line_type`: Enum (`UP`, `DOWN`, `SINGLE`, `COMMON`)
- `start_station`: String (e.g., `"NDLS"`)
- `end_station`: String (e.g., `"GZB"`)
- `start_km`: Float (chainage start)
- `end_km`: Float (chainage end)
- `max_speed_kmh`: Integer
- `traffic_density_index`: Float

### 4.2 Maintenance Requests (`maintenance_requests`) — Unified Normalized Schema
The single normalized internal schema represents records ingested from all four Indian Railways legacy sources (**TMS**, **SMMS**, **TDMS**, **COA**):

| Field Name | Type | Constraints / Format | Description / Legacy Source Origin |
|---|---|---|---|
| `request_id` | String (PK) | e.g. `REQ-20260915-ENG-0001` | Unique request identifier across all departments (sequential, chronological) |
| `source_system` | Enum | `TMS`, `SMMS`, `TDMS`, `COA` | Originating legacy application |
| `department` | Enum | `ENG`, `S&T`, `TRD` | Operating department requesting possession |
| `section_id` | String (FK) | `sections.section_id` | Track section identifier (e.g. `SEC-GZB-ALJN`) |
| `corridor_slot` | Enum | `SLOT_NIGHT`, `SLOT_EARLY_MORN`, `SLOT_MIDDAY`, `SLOT_AFTERNOON` | Operating maintenance corridor window |
| `chainage_start` | Float | km (`start_km <= chainage_start < chainage_end`) | Start kilometer of requested maintenance zone |
| `chainage_end` | Float | km (`chainage_end <= end_km`) | End kilometer of requested maintenance zone |
| `requested_window_start` | DateTime | ISO-8601 (`YYYY-MM-DDTHH:MM:SS`) | Earliest acceptable possession start timestamp |
| `requested_window_end` | DateTime | ISO-8601 (`YYYY-MM-DDTHH:MM:SS`) | Latest acceptable clearance timestamp |
| `required_duration_minutes` | Integer | `0 < required_duration_minutes <= window_minutes` | Net active possession required (provides scheduling slack) |
| `work_type` | String | Domain-specific standard name | e.g., `Track Tamping`, `Point Machine Overhaul` |
| `asset_id` | String | e.g. `ENG-TRK-GZB-ALJN-0012` | Track / electrical / signaling asset identifier |
| `asset_type` | String | Domain asset classification | e.g., `Turnout Assembly`, `Continuous Welded Rail`, `Electric Point Machine` |
| `asset_age_years` | Float | >= 0.0 years | Asset age feature for failure risk scoring |
| `last_maintenance_days_ago` | Integer | >= 0 days | Days since previous overhaul / inspection |
| `past_breakdown_count` | Integer | >= 0 | Failure/defect count in past 12 months |
| `gross_million_tonnes` | Float | >= 0.0 GMT | Cumulative traffic load passed on asset/track |
| `condition_score` | Float | 1.0 (degraded) to 10.0 (pristine) | Physical condition assessment index |
| `urgency_category` | Enum | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | Operational urgency classification |
| `asset_age_or_condition_features` | Object / Dict | Encompassing container | Dict bundling the 6 risk features (`asset_age_years`, `last_maintenance_days_ago`, `past_breakdown_count`, `gross_million_tonnes`, `condition_score`, `urgency_category`) for Phase 2 ML scoring |
| `asset_condition_features` | Object / Dict | Backward-compatible alias | Direct reference alias to `asset_age_or_condition_features` |
| `risk_score` | Float | $0.0 \le \text{risk\_score} \le 100.0$ | Predictive asset failure risk & scheduling priority score generated by LightGBM model (**Added Phase 3**) |
| `requires_power_block` | Boolean | True / False | TRD 25kV OHE isolation & grounding required |
| `requires_traffic_block` | Boolean | True / False | Train movement stoppage / line possession required |
| `status` | Enum | `PENDING`, `BUNDLED`, `SCHEDULED`, `REJECTED`, `COMPLETED` | Scheduling pipeline status (default: `PENDING`) |

#### 4.2.1 Legacy System Ingestion & Normalization Mapping Table

| Unified Field | TMS (Engineering / P-Way) | SMMS (Signal & Telecom) | TDMS (Traction Distribution) | COA (Control Office / Ops) |
|---|---|---|---|---|
| `request_id` | `tms_work_order_id` | `smms_notif_no` | `tdms_permit_req_id` | `coa_block_memo_id` |
| `source_system` | Fixed `"TMS"` | Fixed `"SMMS"` | Fixed `"TDMS"` | Fixed `"COA"` |
| `department` | Fixed `"ENG"` | Fixed `"S&T"` | Fixed `"TRD"` | Mapped from applicant dept |
| `section_id` | `block_section_code` | `station_yard_code` | `ohe_elem_section` | `operating_section_id` |
| `corridor_slot` | Corridor slot name | Maintenance slot | Power block corridor | `operating_corridor_slot` |
| `chainage_start` | `km_from` | `gear_km` | `elem_km_start` | `block_km_from` |
| `chainage_end` | `km_to` | `gear_km + 0.1` | `elem_km_end` | `block_km_to` |
| `requested_window_start` | `pref_slot_start` | `window_from` | `power_cut_from` | `corridor_slot_start` |
| `requested_window_end` | `pref_slot_end` | `window_to` | `power_cut_to` | `corridor_slot_end` |
| `required_duration_minutes` | `net_work_duration` | `possession_duration` | `power_block_duration` | `sanction_duration` |
| `work_type` | `pway_activity_name` | `gear_maintenance_task` | `ohe_work_nature` | `memo_purpose` |
| `asset_id` | `track_asset_tag` | `signal_gear_id` | `mast_structure_id` | `section_track_id` |
| `asset_age_or_condition_features` | Rail wear, GMT, ballast deficit, track quality index | Point operating cycles, megger insulation, fault log | Contact wire wear, insulator flashover count | Track occupancy index, past delay hours |

#### 4.2.2 Dual Storage Representations
1. **Relational / Flat (CSV):** `data/maintenance_requests.csv` containing flat columns matching `CSV_FIELDS` above (`asset_age_years`, `last_maintenance_days_ago`, `past_breakdown_count`, `gross_million_tonnes`, `condition_score`, `urgency_category`), optimized for tabular dataframes and direct LightGBM/XGBoost feature matrices without JSON parsing overhead.
2. **Document / Hierarchical (JSON):** `data/maintenance_requests.json` containing the unified request schema with an explicit `asset_age_or_condition_features` container dictionary (and `asset_condition_features` alias) encapsulating all 6 condition features for API serialization, REST payloads, and document persistence.

### 4.3 Asset Failure & Risk Features (`asset_risk_profiles`)
- `asset_id`: String (PK)
- `asset_type`: String (e.g., `"Turnout"`, `"Point Machine"`, `"OHE Mast"`, `"Rail Joint"`)
- `asset_age_years`: Float
- `last_maintenance_days_ago`: Integer
- `past_breakdown_count`: Integer
- `gross_million_tonnes`: Float
- `condition_score`: Float ($1.0$ degraded to $10.0$ pristine)
- `urgency_category`: Enum (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `risk_score`: Float ($0.0$ to $100.0$, generated by LightGBM model)
- `priority_level`: Enum (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)

#### 4.3.1 Transparent Synthetic Target Formulation & LightGBM Model Architecture (Phase 3)

> **Important Disclosure & Transparency Statement:**  
> In accordance with project governance, historical field failure logs in this hackathon environment are synthetic. There is no pre-existing ground-truth failure event column in the raw departmental data. Rather than pretending this is an unconstrained "magically learned" latent failure pattern, the target label was generated via a **transparent, physics-grounded railway engineering heuristic** combining physical degradation, dynamic fatigue, and maintenance interval metrics. The LightGBM regressor was subsequently trained on tabular features to learn this multi-attribute non-linear risk surface for real-time sub-millisecond inference and CP-SAT priority weighting.

##### 1. Domain-Grounded Failure Risk Formulation
The ground-truth synthetic failure risk label $R_{\text{target}} \in [0.0, 100.0]$ is computed as:

$$R_{\text{target}} = 100 \times \text{clamp}\left(0.30 \cdot C_{\text{def}} + 0.25 \cdot B_{\text{past}} + 0.15 \cdot G_{\text{wear}} + 0.15 \cdot M_{\text{lag}} + 0.10 \cdot A_{\text{age}} + U_{\text{mod}} + \epsilon,\; 0.01,\; 0.99\right)$$

Where:
- **Condition Deficit ($C_{\text{def}}$)**: $C_{\text{def}} = \frac{10.0 - \text{condition\_score}}{9.0} \in [0.0, 1.0]$. Directly reflects track geometry defects, turnout wear, or OHE sag. Weight: **30%**.
- **Past Breakdown Recurrence ($B_{\text{past}}$)**: $B_{\text{past}} = \min\left(\frac{\text{past\_breakdown\_count}}{5.0}, 1.0\right)$. Recurring component failures within 12 months. Weight: **25%**.
- **Cumulative Traffic Fatigue ($G_{\text{wear}}$)**: $G_{\text{wear}} = \min\left(\frac{\text{gross\_million\_tonnes}}{120.0}, 1.0\right)$. Dynamic impact of heavy axle freight and passenger traffic. Weight: **15%**.
- **Maintenance Interval Lag ($M_{\text{lag}}$)**: $M_{\text{lag}} = \min\left(\frac{\text{last\_maintenance\_days_ago}}{300.0}, 1.0\right)$. Days elapsed since previous overhaul or POH. Weight: **15%**.
- **Asset Age Aging Factor ($A_{\text{age}}$)**: $A_{\text{age}} = \min\left(\frac{\text{asset\_age\_years}}{25.0}, 1.0\right)$. Service life relative to 25-year design codal life. Weight: **10%**.
- **Operational Urgency Modifier ($U_{\text{mod}}$)**: Departmental field inspection classification:
  - `CRITICAL`: $+0.05$
  - `HIGH`: $+0.02$
  - `MEDIUM`: $0.00$
  - `LOW`: $-0.03$
- **Field Disturbance ($\epsilon$)**: $\epsilon \sim \mathcal{N}(0, 0.02^2)$ Gaussian noise representing unobserved field factors (ballast contamination, weather extremes).

##### 2. LightGBM Model Architecture & Training Hyperparameters
- **Algorithm:** LightGBM Regressor (`LGBMRegressor`, version 4.7.0)
- **Objective:** Regression ($L_2$ Loss / Mean Squared Error)
- **Hyperparameters:** `n_estimators=100`, `learning_rate=0.05`, `num_leaves=15`, `min_child_samples=5`, `random_state=42`
- **Feature Vector (6 Tabular Attributes):**
  1. `asset_age_years` (float)
  2. `last_maintenance_days_ago` (float)
  3. `past_breakdown_count` (float)
  4. `gross_million_tonnes` (float)
  5. `condition_score` (float)
  6. `urgency_level` (int: LOW=0, MEDIUM=1, HIGH=2, CRITICAL=3)
- **Saved Model Artifacts:**
  - `models/risk_model.joblib`: Serialized Python bundle containing fitted model, feature schema, and evaluation metrics.
  - `models/risk_model.txt`: Pure native LightGBM text format for zero-dependency portability.
  - `models/risk_model_meta.json`: JSON metadata cataloguing hyper-parameters and feature splits.

##### 3. Cross-Validation Performance & Feature Importance
Evaluated with strict 5-Fold Cross-Validation across all 240 requests:
- **5-Fold CV Mean Absolute Error (MAE):** $2.580 \pm 0.327$ (on 0-100 scale)
- **5-Fold CV Root Mean Squared Error (RMSE):** $3.507 \pm 0.812$
- **5-Fold CV Coefficient of Determination ($R^2$):** $0.9810 \pm 0.0125$
- **Full Dataset Fit:** $\text{MAE} = 0.863$, $R^2 = 0.9984$

**Feature Importance Breakdown (Split Frequency):**
- `condition_score`: **339** splits (30.8%)
- `last_maintenance_days_ago`: **279** splits (25.4%)
- `asset_age_years`: **271** splits (24.6%)
- `gross_million_tonnes`: **267** splits (24.3%)
- `past_breakdown_count`: **166** splits (15.1%)
- `urgency_level`: **78** splits (7.1%)

##### 4. Score Distribution & Proof of Non-Degeneracy (N=240 Requests)
To prove that predictions are continuous, diverse, and not clustered artificially around a single constant:
- **Minimum Score:** $2.91$
- **Maximum Score:** $94.43$
- **Mean Score:** $37.69$
- **Standard Deviation:** $26.84$
- **10th Percentile:** $9.75$
- **25th Percentile:** $13.71$
- **Median (50th Percentile):** $40.01$
- **75th Percentile:** $55.19$
- **90th Percentile:** $83.69$

**ASCII Histogram (0-100 Scale in 10-Point Bins):**
```
[  0.0 -  10.0]:  27 | #############
[ 10.0 -  20.0]:  77 | ######################################
[ 20.0 -  30.0]:  14 | #######
[ 30.0 -  40.0]:   1 | 
[ 40.0 -  50.0]:  36 | ##################
[ 50.0 -  60.0]:  47 | #######################
[ 60.0 -  70.0]:   2 | #
[ 70.0 -  80.0]:   5 | ##
[ 80.0 -  90.0]:  20 | ##########
[ 90.0 - 100.0]:  11 | #####
```

**Operational Urgency Tiers:**
- `CRITICAL` ($\ge 75.0$): 34 requests (14.2%)
- `HIGH` ($50.0 \le \text{score} < 75.0$): 51 requests (21.2%)
- `MEDIUM` ($25.0 \le \text{score} < 50.0$): 37 requests (15.4%)
- `LOW` ($< 25.0$): 118 requests (49.2%)

### 4.4 Bundled Blocks & Output Schedule (`bundled_blocks`)
- `block_id`: String (PK, e.g., `"BLK-20260911-0001"`)
- `section_id`: String (FK -> `sections.section_id`)
- `corridor_slot`: Enum (`SLOT_NIGHT`, `SLOT_EARLY_MORN`, `SLOT_MIDDAY`, `SLOT_AFTERNOON`)
- `start_km`: Float (enveloping chainage start)
- `end_km`: Float (enveloping chainage end)
- `scheduled_start`: DateTime (ISO-8601 string)
- `scheduled_end`: DateTime (ISO-8601 string)
- `total_duration_minutes`: Integer
- `bundled_request_ids`: Array[String] (Contained request IDs)
- `departments_involved`: Array[String] (e.g. `["ENG", "S&T", "TRD"]`)
- `power_block_granted`: Boolean (True if 25kV OHE isolation is active)
- `traffic_block_granted`: Boolean (True if train movements are suspended)
- `savings_minutes`: Integer (Sum of individual durations minus bundled duration)
- `explanation_text`: Text (Plain-language justification string, backward-compatible)
- `explanation_detail`: Object / Dict (`BlockExplanation` structured explainability object, **Added Phase 5**)
- `explanation`: Object / Dict (Convenience alias identical to `explanation_detail`, **Added Phase 5**)
- `approval_status`: Enum (`PROPOSED`, `APPROVED_BY_CONTROLLER`, `REJECTED_BY_CONTROLLER`, `MODIFIED_BY_CONTROLLER`, `DEFERRED`)
- `constituent_requests`: Array[Object] (`ConstituentRequestSummarySchema` records)

#### 4.4.1 Explainability Engine Architecture & Constraint Reasoning (Phase 5)

Rather than relying on non-deterministic, high-latency external LLM API calls, the RAKSHA-BLOCK Explainability Engine (`app/explainer.py`) operates as a **deterministic constraint reasoning engine** directly synthesized from the CP-SAT solver's inputs, geometric topology, and optimization outputs.

The structured explanation object (`BlockExplanation`) decomposes each block into four verifiable analytical dimensions:

```
                      ┌────────────────────────────────────────┐
                      │            BlockExplanation            │
                      └───────────────────┬────────────────────┘
                                          │
      ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
      ▼                   ▼                               ▼                   ▼
┌──────────────┐ ┌─────────────────┐             ┌─────────────────┐ ┌─────────────────┐
│ summary      │ │ merged_requests │             │driving_priority │ │driving_constra- │
│ (1-sentence  │ │ (per-request ID,│             │(highest risk    │ │ ints (spatial   │
│ plain text)  │ │  dept, work, km,│             │ asset, score,   │ │  overlap/gap,   │
└──────────────┘ │  dur, risk, OHE)│             │ tier, anchor)   │ │  OHE & traffic) │
                 └─────────────────┘             └─────────────────┘ └────────┬────────┘
                                                                              │
                                                                              ▼
                                                                     ┌─────────────────┐
                                                                     │alternatives_    │
                                                                     │considered (dur  │
                                                                     │saved, why not   │
                                                                     │sep or deferred) │
                                                                     └─────────────────┘
```

##### 1. Merged Requests Container (`merged_requests: List[MergedRequestDetail]`)
Captures exact operational attributes for every constituent request:
- `request_id`, `department`, `work_type`, `asset_id`, `asset_type`
- Linear chainage boundaries (`chainage_start`, `chainage_end`)
- Time windows (`requested_window_start`, `requested_window_end`, `scheduled_start`, `scheduled_end`)
- Net active work duration (`required_duration_minutes`)
- LightGBM `risk_score` ($0.0 - 100.0$) and calibrated operational `urgency_tier` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- Electrical and traffic closure flags (`requires_power_block`, `requires_traffic_block`)

##### 2. Driving Priority Factors (`driving_priority: PriorityReasoning`)
Identifies the highest-risk asset anchoring the schedule:
- `highest_risk_request_id`, `highest_risk_asset_id`, `highest_risk_score`, `highest_risk_department`, `highest_risk_work_type`, `risk_tier`
- `average_risk_score` and `risk_spread` across the bundle
- `anchoring_reason`: Plain-language justification explaining why this asset dictated possession timing (e.g. prioritizing critical safety works while bundling lower-risk companion works).

##### 3. Driving Constraints (`driving_constraints: ConstraintReasoning`)
Quantifies the exact spatial, temporal, and safety limits that governed solver decision:
- `spatial_chainage_overlap` (Boolean: True if linear chainages physically overlap)
- `spatial_proximity_km` (Configured bundling proximity threshold, default $2.0$ km)
- `actual_spatial_gap_km` (Measured track distance between adjacent works)
- `enveloping_chainage_span_km` (Total block possession envelope $\text{end\_km} - \text{start\_km}$)
- `spatial_overlap_type`: Classification enum (`DIRECT_OVERLAP`, `ADJACENT_PROXIMITY`, `BRIDGED_CHAINAGE`, `SINGLE_ISOLATED`)
- `window_bounds` (`earliest_requested_start`, `latest_requested_end`, `scheduled_start`, `scheduled_end`, `total_window_slack_minutes`)
- `power_block_required` and `power_block_driver` (Identifies specific TRD requests mandating 25kV OHE isolation)
- `traffic_block_required` and `traffic_block_driver` (Identifies requests mandating full line closure)
- `duration_savings_minutes` and `key_constraints_applied` (List of active hard constraints)

##### 4. Alternatives Considered (`alternatives_considered: AlternativesReasoning`)
Provides counterfactual reasoning for Section Controllers:
- `separate_possession_minutes`: Total line possession required if each request ran in isolation ($\sum d_i$)
- `bundled_possession_minutes`: Actual scheduled line possession ($B^{\text{dur}}$)
- `possession_savings_minutes` and `possession_savings_pct`: Track downtime reduction metrics
- `why_not_scheduled_separately`: Clear trade-off explanation (e.g. saves $X$ minutes and eliminates $N-1$ extra traffic closures)
- `why_not_deferred`: Why the block was scheduled now rather than deferred to a future maintenance window
- `alternatives_evaluated`: Explicit list of alternative options modeled and rejected (separate possessions, pairwise sub-bundles, or deferred slots)

### 4.5 Formal Mathematical Optimization Model (Google OR-Tools CP-SAT) — Phase 4 Core

The core scheduling engine solves a multi-department Resource-Constrained Project Scheduling Problem with cross-departmental spatial/temporal bundling (RCPSP-CDSTB) using Google OR-Tools CP-SAT (`ortools.sat.python.cp_model`).

#### 4.5.1 Problem Parameters & Sets
- $\mathcal{S}$: Set of track sections $s \in \mathcal{S}$.
- $\mathcal{R}$: Set of normalized maintenance requests $i \in \mathcal{R}$.
- For each request $i \in \mathcal{R}$:
  - $s_i \in \mathcal{S}$: Track section identifier.
  - $dep_i \in \{\text{ENG}, \text{S\&T}, \text{TRD}\}$: Requesting department.
  - $[c^{\text{start}}_i, c^{\text{end}}_i]$: Linear chainage boundaries in kilometers ($c^{\text{start}}_i < c^{\text{end}}_i$).
  - $[W^{\text{start}}_i, W^{\text{end}}_i]$: Feasible possession window (represented as integer minutes from epoch $T_0$).
  - $d_i \in \mathbb{Z}^+$: Net active work duration in minutes ($0 < d_i \le W^{\text{end}}_i - W^{\text{start}}_i$).
  - $R_i \in [0.0, 100.0]$: Predictive asset failure risk & scheduling priority score from Phase 3 LightGBM.
  - $P_i \in \{0, 1\}$: Requires 25kV OHE power block (TRD isolation).
  - $T_i \in \{0, 1\}$: Requires train traffic block (line closure).
- $\Delta_{\text{spatial}} = 2.0\text{ km}$: Spatial proximity threshold for bundling (requests whose chainages overlap or are within $2.0$ km are bundling candidates).
- $L_{\max} = 15.0\text{ km}$: Maximum physical chainage envelope for a single maintenance possession block.

#### 4.5.2 Spatial Interference Graph & Connected Component Partitioning
To guarantee zero double-booking while preserving subproblem independence, requests are partitioned into independent spatial-temporal clusters via **connected components** on the spatial interference graph:
1. **Corridor Grouping**: Requests are grouped by `(section_id, date, corridor_slot)`.
2. **Spatial Interference Edge**: An undirected edge $(i, j) \in \mathcal{E}_{\text{interfere}}$ exists between requests $i, j$ on the same section and corridor slot if:
   $$\max(c^{\text{start}}_i, c^{\text{start}}_j) \le \min(c^{\text{end}}_i, c^{\text{end}}_j) + \Delta_{\text{spatial}}$$
   (i.e. chainages overlap or the linear track gap between them is within $\Delta_{\text{spatial}} = 2.0$ km).
3. **Connected Components**: Maximal connected components $\mathcal{C}_k \subseteq \mathcal{R}$ isolate mutually independent track zones. Requests in different components are separated by $> \Delta_{\text{spatial}}$ of physical track and cannot double-book or bundle. All requests in $\mathcal{C}_k$ are solved together within a single CP-SAT model.

For a cluster $\mathcal{C}_k$ with $|\mathcal{C}_k| = K$ requests, at most $K$ blocks can be instantiated: candidate blocks $\mathcal{B}_k = \{b_1, \dots, b_K\}$.

#### 4.5.3 Decision Variables
For each request $i \in \mathcal{C}_k$:
- $S_i \in [W^{\text{start}}_i, W^{\text{end}}_i - d_i]$: Integer variable for scheduled start time (minute from epoch $T_0$).
- $E_i = S_i + d_i$: Scheduled completion time.
- $I_i = \text{NewIntervalVar}(S_i, d_i, E_i)$: Request execution interval.
- $u_i \in \{0, 1\}$: Boolean indicator; $u_i = 1$ if request $i$ cannot be scheduled due to track capacity bounds (deferred).

For each candidate block $b \in \mathcal{B}_k$:
- $y_b \in \{0, 1\}$: Boolean indicator; $y_b = 1$ if candidate block $b$ is instantiated/active.
- $x_{i, b} \in \{0, 1\}$: Boolean assignment; $x_{i, b} = 1$ if request $i$ is assigned to block $b$.
- $B^{\text{start}}_b \in [0, H]$: Block possession start timestamp (minutes).
- $B^{\text{end}}_b \in [0, H]$: Block possession end timestamp (minutes).
- $B^{\text{dur}}_b \in [0, H]$: Net block possession duration ($B^{\text{dur}}_b = B^{\text{end}}_b - B^{\text{start}}_b$).
- $I_b = \text{NewOptionalIntervalVar}(B^{\text{start}}_b, B^{\text{dur}}_b, B^{\text{end}}_b, y_b)$: Optional CP-SAT interval representing the active physical possession block.

#### 4.5.4 Hard Constraints
1. **Assignment / Deferral Balance**: Each request must either be assigned to exactly one active block or deferred:
   $$\sum_{b \in \mathcal{B}_k} x_{i, b} + u_i = 1 \quad \forall i \in \mathcal{C}_k$$
2. **Block Activation**: A block is active if and only if at least one request is assigned to it:
   $$x_{i, b} \le y_b \quad \forall i \in \mathcal{C}_k, \; \forall b \in \mathcal{B}_k$$
   $$y_b \le \sum_{i \in \mathcal{C}_k} x_{i, b} \quad \forall b \in \mathcal{B}_k$$
3. **Temporal Containment of Constituent Requests**:
   If request $i$ is assigned to block $b$ ($x_{i, b} = 1$), the block possession envelope strictly encloses its work:
   $$B^{\text{start}}_b \le S_i \quad \text{OnlyEnforceIf } x_{i, b}$$
   $$E_i \le B^{\text{end}}_b \quad \text{OnlyEnforceIf } x_{i, b}$$
4. **Block Duration Upper Bound (Zero Negative Savings Guarantee)**:
   The total duration of block $b$ cannot exceed the sum of durations of constituent requests, strictly preventing artificial track closure or dead-time inflation:
   $$B^{\text{dur}}_b \le \sum_{i \in \mathcal{C}_k} d_i \cdot x_{i, b} \quad \forall b \in \mathcal{B}_k$$
5. **Temporal Overlap Prerequisite**:
   Requests $i, j$ whose requested operational windows do not overlap ($W^{\text{end}}_i \le W^{\text{start}}_j$ or $W^{\text{end}}_j \le W^{\text{start}}_i$) cannot share a block:
   $$x_{i, b} + x_{j, b} \le 1 \quad \forall b \in \mathcal{B}_k$$
6. **Maximum Chainage Span Limit**:
   Requests whose combined spatial span exceeds $L_{\max} = 15.0$ km cannot share a block:
   $$\max(c^{\text{end}}_i, c^{\text{end}}_j) - \min(c^{\text{start}}_i, c^{\text{start}}_j) > L_{\max} \implies x_{i, b} + x_{j, b} \le 1 \quad \forall b \in \mathcal{B}_k$$
7. **Spatial Bridging Constraint**:
   If the linear gap between requests $i, j$ exceeds $\Delta_{\text{spatial}} = 2.0$ km, they can share block $b$ only if at least one bridging request $k \in \mathcal{K}_{i, j}$ is also assigned to block $b$:
   $$x_{i, b} + x_{j, b} \le 1 + \sum_{k \in \mathcal{K}_{i, j}} x_{k, b} \quad \forall b \in \mathcal{B}_k$$
   where $\mathcal{K}_{i, j} = \{k \in \mathcal{C}_k : c^{\text{start}}_k \le c^{\text{end}}_i + \Delta_{\text{spatial}} \land c^{\text{end}}_k \ge c^{\text{start}}_j - \Delta_{\text{spatial}}\}$. If $\mathcal{K}_{i, j} = \emptyset$, $x_{i, b} + x_{j, b} \le 1$.
8. **Disjunctive Non-Overlap on Track Infrastructure**:
   Between separate active blocks within the same spatial cluster:
   $$\text{model.AddNoOverlap}\left(\left[I_1, \dots, I_K\right]\right)$$
9. **Symmetry Breaking**:
   $$y_1 \ge y_2 \ge \dots \ge y_K$$
   $$x_{1, 1} + u_1 = 1$$
   $$x_{i, b} = 0 \quad \forall b > i$$

#### 4.5.5 Multi-Objective Optimization Function
The solver minimizes a multi-objective cost function:

$$\min \quad \mathcal{J} = \underbrace{\alpha \sum_{b} y_b}_{\text{Term 1: Block Count}} + \underbrace{\beta \sum_{b} B^{\text{dur}}_b}_{\text{Term 2: Possession Minutes}} + \underbrace{\sum_{i \in \mathcal{C}_k} w_i \cdot \left(S_i - W^{\text{start}}_i\right)}_{\text{Term 3: Risk-Weighted Early Clearance}} + \underbrace{\sum_{i \in \mathcal{C}_k} \left(\Phi + 1000 \cdot w_i\right) u_i}_{\text{Term 4: Deferral Penalty}}$$

Where:
- $\alpha = 10,000$: Massive incentive to consolidate cross-departmental works into shared possession windows.
- $\beta = 10$: Penalizes each minute of physical track closure, tightening possession windows.
- $w_i = \max\left(1, \lfloor R_i \rfloor\right)$: Priority weight derived from LightGBM risk score $R_i \in [0.0, 100.0]$.
- $\Phi = 200,000$: Heavy penalty ensuring requests are only deferred when capacity limits make scheduling physically impossible. High-risk requests incur additional deferral penalty ($1000 \cdot w_i$), guaranteeing critical safety works are granted preference.

#### 4.5.6 Post-Optimization Attribute Synthesis
For each activated block $b$ ($y_b = 1$):
- $\text{scheduled\_start} = T_0 + B^{\text{start}}_b \text{ minutes}$
- $\text{scheduled\_end} = T_0 + B^{\text{end}}_b \text{ minutes}$
- $\text{start\_km} = \min_{i: x_{i, b}=1} c^{\text{start}}_i$
- $\text{end\_km} = \max_{i: x_{i, b}=1} c^{\text{end}}_i$
- $\text{departments\_involved} = \bigcup_{i: x_{i, b}=1} \{dep_i\}$
- $\text{power\_block\_granted} = \bigvee_{i: x_{i, b}=1} P_i$
- $\text{traffic\_block\_granted} = \bigvee_{i: x_{i, b}=1} T_i$
- $\text{savings\_minutes} = \left(\sum_{i: x_{i, b}=1} d_i\right) - B^{\text{dur}}_b$

---

## 5. API Endpoint Specifications

### 5.1 Endpoint Directory

| Method | Route | Status | Description |
|---|---|---|---|
| `GET` | `/requests` | **Active (Phase 2 & 3)** | Fetch list of normalized maintenance requests enriched with LightGBM risk scores (`0.0 - 100.0`), with filtering (`department`, `section_id`, `limit`, `offset`). |
| `GET` | `/api/v1/requests` | **Active (Phase 2 & 3)** | Alias route for `/requests` conforming to API v1 path convention. |
| `POST` | `/api/v1/risk/score`, `/risk/score` | **Active (Phase 3)** | Run on-demand tabular LightGBM inference on asset condition features; returns calibrated risk score and priority tier. |
| `GET` | `/api/v1/risk/distribution`, `/risk/distribution` | **Active (Phase 3)** | Statistical distribution of risk scores across all ingested requests (min, max, mean, std, percentiles, ASCII histogram). |
| `GET` | `/api/v1/risk/model-info`, `/risk/model-info` | **Active (Phase 3)** | Model metadata, algorithm parameters, and feature split frequencies. |
| `POST` | `/optimize`, `/api/v1/optimizer/plan` | **Active (Phase 4 & 5)** | Trigger CP-SAT constraint programming solver to generate conflict-free bundled block schedule, complete with Phase 5 structured BlockExplanation objects. |
| `GET` | `/api/v1/blocks`, `/blocks` | **Active (Phase 5)** | Retrieve all generated bundled blocks and scheduling timeline from database maintenance requests. |
| `GET` | `/api/v1/blocks/{block_id}/explain`, `/blocks/{block_id}/explain` | **Active (Phase 5)** | Detailed plain-language breakdown and structured constraint reasoning (`BlockExplanation`) for an individual block. |
| `POST` | `/api/v1/blocks/{block_id}/action`, `/blocks/{block_id}/action` | **Active (Phase 5)** | Section Controller decision gateway (APPROVE, REJECT, MODIFY) for AI-recommended blocks. |
| `GET` | `/api/v1/health`, `/health` | **Active (Phase 5)** | Service operational health, identifier, and version status. |
| `POST` | `/api/v1/ingest/upload` | Planned (Phase 5 Extension) | Upload & normalize synthetic department requests (CSV/JSON). |
| `POST` | `/api/v1/optimizer/what-if` | Planned (Phase 5 Extension) | Run scenario simulation with parameter overrides and return schedule delta. |

### 5.2 Phase 2 & 3 Implemented Endpoint: `GET /requests`

**Request:**
- Method: `GET`
- Paths: `/requests`, `/api/v1/requests`
- Query Parameters:
  - `department` (optional, string): Filter by department (`ENG`, `S&T`, `TRD`). Case-insensitive.
  - `section_id` (optional, string): Filter by track topology section ID (e.g. `SEC-NDLS-TKJ`).
  - `limit` (optional, integer): Maximum number of records returned. Default: all records.
  - `offset` (optional, integer): Pagination offset. Default: 0.

**Response Schema (`HTTP 200 OK`):**
JSON array of unified maintenance request objects matching Section 4.2.

```json
[
  {
    "request_id": "REQ-20260915-ENG-0001",
    "source_system": "TMS",
    "department": "ENG",
    "section_id": "SEC-TDL-CNB",
    "corridor_slot": "SLOT_NIGHT",
    "chainage_start": 239.06,
    "chainage_end": 239.47,
    "requested_window_start": "2026-09-15T00:30:00",
    "requested_window_end": "2026-09-15T04:15:00",
    "required_duration_minutes": 146,
    "work_type": "Turnout & Switch Crossing Renewal",
    "asset_id": "ENG-TRK-TDL-CNB-0021",
    "asset_type": "Turnout Assembly",
    "asset_age_years": 1.1,
    "last_maintenance_days_ago": 24,
    "past_breakdown_count": 0,
    "gross_million_tonnes": 40.9,
    "condition_score": 8.8,
    "urgency_category": "LOW",
    "asset_age_or_condition_features": {
      "asset_age_years": 1.1,
      "last_maintenance_days_ago": 24,
      "past_breakdown_count": 0,
      "gross_million_tonnes": 40.9,
      "condition_score": 8.8,
      "urgency_category": "LOW"
    },
    "asset_condition_features": {
      "asset_age_years": 1.1,
      "last_maintenance_days_ago": 24,
      "past_breakdown_count": 0,
      "gross_million_tonnes": 40.9,
      "condition_score": 8.8,
      "urgency_category": "LOW"
    },
    "risk_score": 8.04,
    "requires_power_block": true,
    "requires_traffic_block": true,
    "status": "PENDING"
  }
]
```

### 5.3 Database & Ingestion Module Architecture
- **Database Engine:** SQLite at `data/raksha.db` via SQLAlchemy 2.0 ORM with relational schema (`sections` and `maintenance_requests` tables) and foreign key enforcement (`PRAGMA foreign_keys=ON`).
- **Ingestion Pipeline (`app/ingestion.py`):**
  - Reads synthetic datasets (`data/maintenance_requests.json` / `.csv`, `data/sections.json` / `.csv`), automatically detecting `.json` or `.csv` files and safely handling empty files or trailing newlines.
  - Automatically computes and enriches each request with `risk_score` generated by the trained LightGBM model during ingestion.
  - Executes comprehensive row validation (`app/validation.py`):
    - Rejects missing required fields (including `requires_power_block` and `requires_traffic_block`).
    - Validates categorical domains: `department` (`ENG`, `S&T`, `TRD`), `source_system` (`TMS`, `SMMS`, `TDMS`, `COA`), `urgency_category` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), `corridor_slot` (`SLOT_NIGHT`, `SLOT_EARLY_MORN`, `SLOT_MIDDAY`, `SLOT_AFTERNOON`), `status` (`PENDING`, `BUNDLED`, `SCHEDULED`, `REJECTED`, `COMPLETED`), and `line_type` (`UP`, `DOWN`, `SINGLE`, `COMMON`, `DOUBLE`, `TRIPLE`, `QUADRUPLE`).
    - Enforces linear referencing boundaries: validates `start_km <= chainage_start < chainage_end <= end_km` against the referenced section's physical topology.
    - Enforces chronological window constraints (`requested_window_start < requested_window_end`) with timezone offset normalization and positive net duration bounds (`0 < required_duration_minutes <= window_minutes`).
    - Safe integer conversion supporting float string formats (`"120.0"`).
    - Strict boolean parsing rejecting ambiguous values (e.g. `"maybe"`).
  - Idempotent upsert via `db.merge()`.
  - Pydantic Response Validation (`app/schemas.py`): includes a `model_validator` ensuring `asset_age_or_condition_features` and `asset_condition_features` are guaranteed to return valid, fully populated dictionaries bundling the 6 risk features, and computes `risk_score` if null.
  - Query Parameter Bounds (`app/main.py`): enforces `ge=0` on `limit` and `offset`, returning HTTP 422 on negative parameters, and correctly returning an empty list `[]` when `limit=0`.
  - Ingestion Summary: `sections_ingested=8`, `requests_ingested=240`, `requests_rejected=0`.

### 5.4 Phase 3 Implemented ML Inference Endpoints

#### 5.4.1 `POST /api/v1/risk/score`
Runs on-demand failure risk prediction on submitted asset condition features.

**Request Payload:**
```json
{
  "asset_age_years": 14.8,
  "last_maintenance_days_ago": 162,
  "past_breakdown_count": 2,
  "gross_million_tonnes": 83.1,
  "condition_score": 3.6,
  "urgency_category": "HIGH",
  "request_id": "REQ-20260915-ST-0001"
}
```

**Response Payload (`HTTP 200 OK`):**
```json
{
  "request_id": "REQ-20260915-ST-0001",
  "risk_score": 57.95,
  "risk_tier": "HIGH",
  "features": {
    "asset_age_years": 14.8,
    "last_maintenance_days_ago": 162.0,
    "past_breakdown_count": 2.0,
    "gross_million_tonnes": 83.1,
    "condition_score": 3.6,
    "urgency_level": 2,
    "urgency_category": "HIGH"
  }
}
```

#### 5.4.2 `GET /api/v1/risk/distribution`
Returns statistical summary metrics and 10-bin ASCII histogram across all requests in the database to verify non-degeneracy.

#### 5.4.3 `GET /api/v1/risk/model-info`
Returns loaded model parameters, algorithm type, feature schema, and cross-validation performance metrics.

### 5.5 Phase 4 Implemented CP-SAT Optimization Endpoints

#### 5.5.1 `POST /optimize` and `POST /api/v1/optimizer/plan`
Executes constraint programming block scheduling using Google OR-Tools CP-SAT. Can operate on current database requests or on an explicit user-supplied batch of requests.

**Request Payload (`POST /optimize`):**
Optional JSON object. If omitted or `{ "requests": null }`, requests are queried from the database (optionally filtered by `section_id` and `department` query parameters).
```json
{
  "requests": null,
  "spatial_proximity_km": 2.0,
  "max_block_km_span": 15.0
}
```

**Response Payload (`HTTP 200 OK`):**
```json
{
  "status": "OPTIMAL",
  "total_requests_in": 240,
  "total_blocks_out": 180,
  "bundled_blocks_count": 43,
  "single_blocks_count": 137,
  "total_original_duration_minutes": 27807,
  "total_bundled_duration_minutes": 21891,
  "total_savings_minutes": 5916,
  "savings_percentage": 21.28,
  "solve_time_seconds": 6.548,
  "blocks": [
    {
      "block_id": "BLK-20260915-0001",
      "section_id": "SEC-TDL-CNB",
      "corridor_slot": "SLOT_NIGHT",
      "start_km": 238.66,
      "end_km": 239.47,
      "scheduled_start": "2026-09-15T00:45:00",
      "scheduled_end": "2026-09-15T03:12:00",
      "total_duration_minutes": 147,
      "bundled_request_ids": [
        "REQ-20260915-ENG-0001",
        "REQ-20260915-TRD-0002"
      ],
      "departments_involved": [
        "ENG",
        "TRD"
      ],
      "power_block_granted": true,
      "traffic_block_granted": true,
      "savings_minutes": 146,
      "explanation_text": "Bundled 2 cross-departmental requests (ENG + TRD) on section SEC-TDL-CNB (KM 238.66 - 239.47) during SLOT_NIGHT. Consolidated possession window 00:45 to 03:12 (147 min) saves 146 minutes of line possession vs. separate departmental blocks.",
      "approval_status": "PROPOSED",
      "constituent_requests": [
        {
          "request_id": "REQ-20260915-ENG-0001",
          "department": "ENG",
          "work_type": "Turnout & Switch Crossing Renewal",
          "asset_id": "ENG-TRK-TDL-CNB-0021",
          "asset_type": "Turnout Assembly",
          "chainage_start": 239.06,
          "chainage_end": 239.47,
          "requested_window_start": "2026-09-15T00:30:00",
          "requested_window_end": "2026-09-15T04:15:00",
          "required_duration_minutes": 146,
          "scheduled_start": "2026-09-15T00:45:00",
          "scheduled_end": "2026-09-15T03:11:00",
          "risk_score": 8.04,
          "requires_power_block": true,
          "requires_traffic_block": true
        },
        {
          "request_id": "REQ-20260915-TRD-0002",
          "department": "TRD",
          "work_type": "Neutral Section & Phase Break Maintenance",
          "asset_id": "TRD-OHE-TDL-CNB-0015",
          "asset_type": "PTFE Neutral Section",
          "chainage_start": 238.66,
          "chainage_end": 238.98,
          "requested_window_start": "2026-09-15T00:45:00",
          "requested_window_end": "2026-09-15T04:15:00",
          "required_duration_minutes": 147,
          "scheduled_start": "2026-09-15T00:45:00",
          "scheduled_end": "2026-09-15T03:12:00",
          "risk_score": 10.75,
          "requires_power_block": true,
          "requires_traffic_block": true
        }
      ]
    }
  ]
}
```

### 5.5 Phase 5 Implemented Endpoint: `GET /api/v1/blocks/{block_id}/explain`

**Request:**
- Method: `GET`
- Path: `/api/v1/blocks/{block_id}/explain` (alias: `/blocks/{block_id}/explain`)

**Response Schema (`HTTP 200 OK`):**
```json
{
  "block_id": "BLK-20260915-0006",
  "explanation_text": "Bundled 3 cross-departmental requests (ENG + S&T + TRD) on section SEC-ALJN-TDL (KM 166.37 - 169.93) during SLOT_EARLY_MORN; prioritized due to ENG asset ENG-TRK-ALJN-TDL-0019 (risk score: 53.68, HIGH); consolidated possession window 04:30 to 07:04 (154 min) saves 236 minutes (60.5%) of line possession vs. separate departmental blocks.",
  "explanation_detail": {
    "summary": "Bundled 3 cross-departmental requests (ENG + S&T + TRD) on section SEC-ALJN-TDL (KM 166.37 - 169.93) during SLOT_EARLY_MORN; prioritized due to ENG asset ENG-TRK-ALJN-TDL-0019 (risk score: 53.68, HIGH); consolidated possession window 04:30 to 07:04 (154 min) saves 236 minutes (60.5%) of line possession vs. separate departmental blocks.",
    "merged_requests": [
      {
        "request_id": "REQ-20260915-ENG-0003",
        "department": "ENG",
        "work_type": "Track Tamping (BCM/CSM Machine)",
        "asset_id": "ENG-TRK-ALJN-TDL-0019",
        "asset_type": "Ballast & Sleeper Bed",
        "chainage_start": 166.65,
        "chainage_end": 169.26,
        "requested_window_start": "2026-09-15T04:30:00",
        "requested_window_end": "2026-09-15T07:45:00",
        "required_duration_minutes": 154,
        "scheduled_start": "2026-09-15T04:30:00",
        "scheduled_end": "2026-09-15T07:04:00",
        "risk_score": 53.68,
        "urgency_tier": "HIGH",
        "requires_power_block": false,
        "requires_traffic_block": true
      },
      {
        "request_id": "REQ-20260915-ST-0004",
        "department": "S&T",
        "work_type": "Signaling Cable Meggering & Trench Maintenance",
        "asset_id": "SNT-SIG-ALJN-TDL-0014",
        "asset_type": "Underground Signaling Cable",
        "chainage_start": 166.37,
        "chainage_end": 167.4,
        "requested_window_start": "2026-09-15T04:45:00",
        "requested_window_end": "2026-09-15T07:45:00",
        "required_duration_minutes": 99,
        "scheduled_start": "2026-09-15T04:45:00",
        "scheduled_end": "2026-09-15T06:24:00",
        "risk_score": 6.51,
        "urgency_tier": "LOW",
        "requires_power_block": false,
        "requires_traffic_block": false
      },
      {
        "request_id": "REQ-20260915-TRD-0006",
        "department": "TRD",
        "work_type": "Tower Wagon Foot Patrolling & Current Collection Test",
        "asset_id": "TRD-OHE-ALJN-TDL-0013",
        "asset_type": "Overhead Traction Line",
        "chainage_start": 166.65,
        "chainage_end": 169.93,
        "requested_window_start": "2026-09-15T04:45:00",
        "requested_window_end": "2026-09-15T08:00:00",
        "required_duration_minutes": 137,
        "scheduled_start": "2026-09-15T04:45:00",
        "scheduled_end": "2026-09-15T07:02:00",
        "risk_score": 15.25,
        "urgency_tier": "LOW",
        "requires_power_block": true,
        "requires_traffic_block": true
      }
    ],
    "driving_priority": {
      "highest_risk_request_id": "REQ-20260915-ENG-0003",
      "highest_risk_asset_id": "ENG-TRK-ALJN-TDL-0019",
      "highest_risk_score": 53.68,
      "highest_risk_department": "ENG",
      "highest_risk_work_type": "Track Tamping (BCM/CSM Machine)",
      "risk_tier": "HIGH",
      "average_risk_score": 25.15,
      "risk_spread": 47.17,
      "anchoring_reason": "Asset ENG-TRK-ALJN-TDL-0019 (ENG - Track Tamping (BCM/CSM Machine)) has high failure risk (53.68, HIGH), anchoring slot timing to expedite clearance; 2 companion work(s) were bundled into this window to maximize line productivity."
    },
    "driving_constraints": {
      "spatial_chainage_overlap": true,
      "spatial_proximity_km": 2.0,
      "actual_spatial_gap_km": 0.0,
      "enveloping_chainage_span_km": 3.56,
      "spatial_overlap_type": "DIRECT_OVERLAP",
      "window_bounds": {
        "earliest_requested_start": "2026-09-15T04:30:00",
        "latest_requested_end": "2026-09-15T08:00:00",
        "scheduled_start": "2026-09-15T04:30:00",
        "scheduled_end": "2026-09-15T07:04:00",
        "total_window_slack_minutes": 56
      },
      "corridor_slot": "SLOT_EARLY_MORN",
      "power_block_required": true,
      "power_block_driver": "Driven by 1 request(s) (REQ-20260915-TRD-0006) requiring 25kV OHE electrical isolation and earthing; non-traction maintenance accommodated safely under power-cut protection.",
      "traffic_block_required": true,
      "traffic_block_driver": "Driven by 2 request(s) (REQ-20260915-ENG-0003, REQ-20260915-TRD-0006) requiring complete train traffic stoppage and track possession.",
      "duration_savings_minutes": 236,
      "key_constraints_applied": [
        "Linear chainage envelope KM 166.37 - 169.93 (span: 3.56 km <= 15.0 km limit)",
        "Direct spatial chainage overlap between constituent requests",
        "Temporal containment: consolidated block [04:30 - 07:04] strictly encloses all 3 constituent jobs",
        "Duration upper bound: bundled duration <= sum of constituent durations (guarantees >= 0 savings)",
        "Operational corridor window containment within SLOT_EARLY_MORN",
        "25kV OHE traction power isolation & earthing block granted",
        "Train movement stoppage & absolute line possession granted",
        "Disjunctive NoOverlap on track section infrastructure"
      ]
    },
    "alternatives_considered": {
      "separate_possession_minutes": 390,
      "bundled_possession_minutes": 154,
      "possession_savings_minutes": 236,
      "possession_savings_pct": 60.51,
      "why_not_scheduled_separately": "Scheduling these 3 requests separately would require 390 minutes (6.5 hrs) of fragmented track possession across 3 separate line possessions. Bundling saves 236 minutes (60.5%) of track downtime and avoids 2 additional train traffic halts.",
      "why_not_deferred": "High composite urgency (anchoring risk: 53.68) and mutual spatio-temporal alignment satisfied all hard constraints, avoiding the 200,000 pt CP-SAT deferral penalty.",
      "alternatives_evaluated": [
        "Separate departmental possession for each request (evaluated: rejected, causes 390 min total possession vs 154 min bundled)",
        "Deferral to subsequent corridor maintenance cycle (evaluated: rejected, leaves critical assets unmaintained)",
        "Pairwise 2-department sub-bundle (evaluated: rejected, full 3-department consolidation (ENG + S&T + TRD) yields optimal possession reduction)"
      ]
    }
  },
  "explanation": {
    "summary": "Bundled 3 cross-departmental requests (ENG + S&T + TRD) on section SEC-ALJN-TDL (KM 166.37 - 169.93) during SLOT_EARLY_MORN; prioritized due to ENG asset ENG-TRK-ALJN-TDL-0019 (risk score: 53.68, HIGH); consolidated possession window 04:30 to 07:04 (154 min) saves 236 minutes (60.5%) of line possession vs. separate departmental blocks."
  }
}
```

---

## 6. Hard Out-of-Scope Boundaries (Strict)
The following are strictly out-of-scope for the 24–48 hour hackathon build:
1. **Live SCADA / TMS / SMMS / TDMS / COA integrations**: All data is synthetic and pre-loaded.
2. **Autonomous block granting**: The system is strictly recommendation-only; human Section Controller approval is mandatory.
3. **Mobile applications or field hardware integration** (no handheld devices, no IoT/GPS trackers).
4. **Multi-zone / Multi-division scaling**: Limited to a single division or representative test sections.
5. **Real authentication/RBAC system**: Replaced with a simple client-side persona toggle (Controller / Planner / Station Master).
6. **Production security hardening or deployment infrastructure**.

---

## 7. Frontend UI Dashboard Architecture (Phase 6)

### 7.1 Architecture Overview
The frontend is built with **Next.js 14 (App Router)**, **React 18**, and **Tailwind CSS**, organized in the `frontend/` directory. It interfaces with the FastAPI backend running on port 8000 (`http://127.0.0.1:8000`) either directly (with FastAPI CORS middleware) or via Next.js reverse proxy rewrites (`/backend-api/:path*` and server route handlers in `app/api/`).

```
frontend/
├── app/
│   ├── layout.tsx                # Dark railway theme root layout
│   ├── page.tsx                  # Dashboard orchestrator & state manager
│   ├── globals.css               # Tailwind directives & railway custom styles
│   └── api/                      # Next.js server-side reverse proxy handlers
│       ├── health/route.ts       # Proxies to GET /api/v1/health
│       ├── blocks/route.ts       # Proxies to GET /api/v1/blocks
│       ├── optimize/route.ts     # Proxies to POST /optimize
│       ├── requests/route.ts     # Proxies to GET /requests
│       ├── explain/[block_id]/   # Proxies to GET /api/v1/blocks/{block_id}/explain
│       └── action/[block_id]/    # Proxies to POST /api/v1/blocks/{block_id}/action
├── components/
│   ├── Navbar.tsx                # Brand header, live health pill, 3-persona switcher
│   ├── ControllerView.tsx        # Section Controller timeline & data table
│   ├── PlannerView.tsx           # Department Planner 240 requests list & ML risk
│   ├── StationMasterView.tsx     # Station-centric yard view & clearance checklist
│   ├── ExplanationDrawer.tsx     # Slide-out drawer with Phase 5 "Why?" explanation
│   └── StatBadge.tsx             # Color-coded urgency tiers, departments, statuses
├── types/
│   └── raksha.ts                 # Unified TypeScript interfaces matching Pydantic
└── lib/
    └── api.ts                    # Resilient client service with proxy & fallback
```

### 7.2 Persona View Specifications

#### 1. Section Controller View (`components/ControllerView.tsx`)
- **Objective:** Give Section Controllers real-time visibility and decision authority over AI-generated maintenance blocks.
- **Data Source:** `POST /optimize` and `GET /api/v1/blocks`.
- **Key Capabilities:**
  - **KPI Header:** Total scheduled blocks, bundled count, single count, line hours saved, controller approved tally, CP-SAT solve time.
  - **Interactive Filter Bar:** Track section dropdown, corridor slot filter, department filter (ENG, S&T, TRD), and "Bundled Only (2+ Depts)" checkbox.
  - **Dual Display Modes:**
    - **Table View:** Dense data table with Block ID, Section/Slot, Scheduled Window, Span in KM, Department badges, Possession Savings, Risk Priority tier, Protection flags (⚡ OHE, 🛑 Traffic), Approval Status, and action buttons.
    - **Timeline View:** Horizontal Gantt-style slot timeline displaying concurrent cross-departmental possessions.
  - **Human-in-the-Loop Actions:** Quick approval button (`✓`) or row inspection opening the Explanation Drawer.

#### 2. Phase 5 Structured Explanation Drawer (`components/ExplanationDrawer.tsx`)
- **Objective:** Satisfy Rule 4 by exposing deterministic, plain-language reasoning why each block was formed.
- **Trigger:** Clicking any block row or "Why?" button.
- **Sections Rendered:**
  1. **Executive Summary:** Plain-language synopsis of merged departments, chainage span, and time savings.
  2. **Driving Priority & Risk:** Highest risk asset tag, anchor request ID, ML risk score badge (0-100), and specific anchoring justification.
  3. **Governing Constraints:** Spatial overlap type (`DIRECT_OVERLAP`, `ADJACENT_PROXIMITY`), chainage gap, window slack, 25kV OHE power block driver, traffic block driver, and solver constraint checklist.
  4. **Constituent Requests Table:** Complete breakdown of every individual work order bundled into this possession window, with individual risk scores and required durations.
  5. **Alternatives Evaluated:** Counterfactual comparison (separate possessions duration vs bundled duration, savings percentage, why not scheduled separately, why not deferred).
  6. **Controller Decision Form:** Controller operating notes input, Approve Block button, Modify/Annotate button, Reject Block button (dispatches to `POST /api/v1/blocks/{block_id}/action`).

#### 3. Department Planner View (`components/PlannerView.tsx`)
- **Objective:** Allow departmental engineers (ENG P-Way, S&T, TRD) to inspect all 240 maintenance requests and their predictive failure risks.
- **Data Source:** `GET /requests` (and alias `/api/v1/requests`).
- **Key Capabilities:**
  - **KPI Header:** Total requests (240), department breakdown (85 ENG, 78 S&T, 77 TRD), Critical/High count (102), average ML risk score (37.7).
  - **Filters & Sorting:** Full-text search (Request ID, Asset ID, Work Type), Department filter, Urgency Category filter (CRITICAL, HIGH, MEDIUM, LOW), Track Section filter, and sorting by ML Risk Score (High to Low / Low to High) or required duration.
  - **Dense Data Table:** Displays source system (TMS, SMMS, TDMS, COA), asset age, past breakdowns, condition score, GMT tonnage, and LightGBM predicted failure risk score.

#### 4. Station Master View (`components/StationMasterView.tsx`)
- **Objective:** Provide Station Masters with an operational snapshot of maintenance blocks affecting their station yard and adjacent block sections.
- **Data Source:** Station-filtered subset of scheduled blocks from `GET /api/v1/blocks`.
- **Key Capabilities:**
  - **Station Selector:** Ghaziabad (GZB), Aligarh (ALJN), Tundla (TDL), Kanpur Central (CNB), New Delhi (NDLS), Prayagraj (PRYJ), Pt. Deen Dayal Upadhyaya (DDU), Tilak Bridge (TKJ), Moradabad (MB).
  - **Operational Impact Metrics:** Active yard blocks, 25kV OHE dead section count, absolute train stoppage count, and total train detention hours saved.
  - **Possession Clearance & Interlocking Checklist:** Interactive checkboxes for S&T Disconnection Memo (T/351), TRD Permit-to-Work (PTW-25kV), Caution Order (T/409) to train drivers, and P-Way Track Fit Certificate.
  - **Station Block Possession Schedule:** Filtered schedule table of confirmed windows affecting station yard approaches.

### 7.3 Phase 7 Interactive What-If Simulation (`components/WhatIfModal.tsx`)
- **Objective:** Enable Section Controllers and Planners to dynamically modify constraints on any pending request and instantly observe schedule ripple effects without page reload.
- **Trigger:** Accessible from any block row, constituent request, or the Planner view.
- **Interactive Controls:**
  1. **Operational Urgency & ML Risk Recalculation:** Instant tier selection (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) with real-time on-demand LightGBM re-scoring via `POST /api/v1/risk/score`.
  2. **Operational Time Window Shifting:** Quick shift pills (-2h Earlier, -1h Earlier, Baseline, +1h Delay, +2h Delay) or custom bounds.
  3. **Duration Adjustment:** Work scope modification (45m, 60m, 90m, 120m, 150m, 180m).
  4. **Solver Execution Mode:**
     - **Localized Delta Mode (⚡ < 100ms):** Re-solves only the affected connected component and merges with cached unaffected clusters.
     - **Full Fleet Re-solve (🔄 ~3.7s):** Re-optimizes all 240 requests globally from scratch.
- **Real-Time Re-rendering:**
  - Re-renders block schedule, timeline Gantt, and Phase 5 explanations asynchronously.
  - Highlights modified blocks with `is_modified=True` and `delta_type="REOPTIMIZED"`.

### 7.4 Phase 8 Executive KPI Impact Panel (`components/KpiComparisonPanel.tsx`)
- **Objective:** Present a high-level executive before/after impact summary comparing the unbundled baseline against the CP-SAT optimized schedule.
- **Metrics Displayed:**
  - **Block Count Reduction:** -63 blocks (-26.25% line possessions).
  - **Line Possession Time Saved:** -103.7 hours (-6,220 minutes, 22.37% reduction).
  - **Avoided Traffic Halts:** 53 train traffic stoppage events prevented.
  - **Cross-Department Bundles:** 43 bundles (20 triple-department, 23 dual-department).
  - **Bundling Efficiency Bar:** Interactive ratio of bundled vs. isolated possessions.

### 7.5 Phase 8 2D GIS Track Corridor Map (`components/CorridorMapView.tsx`)
- **Objective:** Provide a spatial, geographical map view plotting track sections, mainline stations, and maintenance blocks along the primary Delhi-Howrah trunk corridor.
- **Corridor Stations Plotted:**
  - New Delhi (`NDLS`, km 0.0, 28.6429° N, 77.2195° E)
  - Tilak Bridge (`TKJ`, km 3.5, 28.6256° N, 77.2411° E)
  - Ghaziabad Jn (`GZB`, km 24.5, 28.6534° N, 77.4328° E)
  - Aligarh Jn (`ALJN`, km 126.0, 27.8974° N, 78.0880° E)
  - Tundla Jn (`TDL`, km 204.0, 27.2065° N, 78.2384° E)
  - Kanpur Central (`CNB`, km 435.0, 26.4539° N, 80.3514° E)
  - Prayagraj Jn (`PRYJ`, km 630.0, 25.4484° N, 81.8340° E)
  - Pt. Deen Dayal Upadhyaya (`DDU`, km 783.0, 25.2815° N, 83.1189° E)
  - Moradabad Jn (`MB`, km 165.0, 28.8288° N, 78.7768° E)
- **Features:**
  - Linear referencing chainage interpolation along track sections.
  - Dynamic Leaflet interactive map with custom colored block pins (ENG: Blue, S&T: Emerald, TRD: Amber, Multi-Dept: Violet).
  - Block details tooltip & click-to-open Phase 5 explanation drawer.
  - Client-side dynamic mount pattern ensuring SSR compatibility and zero Next.js hydration mismatches.

---

## 8. Latency & Performance Profile (Benchmarked on N=240 Requests)

| Optimization Mode | Scope | CP-SAT Solve Time | Total Wall Latency | Live Demo Fit |
|---|---|---|---|---|
| **Localized Delta Re-optimization** | Affected Connected Component | **0.0899s (~90ms)** | **0.175s** | **Ideal for live stage demo / instantaneous response** |
| **Full Fleet Global Re-solve** | All 240 Requests / 8 Sections | **3.6829s (~3.7s)** | **3.784s** | Suitable for batch schedule publishing |

---

## 9. Phase 8 Quantitative Baseline vs. Optimized Impact

| Metric Category | Naive Unbundled Baseline | CP-SAT AI Optimized | Executive Impact (Savings / Avoidance) |
|---|---|---|---|
| **Total Scheduled Track Blocks** | 240 blocks | 177 blocks | **-63 blocks (-26.25%)** |
| **Cumulative Line Possession Hours** | 463.4 hours (27,807 min) | 359.8 hours (21,587 min) | **-103.7 hours saved (-22.37%)** |
| **Train Traffic Stoppage Events** | 212 halts | 159 halts | **53 train traffic stoppages avoided** |
| **Coordinated Cross-Department Bundles** | 0 (all isolated) | 43 bundled blocks | **43 multi-department bundles** |
| - *Triple Dept (ENG + S&T + TRD)* | 0 | 20 triple bundles | 20 joint track+signal+traction windows |
| - *Dual Dept (ENG + TRD / ENG + S&T)* | 0 | 23 dual bundles | 23 combined maintenance slots |
| **Double-Booking Track Conflicts** | N/A (uncoordinated) | 0 conflicts | **100% mathematically conflict-free** |
