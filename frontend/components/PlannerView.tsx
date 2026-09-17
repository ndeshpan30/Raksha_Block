import React, { useState, useMemo } from 'react';
import { MaintenanceRequest } from '@/types/raksha';
import { DeptBadge, UrgencyBadge, StatusBadge } from './StatBadge';

interface PlannerViewProps {
  requests: MaintenanceRequest[];
  loading: boolean;
  onRefresh: () => void;
  onOpenWhatIf?: (req: MaintenanceRequest) => void;
  modifiedRequestIds?: Set<string>;
  onResetSimulation?: () => void;
  lastSolveMetrics?: {
    solveTime: number;
    mode: string;
    affectedCount: number;
  } | null;
}

export const PlannerView: React.FC<PlannerViewProps> = ({
  requests,
  loading,
  onRefresh,
  onOpenWhatIf,
  modifiedRequestIds,
  onResetSimulation,
  lastSolveMetrics,
}) => {
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [selectedUrgency, setSelectedUrgency] = useState<string>('ALL');
  const [selectedSection, setSelectedSection] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortBy, setSortBy] = useState<'risk_desc' | 'risk_asc' | 'duration' | 'window'>('risk_desc');

  // Unique sections
  const sectionList = useMemo(() => {
    const set = new Set<string>();
    requests.forEach((r) => set.add(r.section_id));
    return Array.from(set).sort();
  }, [requests]);

  // Filtered requests
  const filteredRequests = useMemo(() => {
    let result = requests.filter((r) => {
      if (selectedDept !== 'ALL' && r.department !== selectedDept) return false;
      if (selectedUrgency !== 'ALL' && (r.urgency_category || '').toUpperCase() !== selectedUrgency) return false;
      if (selectedSection !== 'ALL' && r.section_id !== selectedSection) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = r.request_id.toLowerCase().includes(q);
        const matchAsset = r.asset_id.toLowerCase().includes(q);
        const matchWork = r.work_type.toLowerCase().includes(q);
        const matchSec = r.section_id.toLowerCase().includes(q);
        if (!matchId && !matchAsset && !matchWork && !matchSec) return false;
      }
      return true;
    });

    result.sort((a, b) => {
      if (sortBy === 'risk_desc') {
        return (b.risk_score ?? 0) - (a.risk_score ?? 0);
      } else if (sortBy === 'risk_asc') {
        return (a.risk_score ?? 0) - (b.risk_score ?? 0);
      } else if (sortBy === 'duration') {
        return b.required_duration_minutes - a.required_duration_minutes;
      } else if (sortBy === 'window') {
        return (a.requested_window_start || '').localeCompare(b.requested_window_start || '');
      }
      return 0;
    });

    return result;
  }, [requests, selectedDept, selectedUrgency, selectedSection, searchQuery, sortBy]);

  // Aggregate stats
  const stats = useMemo(() => {
    const total = requests.length;
    const engCount = requests.filter((r) => r.department === 'ENG').length;
    const sntCount = requests.filter((r) => r.department === 'S&T').length;
    const trdCount = requests.filter((r) => r.department === 'TRD').length;
    const criticalCount = requests.filter((r) => (r.urgency_category || '').toUpperCase() === 'CRITICAL').length;
    const highCount = requests.filter((r) => (r.urgency_category || '').toUpperCase() === 'HIGH').length;

    const avgRisk =
      total > 0
        ? (requests.reduce((acc, r) => acc + (r.risk_score ?? 0), 0) / total).toFixed(1)
        : '0.0';

    return {
      total,
      engCount,
      sntCount,
      trdCount,
      criticalCount,
      highCount,
      avgRisk,
    };
  }, [requests]);

  return (
    <div className="space-y-6">
      {/* Active What-If Simulation Banner */}
      {modifiedRequestIds && modifiedRequestIds.size > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 text-xs shadow-lg animate-in fade-in">
          <div className="flex items-center space-x-3">
            <span className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 text-lg font-bold">
              ⚡
            </span>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-white text-sm">Active What-If Simulation</span>
                <span className="px-2 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                  {modifiedRequestIds.size} MODIFIED
                </span>
              </div>
              <p className="text-slate-300 text-[11px] mt-0.5">
                Constraints altered in memory. Schedule re-optimized with CP-SAT without page reload.
                {lastSolveMetrics && (
                  <span className="ml-2 font-mono text-emerald-400 font-bold">
                    [Solve Latency: {(lastSolveMetrics.solveTime * 1000).toFixed(0)}ms | Mode: {lastSolveMetrics.mode}]
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onResetSimulation}
            className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-bold border border-slate-700 shadow transition flex items-center space-x-1.5 text-xs"
          >
            <span>🔄 Revert to Baseline Requests</span>
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Total Requests</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-white">{stats.total}</span>
            <span className="text-xs text-slate-400 font-medium">Ingested</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Department Mix</span>
          <div className="flex items-center space-x-2 mt-1 text-xs">
            <span className="text-blue-400 font-bold">{stats.engCount} ENG</span>
            <span className="text-slate-500">|</span>
            <span className="text-emerald-400 font-bold">{stats.sntCount} S&T</span>
            <span className="text-slate-500">|</span>
            <span className="text-amber-400 font-bold">{stats.trdCount} TRD</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Critical / High Risk</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-red-400">{stats.criticalCount + stats.highCount}</span>
            <span className="text-xs text-red-400/80">({stats.criticalCount} Critical)</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Average ML Risk</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-amber-400">{stats.avgRisk}</span>
            <span className="text-xs text-slate-400">/ 100</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Legacy Sync</span>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="w-full mt-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold py-1.5 px-3 rounded-lg border border-slate-700 transition"
          >
            {loading ? 'Refreshing...' : '🔄 Sync TMS / SMMS / TDMS'}
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Request ID, Asset, Work Type..."
                className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg pl-8 pr-3 py-1.5 w-64 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
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

            {/* Department */}
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

            {/* Urgency */}
            <select
              value={selectedUrgency}
              onChange={(e) => setSelectedUrgency(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Urgencies</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>

            {/* Section */}
            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Sections ({sectionList.length})</option>
              {sectionList.map((sec) => (
                <option key={sec} value={sec}>
                  {sec}
                </option>
              ))}
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="risk_desc">Risk Score (High to Low)</option>
              <option value="risk_asc">Risk Score (Low to High)</option>
              <option value="duration">Required Duration (Longest)</option>
              <option value="window">Requested Start Time</option>
            </select>
          </div>
        </div>
      </div>

      {/* Requests Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 font-semibold">Request ID</th>
                <th className="px-4 py-3 font-semibold">Source</th>
                <th className="px-4 py-3 font-semibold">Dept & Work Type</th>
                <th className="px-4 py-3 font-semibold">Asset Details</th>
                <th className="px-4 py-3 font-semibold">Section & Chainage</th>
                <th className="px-4 py-3 font-semibold">Window & Duration</th>
                <th className="px-4 py-3 font-semibold">Risk Features</th>
                <th className="px-4 py-3 font-semibold">ML Risk Score</th>
                <th className="px-4 py-3 font-semibold">Blocks</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold text-right">What-If Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-slate-400">
                    No maintenance requests match the selected criteria.
                  </td>
                </tr>
              ) : (
                filteredRequests.map((req) => (
                  <tr
                    key={req.request_id}
                    className={`hover:bg-slate-800/50 transition ${
                      modifiedRequestIds?.has(req.request_id) ? 'bg-amber-500/5 border-l-2 border-l-amber-400' : ''
                    }`}
                  >
                    {/* Request ID */}
                    <td className="px-4 py-3 font-mono font-bold text-white whitespace-nowrap">
                      <div className="flex items-center space-x-1.5">
                        <span>{req.request_id}</span>
                        {modifiedRequestIds?.has(req.request_id) && (
                          <span
                            className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[9px] font-bold"
                            title="Modified in What-If Simulator"
                          >
                            ⚡ SIM
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Source System */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold border border-slate-700 text-[11px]">
                        {req.source_system}
                      </span>
                    </td>

                    {/* Dept & Work Type */}
                    <td className="px-4 py-3">
                      <div className="flex items-center space-x-2">
                        <DeptBadge dept={req.department} />
                        <span className="font-semibold text-slate-100">{req.work_type}</span>
                      </div>
                    </td>

                    {/* Asset Details */}
                    <td className="px-4 py-3">
                      <span className="font-mono text-slate-200 block text-[11px]">{req.asset_id}</span>
                      <span className="text-[10px] text-slate-400">{req.asset_type}</span>
                    </td>

                    {/* Section & Chainage */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-slate-200 block font-medium">{req.section_id}</span>
                      <span className="text-[10px] font-mono text-slate-400">
                        KM {typeof req.chainage_start === 'number' ? req.chainage_start.toFixed(2) : req.chainage_start} - {typeof req.chainage_end === 'number' ? req.chainage_end.toFixed(2) : req.chainage_end}
                      </span>
                    </td>

                    {/* Window & Duration */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-slate-200 font-medium block">
                        {req.requested_window_start?.slice(11, 16) || '00:00'} - {req.requested_window_end?.slice(11, 16) || '00:00'}
                      </span>
                      <span className="text-[10px] text-slate-400">{req.required_duration_minutes ?? '-'} min required</span>
                    </td>

                    {/* Condition Features */}
                    <td className="px-4 py-3 text-[11px] text-slate-300">
                      <div>
                        Age: {typeof req.asset_age_years === 'number' ? req.asset_age_years.toFixed(1) : (req.asset_age_years ?? '-')}y | Maint: {req.last_maintenance_days_ago ?? '-'}d
                      </div>
                      <div className="text-slate-400 text-[10px]">
                        Failures: {req.past_breakdown_count ?? 0} | Score: {typeof req.condition_score === 'number' ? req.condition_score.toFixed(1) : (req.condition_score ?? '-')}/10
                      </div>
                    </td>

                    {/* ML Risk Score */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <UrgencyBadge
                        tier={(req.urgency_category || 'MEDIUM').toUpperCase()}
                        score={req.risk_score}
                      />
                    </td>

                    {/* Power / Traffic */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center space-x-1 text-[11px]">
                        {req.requires_power_block && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30"
                            title="Requires 25kV OHE Power Block"
                          >
                            ⚡
                          </span>
                        )}
                        {req.requires_traffic_block && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 font-bold border border-red-500/30"
                            title="Requires Train Traffic Block"
                          >
                            🛑
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={req.status || 'PENDING'} />
                    </td>

                    {/* What-If Action */}
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenWhatIf?.(req);
                        }}
                        className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 hover:text-white border border-amber-500/40 font-bold text-[11px] transition shadow-sm inline-flex items-center space-x-1"
                        title="Simulate time shift or urgency change on this request"
                      >
                        <span>⚡ What-If</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
