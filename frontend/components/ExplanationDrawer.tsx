import React, { useState } from 'react';
import { BundledBlock, BlockExplanation } from '@/types/raksha';
import { UrgencyBadge, DeptBadge, StatusBadge } from './StatBadge';

interface ExplanationDrawerProps {
  block: BundledBlock | null;
  isOpen: boolean;
  onClose: () => void;
  onAction: (blockId: string, action: 'APPROVE' | 'REJECT' | 'MODIFY', notes?: string) => Promise<void>;
  onOpenWhatIf?: (requestId: string) => void;
}

export const ExplanationDrawer: React.FC<ExplanationDrawerProps> = ({
  block,
  isOpen,
  onClose,
  onAction,
  onOpenWhatIf,
}) => {
  const [controllerNotes, setControllerNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  if (!isOpen || !block) return null;

  const expl: BlockExplanation | undefined = block.explanation_detail || block.explanation;

  const handleAction = async (action: 'APPROVE' | 'REJECT' | 'MODIFY') => {
    setActionLoading(true);
    setActionSuccess(null);
    try {
      await onAction(block.block_id, action, controllerNotes);
      setActionSuccess(`Block successfully marked as ${action}D`);
      setTimeout(() => setActionSuccess(null), 3500);
    } catch {
      setActionSuccess(`Failed to update block status.`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Slide-out Drawer */}
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-slate-900 border-l border-slate-800 text-slate-100 shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="px-6 py-5 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
            <div>
              <div className="flex items-center space-x-3">
                <h2 className="text-xl font-bold text-white tracking-tight">{block.block_id}</h2>
                <StatusBadge status={block.approval_status || 'PROPOSED'} />
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Section: <span className="font-semibold text-slate-200">{block.section_id}</span> | Slot:{' '}
                <span className="font-semibold text-slate-200">{block.corridor_slot}</span> | Span:{' '}
                <span className="font-semibold text-slate-200">
                  KM {typeof block.start_km === 'number' ? block.start_km.toFixed(2) : block.start_km} - {typeof block.end_km === 'number' ? block.end_km.toFixed(2) : block.end_km} ({typeof block.end_km === 'number' && typeof block.start_km === 'number' ? `${(block.end_km - block.start_km).toFixed(2)} km` : '-'})
                </span>
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Drawer Scrollable Body */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 text-sm">
            {/* Phase 7 What-If Simulation Delta Indicator */}
            {(block.is_modified || block.delta_type) && (
              <div className="bg-amber-500/10 border border-amber-500/50 rounded-lg p-3 flex items-center justify-between text-xs text-amber-300 shadow-md animate-in fade-in">
                <div className="flex items-center space-x-2.5">
                  <span className="text-base">⚡</span>
                  <div>
                    <span className="font-bold text-white uppercase tracking-wide text-[11px]">
                      Interactive Re-optimization Delta
                    </span>
                    <p className="text-slate-300 text-[11px] mt-0.5">
                      This block schedule and constraint reasoning were dynamically updated via Localized Delta CP-SAT re-optimization.
                    </p>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold font-mono">
                  {block.delta_type || 'REOPTIMIZED'}
                </span>
              </div>
            )}

            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-800/80 p-3 rounded-lg border border-slate-700/60">
                <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Possession Window</span>
                <p className="text-sm font-bold text-white mt-1">
                  {block.scheduled_start?.slice(11, 16)} - {block.scheduled_end?.slice(11, 16)}
                </p>
                <p className="text-xs text-slate-400">{block.total_duration_minutes} mins duration</p>
              </div>

              <div className="bg-slate-800/80 p-3 rounded-lg border border-slate-700/60">
                <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Departments</span>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {block.departments_involved.map((dept) => (
                    <DeptBadge key={dept} dept={dept} />
                  ))}
                </div>
                <p className="text-xs text-slate-400 mt-1">{block.bundled_request_ids.length} requests combined</p>
              </div>

              <div className="bg-slate-800/80 p-3 rounded-lg border border-slate-700/60">
                <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-medium">Possession Saved</span>
                <p className="text-lg font-extrabold text-emerald-400 mt-0.5">
                  {block.savings_minutes} min
                </p>
                <p className="text-xs text-emerald-400/80">
                  {typeof expl?.alternatives_considered?.possession_savings_pct === 'number'
                    ? `${expl.alternatives_considered.possession_savings_pct.toFixed(1)}% reduction`
                    : 'Consolidated window'}
                </p>
              </div>
            </div>

            {/* Section 1: Plain-Language Summary */}
            <div className="bg-blue-950/30 border border-blue-800/50 rounded-lg p-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center space-x-1.5">
                <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>AI Coordination Summary</span>
              </h3>
              <p className="text-slate-200 text-xs leading-relaxed mt-2">
                {expl?.summary || block.explanation_text || 'No explanation generated for this block.'}
              </p>
            </div>

            {/* Section 2: Driving Priority & Risk Rationale */}
            {expl?.driving_priority && (
              <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center space-x-1.5">
                    <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span>Driving Priority & Failure Risk</span>
                  </h3>
                  <UrgencyBadge
                    tier={expl.driving_priority.risk_tier}
                    score={expl.driving_priority.highest_risk_score}
                  />
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs bg-slate-900/60 p-2.5 rounded border border-slate-800">
                  <div>
                    <span className="text-slate-400">Highest Risk Asset:</span>{' '}
                    <span className="font-mono font-medium text-slate-200">{expl.driving_priority.highest_risk_asset_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Anchor Request:</span>{' '}
                    <span className="font-mono font-medium text-slate-200">{expl.driving_priority.highest_risk_request_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Work Category:</span>{' '}
                    <span className="font-medium text-slate-200">{expl.driving_priority.highest_risk_work_type}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Average Risk Score:</span>{' '}
                    <span className="font-medium text-slate-200">
                      {typeof expl.driving_priority.average_risk_score === 'number'
                        ? `${expl.driving_priority.average_risk_score.toFixed(1)} / 100`
                        : `${expl.driving_priority.average_risk_score ?? '-'} / 100`}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 italic bg-amber-500/10 p-2.5 rounded border border-amber-500/20">
                  &ldquo;{expl.driving_priority.anchoring_reason}&rdquo;
                </p>
              </div>
            )}

            {/* Section 3: Driving Constraints */}
            {expl?.driving_constraints && (
              <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
                  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <span>Governing Constraints & Protection</span>
                </h3>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                    <span className="text-slate-400 block">Spatial Overlap Type</span>
                    <span className="font-semibold text-blue-400">{expl.driving_constraints.spatial_overlap_type}</span>
                    <span className="text-slate-400 block mt-0.5">
                      Gap: {typeof expl.driving_constraints.actual_spatial_gap_km === 'number'
                        ? `${expl.driving_constraints.actual_spatial_gap_km.toFixed(2)} km`
                        : '-'}
                    </span>
                  </div>
                  <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                    <span className="text-slate-400 block">Window Slack Available</span>
                    <span className="font-semibold text-slate-200">
                      {expl.driving_constraints.window_bounds?.total_window_slack_minutes || 0} minutes
                    </span>
                    <span className="text-slate-400 block mt-0.5">Slot: {expl.driving_constraints.corridor_slot}</span>
                  </div>
                </div>

                {/* Power & Traffic Block Drivers */}
                {expl.driving_constraints.power_block_driver && (
                  <div className="text-xs p-2.5 bg-amber-500/10 rounded border border-amber-500/20 text-amber-300">
                    <span className="font-bold">⚡ 25kV OHE Power Block:</span> {expl.driving_constraints.power_block_driver}
                  </div>
                )}
                {expl.driving_constraints.traffic_block_driver && (
                  <div className="text-xs p-2.5 bg-red-500/10 rounded border border-red-500/20 text-red-300">
                    <span className="font-bold">🛑 Train Traffic Block:</span> {expl.driving_constraints.traffic_block_driver}
                  </div>
                )}

                {/* Applied constraints checklist */}
                {expl.driving_constraints.key_constraints_applied?.length > 0 && (
                  <div className="space-y-1 mt-2">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Solver Constraints Enforced:</span>
                    <ul className="space-y-1 text-xs text-slate-300">
                      {expl.driving_constraints.key_constraints_applied.map((c, i) => (
                        <li key={i} className="flex items-start space-x-2">
                          <span className="text-emerald-400 font-bold">✓</span>
                          <span>{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Section 4: Constituent Requests List */}
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
                <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                <span>Constituent Maintenance Requests ({block.bundled_request_ids.length})</span>
              </h3>

              <div className="space-y-2">
                {(expl?.merged_requests || block.constituent_requests || []).map((req, idx) => (
                  <div
                    key={req.request_id || idx}
                    className="bg-slate-900/80 p-2.5 rounded border border-slate-800 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <DeptBadge dept={req.department} />
                        <span className="font-mono text-xs font-semibold text-white">{req.request_id}</span>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        <UrgencyBadge
                          tier={(req as any).urgency_tier || (req as any).urgency_category || 'MEDIUM'}
                          score={req.risk_score}
                        />
                        {onOpenWhatIf && (
                          <button
                            type="button"
                            onClick={() => onOpenWhatIf(req.request_id)}
                            title="Simulate What-If on this constituent request"
                            className="px-1.5 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-[10px] border border-amber-500/30 transition"
                          >
                            ⚡ What-If
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-slate-300">
                      <span className="font-medium text-slate-100">{req.work_type}</span> on{' '}
                      <span className="font-mono text-slate-300">{req.asset_id}</span> ({req.asset_type})
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
                      <span>
                        KM {typeof req.chainage_start === 'number' ? req.chainage_start.toFixed(2) : req.chainage_start} - {typeof req.chainage_end === 'number' ? req.chainage_end.toFixed(2) : req.chainage_end}
                      </span>
                      <span>Req Duration: {req.required_duration_minutes ?? '-'} min</span>
                      <div className="flex items-center space-x-1">
                        {req.requires_power_block && <span className="text-amber-400 font-bold" title="Requires Power Block">⚡ OHE</span>}
                        {req.requires_traffic_block && <span className="text-red-400 font-bold" title="Requires Traffic Block">🛑 Traffic</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 5: Alternatives Considered */}
            {expl?.alternatives_considered && (
              <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
                  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  <span>Alternatives Evaluated & Counterfactuals</span>
                </h3>

                <div className="bg-slate-900/60 p-3 rounded border border-slate-800 space-y-2 text-xs">
                  <div>
                    <span className="text-slate-400 font-medium">Why not separate blocks?</span>
                    <p className="text-slate-200 mt-0.5">{expl.alternatives_considered.why_not_scheduled_separately}</p>
                  </div>
                  <div className="pt-2 border-t border-slate-800">
                    <span className="text-slate-400 font-medium">Why not deferred?</span>
                    <p className="text-slate-200 mt-0.5">{expl.alternatives_considered.why_not_deferred}</p>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Candidate Options Explored:</span>
                  <ul className="space-y-1 text-xs text-slate-300">
                    {expl.alternatives_considered.alternatives_evaluated?.map((alt, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="text-amber-400">•</span>
                        <span>{alt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Section 6: Controller Action & Human-in-the-Loop Decision */}
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Section Controller Decision
              </h3>
              <textarea
                value={controllerNotes}
                onChange={(e) => setControllerNotes(e.target.value)}
                placeholder="Optional controller notes or operating remarks (e.g. 'Caution order CO-12 imposed at KM 167')..."
                className="w-full bg-slate-900 text-slate-200 border border-slate-700 rounded-lg p-2.5 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                rows={2}
              />

              {actionSuccess && (
                <div className="text-xs text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/30">
                  {actionSuccess}
                </div>
              )}

              <div className="flex items-center space-x-2 pt-1">
                <button
                  onClick={() => handleAction('APPROVE')}
                  disabled={actionLoading}
                  className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-2 px-3 rounded-lg text-xs transition"
                >
                  Approve Block
                </button>
                <button
                  onClick={() => handleAction('MODIFY')}
                  disabled={actionLoading}
                  className="bg-purple-600 hover:bg-purple-500 text-white font-semibold py-2 px-3 rounded-lg text-xs transition"
                >
                  Modify / Annotate
                </button>
                <button
                  onClick={() => handleAction('REJECT')}
                  disabled={actionLoading}
                  className="bg-red-600 hover:bg-red-500 text-white font-semibold py-2 px-3 rounded-lg text-xs transition"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
