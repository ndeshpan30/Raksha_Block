# Product Requirements Document: RAKSHA-BLOCK
**Problem Statement:** SIH26027 — AI-Powered Railway Maintenance Block Planning
**Document Owner:** Product
**Scope:** 24–48 Hour Hackathon MVP

---

## 1. Problem Statement & Impact

Indian Railways maintenance blocks are requested independently by three departments — **Engineering (P-Way)**, **Signal & Telecom (S&T)**, and **Traction Distribution (TRD)** — using disconnected legacy systems (TMS, SMMS, TDMS, COA). Because no shared view of the track occupancy calendar exists:

- **Wasted block hours:** Overlapping or redundant block requests on the same section get sanctioned separately instead of bundled, multiplying total possession time.
- **Asset downtime inflation:** A single track section may be blocked 3 separate times in a month for 3 departments' independent work, when one coordinated block could suffice.
- **Traffic disruption:** Section Controllers grant blocks manually against a traffic timetable with no risk-weighted prioritization — high-risk assets and low-risk routine work compete for the same slots with equal footing.
- **No audit trail for "why":** Block sanctioning decisions are undocumented judgment calls, making post-hoc review and optimization impossible.

**Cost driver:** Every unbundled block = duplicated safety caution periods, duplicated traffic diversion overhead, and duplicated asset unavailability windows — all of which are avoidable through spatial and temporal coordination.

---

## 2. Proposed Solution & Value Proposition

RAKSHA-BLOCK ingests fragmented block requests from all three departments, geotags them onto a common track topology, and applies **cross-departmental spatial task bundling**: requests that fall within overlapping track sections and time windows are algorithmically merged into a single coordinated block proposal.

**Core value proposition:** Replace manual, siloed block granting with a mathematically optimized schedule that:
- Minimizes total block hours for a given set of maintenance demands.
- Risk-ranks which requests are urgent vs. deferrable using ML.
- Explains every recommendation in human-readable terms for controller trust and adoption.
- Lets planners simulate "what-if" changes and see the schedule re-optimize instantly.

---

## 3. Target Personas

| Persona | Role | Primary Need |
|---|---|---|
| **Section Controller** | Grants/denies blocks against live traffic constraints | A single prioritized, conflict-free block plan per section, with justification |
| **Station Master** | Executes block implementation at the ground level | Clear, unambiguous block windows and affected assets per station |
| **Department Planner** (Engineering / S&T / TRD) | Submits maintenance requests | Confidence that requests get fairly bundled/scheduled, not silently deprioritized |

---

## 4. User Stories

- As a **Section Controller**, I want to see all pending block requests for my section on one timeline, so that I can grant blocks without cross-checking three separate systems.
- As a **Section Controller**, I want the system to recommend a bundled block plan, so that I minimize total line possession time.
- As a **Department Planner**, I want to submit a maintenance request with location, urgency, and duration, so that it enters the unified scheduling pool.
- As a **Department Planner**, I want to see why my request was scheduled at a given time (or deferred), so that I trust the system isn't arbitrarily deprioritizing my work.
- As a **Station Master**, I want a simplified view of confirmed block windows for my station, so that I can coordinate ground staff without ambiguity.
- As a **Section Controller**, I want to tweak a constraint (e.g., "delay this block by 2 hours") and instantly see the ripple effect on the rest of the schedule, so that I can resolve conflicts without re-running the whole planning process manually.
- As a **Department Planner**, I want to see a risk score attached to each asset/request, so that I understand why high-risk items are prioritized over routine ones.

---

## 5. Core MVP Features (Strict Priority Order)

**P0 — Must Ship**
1. **Unified Data Ingestion (Synthetic Datasets)** — CSV/JSON loaders that normalize synthetic TMS, SMMS, TDMS, and COA-style request records into one internal schema (section, chainage/location, department, requested window, work type, asset ID).
2. **ML Priority/Risk Scoring** — LightGBM/XGBoost model trained on synthetic asset-failure-probability features to output a risk score per request, used as a scheduling priority weight.
3. **CP-SAT/OR-Tools Scheduling Optimizer** — Constraint programming model that takes all pending requests + risk scores + traffic window constraints, and outputs the minimum set of non-overlapping, spatially bundled blocks satisfying all hard constraints (no double-booking a section, respecting safety caution periods).

**P1 — Must Ship (Differentiators)**
4. **Explainable Recommendation Panel ("Why this block?")** — For each proposed block, surface the contributing requests, their risk scores, and the specific constraint(s) that drove the bundling/timing decision, in plain language.
5. **Interactive "What-If" Scenario Simulator** — UI control to adjust a parameter (shift a time window, mark a request urgent, remove a request) and re-run the optimizer in near-real-time to show the updated schedule and resolved/introduced conflicts.

**P2 — Nice to Have (only if time permits after P0/P1 are demo-stable)**
- Baseline-vs-optimized KPI comparison dashboard (block hours saved, asset downtime reduced).
- Leaflet map view of block locations along the track network.

---

## 6. Out of Scope / Non-Goals

Explicitly excluded from this MVP to protect the 24–48 hour build window:

- **No live SCADA, TMS, SMMS, TDMS, or COA API integration** — all data is synthetic, static, and pre-loaded.
- **No autonomous block granting** — the system only *recommends*; a human Section Controller must approve every block. No human-in-the-loop bypass.
- **No mobile app or field-hardware integration** (handheld devices, IoT sensors, GPS trackers).
- **No multi-year roadmap features**: no fleet-wide national rollout planning, no real-time train location tracking, no predictive maintenance beyond the MVP's risk score.
- **No user authentication/role management system beyond a basic persona switcher** (Controller / Planner / Station Master views can be hardcoded toggle, not a full auth system).
- **No multi-zone/multi-division scaling** — MVP scope is a single division or a representative set of sections.
- **No production-grade data validation, security hardening, or deployment infrastructure.**

---

## 7. Technical Architecture & Stack

**Backend**
- **Python + FastAPI** — REST API layer exposing endpoints for: data ingestion, risk scoring inference, optimizer trigger, what-if re-optimization, and explanation retrieval.

**Optimization & ML**
- **Google OR-Tools (CP-SAT)** — core scheduling engine; model block requests as tasks with resource (section) constraints, time windows, and precedence/exclusion rules.
- **LightGBM / XGBoost** — tabular risk/priority scoring model, trained offline on synthetic asset failure data; served via a lightweight inference function called by FastAPI.

**Database**
- **Supabase or PostgreSQL with LRS (Linear Referencing System) spatial indexing** — stores track topology (sections, chainage ranges), block requests, and optimizer outputs; LRS enables spatial overlap queries (does request A's chainage range intersect request B's?) needed for bundling logic.

**Frontend**
- **Next.js + React + Tailwind CSS** — controller/planner dashboard, what-if simulator UI, explanation panel.
- **Leaflet** — visual network map rendering block locations along the track (P2, if time allows).

**Suggested Data Flow**
1. Synthetic request data ingested → normalized → stored in Postgres/Supabase.
2. Risk scoring model scores each pending request → priority weight written back to DB.
3. FastAPI endpoint triggers CP-SAT optimizer with current requests + weights + constraints → returns block plan + per-block justification metadata.
4. Frontend renders plan + explanation panel; what-if UI edits trigger a re-call to the optimizer endpoint with modified constraints.

---

## 8. Judging Criteria Alignment / Pitch Strategy

**Core narrative:** *"We replaced manual, siloed block-granting judgment calls with a mathematically optimal, explainable scheduling engine — and we built it without needing access to restricted government systems."*

**Positioning points to hit in the pitch:**
- **Manual → Mathematical:** Explicitly contrast today's process (each department requests blocks independently, controllers approve by intuition) against RAKSHA-BLOCK's constraint-programming approach that guarantees the minimum number of blocks for a given demand set — this is a provable optimization claim, not a heuristic.
- **Synthetic data as a strength, not a limitation:** Proactively state that TMS/SMMS/TDMS/COA access is restricted, and that the team engineered realistic synthetic datasets that mirror real schema/scale — framing this as responsible scoping rather than an excuse. Judges reward teams who understand real-world integration constraints.
- **Explainability as trust infrastructure:** Emphasize that in a safety-critical domain like railway block granting, a black-box recommendation is unusable — the "Why this block?" panel is what makes the system deployable, not just clever.
- **Human-in-the-loop, not autonomous:** Reassure judges (especially domain experts on the panel) that the system augments Controller decision-making rather than replacing safety authority — this directly counters the most likely judge pushback.
- **Show the KPI delta live:** During the demo, load a baseline (unoptimized, siloed) schedule side-by-side with the RAKSHA-BLOCK optimized schedule and call out concrete numbers — **block hours saved**, **number of distinct blocks reduced**, **high-risk assets prioritized ahead of routine work**. A visual before/after is more persuasive to judges than a feature list.
- **Demo the what-if simulator live** — this is the single most convincing "wow" moment: ask the audience or a judge for a constraint change on the spot and show the schedule re-optimize in seconds.

