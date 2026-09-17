'use client';

import React, { useState, useEffect } from 'react';
import { MaintenanceRequest, UrgencyTier } from '@/types/raksha';
import { DeptBadge, UrgencyBadge } from './StatBadge';
import { calculateRiskScore } from '@/lib/api';

interface WhatIfModalProps {
  isOpen: boolean;
  request: MaintenanceRequest | null;
  onClose: () => void;
  onApply: (
    modifiedReq: MaintenanceRequest,
    options: { deltaMode: boolean; recomputeRisk: boolean }
  ) => Promise<void>;
  isOptimizing: boolean;
}

export const WhatIfModal: React.FC<WhatIfModalProps> = ({
  isOpen,
  request,
  onClose,
  onApply,
  isOptimizing,
}) => {
  const [urgency, setUrgency] = useState<UrgencyTier>('MEDIUM');
  const [windowStart, setWindowStart] = useState<string>('');
  const [windowEnd, setWindowEnd] = useState<string>('');
  const [durationMinutes, setDurationMinutes] = useState<number>(60);
  const [riskScore, setRiskScore] = useState<number>(0);
  const [riskTier, setRiskTier] = useState<string>('MEDIUM');
  const [deltaMode, setDeltaMode] = useState<boolean>(true);
  const [calculatingRisk, setCalculatingRisk] = useState<boolean>(false);
  const [shiftMinutes, setShiftMinutes] = useState<number>(0);

  // Sync state when request prop changes
  useEffect(() => {
    if (request) {
      const urg = (request.urgency_category || 'MEDIUM').toUpperCase() as UrgencyTier;
      setUrgency(urg);
      setWindowStart(request.requested_window_start || '');
      setWindowEnd(request.requested_window_end || '');
      setDurationMinutes(request.required_duration_minutes || 60);
      setRiskScore(request.risk_score ?? 0);
      setRiskTier(request.urgency_category || 'MEDIUM');
      setShiftMinutes(0);
    }
  }, [request]);

  if (!isOpen || !request) return null;

  // Handle shift by +/- hours
  const handleShiftHours = (hours: number) => {
    if (!request.requested_window_start || !request.requested_window_end) return;

    try {
      const baseStart = new Date(request.requested_window_start);
      const baseEnd = new Date(request.requested_window_end);

      const newStart = new Date(baseStart.getTime() + hours * 3600 * 1000);
      const newEnd = new Date(baseEnd.getTime() + hours * 3600 * 1000);

      setWindowStart(newStart.toISOString().slice(0, 19));
      setWindowEnd(newEnd.toISOString().slice(0, 19));
      setShiftMinutes(hours * 60);
    } catch (err) {
      console.error('Error shifting window:', err);
    }
  };

  // Handle urgency toggle with on-demand LightGBM re-scoring
  const handleUrgencyChange = async (newUrgency: UrgencyTier) => {
    setUrgency(newUrgency);
    setCalculatingRisk(true);
    try {
      const updatedMock: Partial<MaintenanceRequest> = {
        ...request,
        urgency_category: newUrgency,
      };
      const res = await calculateRiskScore(updatedMock);
      if (res) {
        setRiskScore(res.risk_score);
        setRiskTier(res.risk_tier);
      }
    } catch (err) {
      console.warn('Could not re-score risk score via LightGBM:', err);
    } finally {
      setCalculatingRisk(false);
    }
  };

  // Reset to original baseline values
  const handleReset = () => {
    if (!request) return;
    setUrgency((request.urgency_category || 'MEDIUM').toUpperCase() as UrgencyTier);
    setWindowStart(request.requested_window_start || '');
    setWindowEnd(request.requested_window_end || '');
    setDurationMinutes(request.required_duration_minutes || 60);
    setRiskScore(request.risk_score ?? 0);
    setRiskTier(request.urgency_category || 'MEDIUM');
    setShiftMinutes(0);
  };

  // Submit simulation & re-optimize
  const handleSubmit = async () => {
    if (!request) return;

    const modifiedReq: MaintenanceRequest = {
      ...request,
      urgency_category: urgency,
      requested_window_start: windowStart,
      requested_window_end: windowEnd,
      required_duration_minutes: durationMinutes,
      risk_score: riskScore,
    };

    await onApply(modifiedReq, {
      deltaMode,
      recomputeRisk: urgency !== request.urgency_category,
    });
  };

  const startDisplay = windowStart.length >= 16 ? windowStart.slice(11, 16) : '00:00';
  const endDisplay = windowEnd.length >= 16 ? windowEnd.slice(11, 16) : '00:00';
  const origStart = request.requested_window_start?.slice(11, 16) || '00:00';
  const origEnd = request.requested_window_end?.slice(11, 16) || '00:00';
  const hasWindowShifted = shiftMinutes !== 0;
  const hasUrgencyChanged = urgency !== (request.urgency_category || 'MEDIUM').toUpperCase();
  const hasDurationChanged = durationMinutes !== request.required_duration_minutes;
  const hasAnyChange = hasWindowShifted || hasUrgencyChanged || hasDurationChanged;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 bg-slate-950 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 font-bold text-lg">
              ⚡
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-white">What-If Constraint Simulator</h3>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Phase 7
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Interactive re-optimization without full page reload
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white rounded-lg p-1.5 hover:bg-slate-800 transition text-lg"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-5 overflow-y-auto flex-1 text-xs">
          {/* Target Request Info Card */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-white text-sm">{request.request_id}</span>
              <DeptBadge dept={request.department} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300">
              <div>
                <span className="text-slate-500 block">Work Type:</span>
                <span className="font-semibold text-slate-200">{request.work_type}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Asset:</span>
                <span className="font-mono text-slate-200">{request.asset_id}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Section & Chainage:</span>
                <span>
                  {request.section_id} (KM {typeof request.chainage_start === 'number' ? request.chainage_start.toFixed(1) : request.chainage_start}-{typeof request.chainage_end === 'number' ? request.chainage_end.toFixed(1) : request.chainage_end})
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Baseline Window:</span>
                <span className="font-medium text-slate-300">
                  {origStart} - {origEnd} ({request.required_duration_minutes}m)
                </span>
              </div>
            </div>
          </div>

          {/* 1. Urgency Tier & LightGBM Risk Recalculation */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-bold text-white flex items-center space-x-1.5">
                <span>1. Operational Urgency Tier & LightGBM ML Risk</span>
              </label>
              {calculatingRisk && (
                <span className="text-[10px] text-blue-400 animate-pulse">
                  ⚡ Running LightGBM inference...
                </span>
              )}
            </div>

            <div className="grid grid-cols-4 gap-2">
              {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as UrgencyTier[]).map((tier) => {
                const isSelected = urgency === tier;
                const colors = {
                  LOW: isSelected ? 'bg-slate-700 text-slate-200 border-slate-500' : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700',
                  MEDIUM: isSelected ? 'bg-blue-600/30 text-blue-300 border-blue-500' : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-blue-500/50',
                  HIGH: isSelected ? 'bg-amber-600/30 text-amber-300 border-amber-500' : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-amber-500/50',
                  CRITICAL: isSelected ? 'bg-red-600/30 text-red-300 border-red-500' : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-red-500/50',
                };
                return (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => handleUrgencyChange(tier)}
                    className={`py-2 px-2.5 rounded-lg border text-center font-bold transition flex flex-col items-center justify-center space-y-1 ${colors[tier]}`}
                  >
                    <span>{tier}</span>
                    {isSelected && <span className="text-[10px] opacity-80 font-normal">Active</span>}
                  </button>
                );
              })}
            </div>

            {/* Dynamic ML Risk Score Delta */}
            <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-[11px]">
              <div className="flex items-center space-x-2">
                <span className="text-slate-400">LightGBM Risk Score:</span>
                <UrgencyBadge tier={riskTier as any} score={riskScore} />
              </div>
              {hasUrgencyChanged && (
                <span className="text-amber-400 font-semibold">
                  Delta: {typeof request.risk_score === 'number' ? (riskScore - request.risk_score > 0 ? `+${(riskScore - request.risk_score).toFixed(1)}` : (riskScore - request.risk_score).toFixed(1)) : 'Updated'} pts
                </span>
              )}
            </div>
          </div>

          {/* 2. Shift Operational Time Window */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-bold text-white">2. Shift Requested Window Timing</label>
              {hasWindowShifted && (
                <span className="text-[11px] font-mono text-amber-400 font-semibold">
                  Shift: {shiftMinutes > 0 ? `+${shiftMinutes / 60}h` : `${shiftMinutes / 60}h`} delay
                </span>
              )}
            </div>

            {/* Quick Shift Pills */}
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => handleShiftHours(-2)}
                className="flex-1 py-1.5 px-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-300 font-semibold transition"
              >
                -2h Earlier
              </button>
              <button
                type="button"
                onClick={() => handleShiftHours(-1)}
                className="flex-1 py-1.5 px-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-300 font-semibold transition"
              >
                -1h Earlier
              </button>
              <button
                type="button"
                onClick={() => handleShiftHours(0)}
                className={`flex-1 py-1.5 px-2 border rounded-lg font-semibold transition ${
                  shiftMinutes === 0
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 hover:bg-slate-800 border-slate-800 text-slate-400'
                }`}
              >
                Baseline
              </button>
              <button
                type="button"
                onClick={() => handleShiftHours(1)}
                className="flex-1 py-1.5 px-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-300 font-semibold transition"
              >
                +1h Delay
              </button>
              <button
                type="button"
                onClick={() => handleShiftHours(2)}
                className="flex-1 py-1.5 px-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-300 font-semibold transition"
              >
                +2h Delay
              </button>
            </div>

            {/* Window Comparison Preview */}
            <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-[11px]">
              <div>
                <span className="text-slate-500 block">Baseline Window:</span>
                <span className="font-mono text-slate-400">{origStart} - {origEnd}</span>
              </div>
              <span className="text-slate-600 font-bold">➔</span>
              <div className="text-right">
                <span className="text-amber-400 block font-semibold">Simulated Window:</span>
                <span className="font-mono font-bold text-white">{startDisplay} - {endDisplay}</span>
              </div>
            </div>
          </div>

          {/* 3. Duration Adjustment */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-bold text-white">3. Required Block Duration (Minutes)</label>
              <span className="font-mono text-slate-300 font-semibold">{durationMinutes} min</span>
            </div>
            <div className="flex items-center space-x-2">
              {[45, 60, 90, 120, 150, 180].map((dur) => (
                <button
                  key={dur}
                  type="button"
                  onClick={() => setDurationMinutes(dur)}
                  className={`flex-1 py-1 px-1 rounded-lg border font-semibold text-[11px] transition ${
                    durationMinutes === dur
                      ? 'bg-indigo-600/30 text-indigo-300 border-indigo-500'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {dur}m
                </button>
              ))}
            </div>
          </div>

          {/* 4. Optimization Engine Mode */}
          <div className="space-y-2">
            <label className="font-bold text-white">4. Solver Execution Mode</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setDeltaMode(true)}
                className={`p-2.5 rounded-xl border text-left transition flex flex-col justify-between ${
                  deltaMode
                    ? 'bg-blue-600/20 border-blue-500 text-white shadow-sm'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-blue-300">⚡ Localized Delta</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/30 text-blue-200">
                    &lt; 100ms
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  Re-solves only the affected section/corridor component; keeps unaffected clusters constant.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setDeltaMode(false)}
                className={`p-2.5 rounded-xl border text-left transition flex flex-col justify-between ${
                  !deltaMode
                    ? 'bg-indigo-600/20 border-indigo-500 text-white shadow-sm'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-indigo-300">🔄 Full Fleet Re-solve</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/30 text-indigo-200">
                    ~4.8s
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  Global re-optimization across all 240 requests &amp; 8 sections from scratch.
                </p>
              </button>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between">
          <button
            type="button"
            onClick={handleReset}
            disabled={!hasAnyChange || isOptimizing}
            className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 transition disabled:opacity-40"
          >
            Reset Constraints
          </button>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white font-semibold text-xs transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isOptimizing}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 hover:from-amber-400 hover:to-red-400 text-white font-bold text-xs shadow-lg transition flex items-center space-x-1.5 disabled:opacity-50"
            >
              {isOptimizing ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Re-optimizing CP-SAT...</span>
                </>
              ) : (
                <>
                  <span>⚡ Apply &amp; Re-optimize</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
