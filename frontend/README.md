# RAKSHA-BLOCK Frontend UI Dashboard (Phase 6)
**SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination**

Minimal Next.js + React + Tailwind CSS dashboard with 3 hardcoded persona views:
1. **Section Controller**: Block schedule timeline & table, CP-SAT optimizer trigger, KPI cards, human-in-the-loop approval actions.
2. **Department Planner**: 240 maintenance requests list from legacy systems (TMS, SMMS, TDMS, COA) with LightGBM operational failure risk scores (0-100), condition features, and department filters.
3. **Station Master**: Station-centric yard possession impact view, 25kV OHE power isolation alerts, absolute train traffic halt warnings, and interlocking clearance checklist.
4. **Structured "Why this block?" Explanation Drawer**: Slide-out drawer displaying Phase 5 structured explanations (plain-language summary, driving priority & failure risk, governing spatial/electrical constraints, constituent requests table, and counterfactual alternatives considered).

---

## 🚀 Getting Started

### 1. Ensure Backend is Running
The backend should be running on port 8000:
```bash
# In project root:
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Install Frontend Dependencies & Start Dev Server
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🏗️ Architecture & Component Hierarchy
```
frontend/
├── app/
│   ├── layout.tsx         # Root layout with dark railway theme
│   ├── page.tsx           # Main page orchestrating personas & state
│   ├── globals.css        # Tailwind CSS styles & railway theme variables
│   └── api/               # Next.js API route handlers proxying to FastAPI
│       ├── health/
│       ├── blocks/
│       ├── optimize/
│       ├── requests/
│       ├── explain/[block_id]/
│       └── action/[block_id]/
├── components/
│   ├── Navbar.tsx             # Brand header, health pill, persona toggle
│   ├── ControllerView.tsx     # Section Controller timeline & data table
│   ├── PlannerView.tsx        # Department Planner requests list & ML risk
│   ├── StationMasterView.tsx  # Station Master yard view & clearance checklist
│   ├── ExplanationDrawer.tsx  # Slide-out drawer with Phase 5 "Why?" explanation
│   └── StatBadge.tsx          # Urgency, department, and status badges
├── types/
│   └── raksha.ts          # Unified TypeScript interfaces
└── lib/
    └── api.ts             # Client API service interacting with FastAPI
```
