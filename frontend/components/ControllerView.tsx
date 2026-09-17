import React, { useState, useMemo, useEffect } from 'react';
import { BundledBlock, OptimizationPlan, BaselineComparison } from '@/types/raksha';
import { DeptBadge, UrgencyBadge, StatusBadge } from './StatBadge';
import { KpiComparisonPanel } from './KpiComparisonPanel';
import { CorridorMapView } from './CorridorMapView';
import { fetchBaselineComparison } from '@/lib/api';

interface ControllerViewProps {
  blocks: BundledBlock[];
  optimizationPlan: OptimizationPlan | null;
  loading: boolean;
  onSelectBlock: (block: BundledBlock) => void;
  onAction: (blockId: string, action: 'APPROVE' | 'REJECT' | 'MODIFY', notes?: string) => Promise<void>;
  onTriggerOptimize: () => void;
  modifiedRequestIds?: Set<string>;
  onResetSimulation?: () => void;
  onOpenWhatIfForBlock?: (block: BundledBlock) => void;
  lastSolveMetrics?: {
    solveTime: number;
    mode: string;
    affectedCount: number;
  } | null;
}

export const ControllerView: React.FC<ControllerViewProps> = ({
  blocks,
  optimizationPlan,
  loading,
  onSelectBlock,
  onAction,
  onTriggerOptimize,
  modifiedRequestIds,
  onResetSimulation,
  onOpenWhatIfForBlock,
  lastSolveMetrics,
}) => {
  const [selectedSection, setSelectedSection] = useState<string>('ALL');
  const [selectedSlot, setSelectedSlot] = useState<string>('ALL');
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [bundledOnly, setBundledOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'table' | 'timeline' | 'map'>('table');
  const [isKpiOpen, setIsKpiOpen] = useState<boolean>(true);
  const [fetchedComparison, setFetchedComparison] = useState<BaselineComparison | null>(null);

  useEffect(() => {
    if (optimizationPlan?.baseline_comparison) {
      setFetchedComparison(optimizationPlan.baseline_comparison);
    } else {
      fetchBaselineComparison().then((data) => {
        if (data) setFetchedComparison(data);
      });
    }
  }, [optimizationPlan]);

  // Extract unique sections and slots
  const sectionList = useMemo(() => {
    const set = new Set<string>();
    blocks.forEach((b) => set.add(b.section_id));
    return Array.from(set).sort();
  }, [blocks]);

  const slotList = useMemo(() => {
    const set = new Set<string>();
    blocks.forEach((b) => set.add(b.corridor_slot));
    return Array.from(set).sort();
  }, [blocks]);

  // Filtered blocks
  const filteredBlocks = useMemo(() => {
    return blocks.filter((b) => {
      if (selectedSection !== 'ALL' && b.section_id !== selectedSection) return false;
      if (selectedSlot !== 'ALL' && b.corridor_slot !== selectedSlot) return false;
      if (selectedDept !== 'ALL' && !b.departments_involved.includes(selectedDept)) return false;
      if (bundledOnly && b.bundled_request_ids.length <= 1) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = b.block_id.toLowerCase().includes(q);
        const matchSec = b.section_id.toLowerCase().includes(q);
        const matchReq = b.bundled_request_ids.some((r) => r.toLowerCase().includes(q));
        if (!matchId && !matchSec && !matchReq) return false;
      }
      return true;
    });
  }, [blocks, selectedSection, selectedSlot, selectedDept, bundledOnly, searchQuery]);

  // Aggregate metrics
  const metrics = useMemo(() => {
    const total = blocks.length;
    const bundled = blocks.filter((b) => b.bundled_request_ids.length > 1).length;
    const single = total - bundled;
    const totalSavingsMin = blocks.reduce((acc, b) => acc + (b.savings_minutes || 0), 0);
    const approvedCount = blocks.filter((b) => (b.approval_status || '').includes('APPROVED')).length;

    let highestRisk = 0;
    blocks.forEach((b) => {
      const explRisk = b.explanation_detail?.driving_priority?.highest_risk_score || 0;
      if (explRisk > highestRisk) highestRisk = explRisk;
    });

    return {
      total,
      bundled,
      single,
      hoursSaved: (totalSavingsMin / 60).toFixed(1),
      savingsMin: totalSavingsMin,
      approvedCount,
      highestRisk: highestRisk.toFixed(1),
    };
  }, [blocks]);

  return (
    <div className="space-y-6">
      {/* Phase 7 What-If Simulation Active Banner */}
      {modifiedRequestIds && modifiedRequestIds.size > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 text-xs shadow-lg animate-in fade-in">
          <div className="flex items-center space-x-3">
            <span className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 text-lg font-bold">
              ⚡
            </span>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-white text-sm">Interactive What-If Simulation Active</span>
                <span className="px-2 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                  {modifiedRequestIds.size} MODIFIED REQUEST(S)
                </span>
                <span className="px-2 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                  {optimizationPlan?.reoptimization_mode || 'LOCALIZED_DELTA'}
                </span>
              </div>
              <p className="text-slate-300 text-[11px] mt-0.5">
                Block schedule dynamically re-solved with CP-SAT. Visual delta indicators highlight affected track possession windows.
                {optimizationPlan?.solve_time_seconds !== undefined && (
                  <span className="ml-2 font-mono text-emerald-400 font-bold">
                    [Solve Latency: {(optimizationPlan.solve_time_seconds * 1000).toFixed(0)}ms ({optimizationPlan.solve_time_seconds.toFixed(3)}s)]
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onResetSimulation}
            className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-bold border border-slate-700 shadow transition flex items-center space-x-1.5 text-xs"
          >
            <span>🔄 Revert to Baseline Schedule</span>
          </button>
        </div>
      )}

      {/* Top Banner & KPI Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Scheduled Blocks</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-white">{metrics.total}</span>
            <span className="text-xs text-blue-400 font-medium">{metrics.bundled} Bundled</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Single Blocks</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-slate-300">{metrics.single}</span>
            <span className="text-xs text-slate-400">Isolated</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Possession Saved</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-emerald-400">{metrics.hoursSaved} hrs</span>
            <span className="text-xs text-emerald-400/80">({metrics.savingsMin} m)</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Controller Approved</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-blue-400">{metrics.approvedCount}</span>
            <span className="text-xs text-slate-400">/ {metrics.total}</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">CP-SAT Solver</span>
            <span className="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
              {optimizationPlan?.status || 'OPTIMAL'}
            </span>
          </div>
          <div className="text-xs text-slate-400 mt-1 flex justify-between items-center">
            <span>Solve Time:</span>
            <span className="font-mono text-slate-200 font-semibold">
              {optimizationPlan?.solve_time_seconds !== undefined
                ? `${optimizationPlan.solve_time_seconds.toFixed(2)}s`
                : '8.12s'}
            </span>
          </div>
          <button
            onClick={onTriggerOptimize}
            disabled={loading}
            className="w-full mt-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow transition disabled:opacity-50"
          >
            {loading ? 'Optimizing...' : '⚡ Re-run CP-SAT'}
          </button>
        </div>
      </div>

      {/* Phase 8 Executive KPI Impact: Baseline vs. CP-SAT Optimized */}
      {(optimizationPlan?.baseline_comparison || fetchedComparison) && (
        <KpiComparisonPanel
          comparison={optimizationPlan?.baseline_comparison || fetchedComparison}
          solveTimeSeconds={optimizationPlan?.solve_time_seconds}
          isOpen={isKpiOpen}
          onToggle={() => setIsKpiOpen(!isKpiOpen)}
        />
      )}

      {/* Filter & Control Bar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {/* Search Input */}
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Block ID, Section, Request..."
                className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg pl-8 pr-3 py-1.5 w-60 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <svg
                className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>

            {/* Track Section Selector */}
            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Sections ({blocks.length})</option>
              {sectionList.map((sec) => (
                <option key={sec} value={sec}>
                  {sec}
                </option>
              ))}
            </select>

            {/* Corridor Slot Selector */}
            <select
              value={selectedSlot}
              onChange={(e) => setSelectedSlot(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Corridor Slots</option>
              {slotList.map((slot) => (
                <option key={slot} value={slot}>
                  {slot}
                </option>
              ))}
            </select>

            {/* Department Filter */}
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Departments</option>
              <option value="ENG">ENG (P-Way)</option>
              <option value="S&T">S&T (Signal & Telecom)</option>
              <option value="TRD">TRD (Traction Distribution)</option>
            </select>

            {/* Bundled-only Checkbox */}
            <label className="flex items-center space-x-1.5 cursor-pointer text-slate-300 font-medium">
              <input
                type="checkbox"
                checked={bundledOnly}
                onChange={(e) => setBundledOnly(e.target.checked)}
                className="rounded border-slate-700 text-blue-600 focus:ring-0"
              />
              <span>Bundled Only (2+ Depts)</span>
            </label>
          </div>

          {/* Table vs Timeline vs GIS Corridor Map Toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 space-x-1">
            <button
              onClick={() => setActiveTab('table')}
              className={`px-3 py-1 rounded text-xs font-semibold transition ${
                activeTab === 'table' ? 'bg-slate-800 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Table View ({filteredBlocks.length})
            </button>
            <button
              onClick={() => setActiveTab('timeline')}
              className={`px-3 py-1 rounded text-xs font-semibold transition ${
                activeTab === 'timeline' ? 'bg-slate-800 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Timeline View
            </button>
            <button
              onClick={() => setActiveTab('map')}
              className={`px-3 py-1 rounded text-xs font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'map'
                  ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40 shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>🗺️</span>
              <span>Corridor Map (GIS)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="font-semibold text-white">Loading CP-SAT Optimization Schedule...</p>
          <p className="text-xs text-slate-400 mt-1">Evaluating cross-department spatio-temporal bundles</p>
        </div>
      ) : activeTab === 'map' ? (
        /* Phase 8 Leaflet 2D GIS Track Corridor Map */
        <CorridorMapView
          blocks={filteredBlocks}
          selectedBlock={null}
          onSelectBlock={onSelectBlock}
          filterSection={selectedSection}
        />
      ) : activeTab === 'timeline' ? (
        /* Timeline View */
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <span>Section Maintenance Gantt & Corridor Windows</span>
              <span className="text-xs font-normal text-slate-400">({filteredBlocks.length} blocks rendered)</span>
            </h3>
            <div className="flex items-center space-x-3 text-xs">
              <span className="flex items-center space-x-1 text-blue-400">
                <span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block" />
                <span>ENG</span>
              </span>
              <span className="flex items-center space-x-1 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" />
                <span>S&T</span>
              </span>
              <span className="flex items-center space-x-1 text-amber-400">
                <span className="w-2.5 h-2.5 rounded bg-amber-500 inline-block" />
                <span>TRD</span>
              </span>
            </div>
          </div>

          <div className="space-y-2.5">
            {filteredBlocks.map((block) => {
              const startStr = block.scheduled_start?.slice(11, 16) || '00:00';
              const endStr = block.scheduled_end?.slice(11, 16) || '00:00';
              const isBundled = block.bundled_request_ids.length > 1;
              const isDelta =
                Boolean(block.is_modified) ||
                block.bundled_request_ids.some((r) => modifiedRequestIds?.has(r));

              return (
                <div
                  key={block.block_id}
                  onClick={() => onSelectBlock(block)}
                  className={`p-3 rounded-lg cursor-pointer transition flex items-center justify-between border ${
                    isDelta
                      ? 'border-amber-500/70 bg-amber-500/10 shadow-[0_0_15px_rgba(245,158,11,0.2)]'
                      : 'bg-slate-950/80 hover:bg-slate-800/80 border-slate-800 hover:border-blue-500/50'
                  }`}
                >
                  <div className="w-48">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs font-bold text-white">{block.block_id}</span>
                      {isDelta && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/30 text-amber-300 border border-amber-500/50 font-bold animate-pulse">
                          ⚡ DELTA
                        </span>
                      )}
                      {isBundled && !isDelta && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                          Bundled
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {block.section_id} | KM {typeof block.start_km === 'number' ? block.start_km.toFixed(1) : block.start_km}-{typeof block.end_km === 'number' ? block.end_km.toFixed(1) : block.end_km}
                    </p>
                  </div>

                  {/* Horizontal Timeline Bar */}
                  <div className="flex-1 mx-4">
                    <div className="h-6 bg-slate-900 rounded-md overflow-hidden flex items-center p-1 border border-slate-800 relative">
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden flex">
                        {block.departments_involved.map((dept, i) => (
                          <div
                            key={i}
                            className={`h-full ${
                              dept === 'ENG' ? 'bg-blue-500' : dept === 'S&T' ? 'bg-emerald-500' : 'bg-amber-500'
                            }`}
                            style={{ width: `${100 / block.departments_involved.length}%` }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Time Window & Action */}
                  <div className="flex items-center space-x-3 text-xs">
                    <div className="text-right">
                      <span className="font-bold text-white block">
                        {startStr} - {endStr}
                      </span>
                      <span className="text-[11px] text-slate-400">{block.total_duration_minutes} min</span>
                    </div>

                    {block.savings_minutes > 0 && (
                      <span className="text-emerald-400 font-bold text-xs bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        +{block.savings_minutes}m saved
                      </span>
                    )}

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectBlock(block);
                      }}
                      className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[11px] font-semibold transition"
                    >
                      Why?
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Table View */
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 font-semibold">Block ID</th>
                  <th className="px-4 py-3 font-semibold">Section & Slot</th>
                  <th className="px-4 py-3 font-semibold">Scheduled Window</th>
                  <th className="px-4 py-3 font-semibold">Span (KM)</th>
                  <th className="px-4 py-3 font-semibold">Departments</th>
                  <th className="px-4 py-3 font-semibold">Savings</th>
                  <th className="px-4 py-3 font-semibold">Risk Priority</th>
                  <th className="px-4 py-3 font-semibold">Protection</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {filteredBlocks.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-slate-400">
                      No maintenance blocks match the active filters.
                    </td>
                  </tr>
                ) : (
                  filteredBlocks.map((block) => {
                    const startStr = block.scheduled_start?.slice(11, 16) || '00:00';
                    const endStr = block.scheduled_end?.slice(11, 16) || '00:00';
                    const isBundled = block.bundled_request_ids.length > 1;
                    const isDelta =
                      Boolean(block.is_modified) ||
                      block.bundled_request_ids.some((r) => modifiedRequestIds?.has(r));
                    const highestRisk =
                      block.explanation_detail?.driving_priority?.highest_risk_score ||
                      (block.constituent_requests?.[0]?.risk_score ?? 0);
                    const riskTier =
                      block.explanation_detail?.driving_priority?.risk_tier ||
                      (highestRisk >= 75 ? 'CRITICAL' : highestRisk >= 50 ? 'HIGH' : highestRisk >= 25 ? 'MEDIUM' : 'LOW');

                    return (
                      <tr
                        key={block.block_id}
                        onClick={() => onSelectBlock(block)}
                        className={`cursor-pointer transition ${
                          isDelta
                            ? 'bg-amber-500/10 hover:bg-amber-500/20 border-l-4 border-l-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
                            : 'hover:bg-slate-800/60'
                        }`}
                      >
                        {/* Block ID */}
                        <td className="px-4 py-3">
                          <div className="flex items-center space-x-1.5">
                            <span className="font-mono font-bold text-white">{block.block_id}</span>
                            {isDelta && (
                              <span
                                className="px-1.5 py-0.2 rounded bg-amber-500/30 text-amber-300 border border-amber-500/50 text-[9px] font-bold animate-pulse"
                                title="Re-optimized by What-If Simulator"
                              >
                                ⚡ DELTA
                              </span>
                            )}
                            {isBundled && !isDelta && (
                              <span
                                className="w-2 h-2 rounded-full bg-indigo-400 inline-block"
                                title="Bundled cross-department block"
                              />
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400">
                            {block.bundled_request_ids.length} work orders
                          </span>
                        </td>

                        {/* Section & Slot */}
                        <td className="px-4 py-3">
                          <span className="font-medium text-slate-200 block">{block.section_id}</span>
                          <span className="text-[10px] text-slate-400">{block.corridor_slot}</span>
                        </td>

                        {/* Scheduled Window */}
                        <td className="px-4 py-3">
                          <span className="font-semibold text-white block">
                            {startStr} - {endStr}
                          </span>
                          <span className="text-[10px] text-slate-400">{block.total_duration_minutes} min duration</span>
                        </td>

                        {/* Span */}
                        <td className="px-4 py-3">
                          <span className="font-mono text-slate-200 block">
                            {typeof block.start_km === 'number' ? block.start_km.toFixed(2) : block.start_km} - {typeof block.end_km === 'number' ? block.end_km.toFixed(2) : block.end_km}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {typeof block.end_km === 'number' && typeof block.start_km === 'number'
                              ? `${(block.end_km - block.start_km).toFixed(2)} km`
                              : '-'}
                          </span>
                        </td>

                        {/* Departments */}
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {block.departments_involved.map((dept) => (
                              <DeptBadge key={dept} dept={dept} />
                            ))}
                          </div>
                        </td>

                        {/* Savings */}
                        <td className="px-4 py-3">
                          {block.savings_minutes > 0 ? (
                            <div>
                              <span className="font-bold text-emerald-400">+{block.savings_minutes} min</span>
                              <span className="text-[10px] text-emerald-400/80 block">
                                {typeof block.explanation_detail?.alternatives_considered?.possession_savings_pct === 'number'
                                  ? `${block.explanation_detail.alternatives_considered.possession_savings_pct.toFixed(0)}% saved`
                                  : 'Bundled'}
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-400 font-mono text-[11px]">0 min</span>
                          )}
                        </td>

                        {/* Risk Priority */}
                        <td className="px-4 py-3">
                          <UrgencyBadge tier={riskTier as any} score={highestRisk} />
                        </td>

                        {/* Protection */}
                        <td className="px-4 py-3">
                          <div className="flex items-center space-x-1 text-[11px]">
                            {block.power_block_granted && (
                              <span
                                className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30"
                                title="25kV OHE Isolation Granted"
                              >
                                ⚡ OHE
                              </span>
                            )}
                            {block.traffic_block_granted && (
                              <span
                                className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 font-bold border border-red-500/30"
                                title="Train Traffic Block Granted"
                              >
                                🛑 TRF
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          <StatusBadge status={block.approval_status || 'PROPOSED'} />
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end space-x-1.5">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpenWhatIfForBlock?.(block);
                              }}
                              title="What-If Simulation on this block"
                              className="px-2 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 hover:text-white rounded text-xs font-semibold border border-amber-500/40 transition"
                            >
                              ⚡
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectBlock(block);
                              }}
                              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-blue-400 hover:text-blue-300 rounded text-xs font-semibold border border-slate-700 transition"
                            >
                              Why?
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onAction(block.block_id, 'APPROVE');
                              }}
                              title="Approve Block"
                              className="px-2 py-1 bg-emerald-600/80 hover:bg-emerald-600 text-white rounded text-xs font-semibold transition"
                            >
                              ✓
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
