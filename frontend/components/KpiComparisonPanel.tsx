'use client';

import React from 'react';
import { BaselineComparison } from '@/types/raksha';

interface KpiComparisonPanelProps {
  comparison: BaselineComparison | null;
  solveTimeSeconds?: number;
  isOpen: boolean;
  onToggle: () => void;
}

export const KpiComparisonPanel: React.FC<KpiComparisonPanelProps> = ({
  comparison,
  solveTimeSeconds,
  isOpen,
  onToggle,
}) => {
  if (!comparison) return null;

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl shadow-xl overflow-hidden mb-6 transition-all duration-300">
      {/* Header bar with toggle */}
      <div 
        onClick={onToggle}
        className="p-4 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 border-b border-slate-800 flex items-center justify-between cursor-pointer select-none hover:bg-slate-800/40 transition"
      >
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-sm">
            📊
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-white tracking-wide">
                Executive KPI Impact: Baseline (Unbundled) vs. CP-SAT Optimized
              </h3>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Phase 8 (P2)
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Mathematical proof of cross-departmental spatial/temporal bundling efficiency
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {solveTimeSeconds !== undefined && (
            <span className="text-[11px] font-mono text-slate-400 hidden sm:inline-block">
              Solve time: <strong className="text-blue-400">{solveTimeSeconds.toFixed(2)}s</strong>
            </span>
          )}
          <button className="text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/50">
            {isOpen ? '▲ Collapse' : '▼ Expand'}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="p-5 space-y-5 animate-in fade-in duration-200">
          {/* Main 4 Comparative Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Total Blocks Count */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Total Possession Blocks</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-bold">
                  -{comparison.block_count_reduction_pct.toFixed(1)}%
                </span>
              </div>

              <div className="my-3 flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-500 block">Baseline</span>
                  <span className="text-lg font-bold text-slate-400 line-through">
                    {comparison.baseline_block_count}
                  </span>
                </div>
                <div className="text-slate-600 font-bold text-base">➔</div>
                <div className="text-right">
                  <span className="text-xs text-emerald-400 block font-semibold">Optimized</span>
                  <span className="text-2xl font-black text-white">
                    {comparison.optimized_block_count}
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-2.5 py-1 text-center">
                ✓ {comparison.block_count_reduction} fewer track blocks
              </div>
            </div>

            {/* 2. Total Line Possession Hours */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Total Possession Duration</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                  -{comparison.possession_reduction_pct.toFixed(1)}%
                </span>
              </div>

              <div className="my-3 flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-500 block">Baseline</span>
                  <span className="text-lg font-bold text-slate-400 line-through">
                    {comparison.baseline_possession_hours.toFixed(1)}h
                  </span>
                </div>
                <div className="text-slate-600 font-bold text-base">➔</div>
                <div className="text-right">
                  <span className="text-xs text-emerald-400 block font-semibold">Optimized</span>
                  <span className="text-2xl font-black text-white">
                    {comparison.optimized_possession_hours.toFixed(1)}h
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-2.5 py-1 text-center">
                ⚡ {comparison.possession_savings_hours.toFixed(1)} hrs saved ({comparison.possession_savings_minutes}m)
              </div>
            </div>

            {/* 3. Train Traffic Closure Halts */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Train Traffic Halts</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                  Avoided
                </span>
              </div>

              <div className="my-3 flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-500 block">Baseline Halts</span>
                  <span className="text-lg font-bold text-slate-400 line-through">
                    {comparison.baseline_traffic_halts}
                  </span>
                </div>
                <div className="text-slate-600 font-bold text-base">➔</div>
                <div className="text-right">
                  <span className="text-xs text-emerald-400 block font-semibold">Optimized Halts</span>
                  <span className="text-2xl font-black text-white">
                    {comparison.optimized_traffic_halts}
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-amber-300 font-semibold bg-amber-500/10 border border-amber-500/20 rounded-lg px-2.5 py-1 text-center">
                🛑 {comparison.avoided_traffic_halts} line closures avoided
              </div>
            </div>

            {/* 4. Coordinated Bundles Created */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Coordinated Bundles</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold">
                  Cross-Dept
                </span>
              </div>

              <div className="my-3 flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-500 block">Baseline</span>
                  <span className="text-lg font-bold text-slate-400">0</span>
                </div>
                <div className="text-slate-600 font-bold text-base">➔</div>
                <div className="text-right">
                  <span className="text-xs text-purple-400 block font-semibold">Bundled Blocks</span>
                  <span className="text-2xl font-black text-purple-200">
                    {comparison.coordinated_bundles_created}
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-purple-300 font-semibold bg-purple-500/10 border border-purple-500/20 rounded-lg px-2.5 py-1 text-center">
                🤝 {comparison.triple_department_bundles} Triple + {comparison.dual_department_bundles} Dual Dept
              </div>
            </div>
          </div>

          {/* Efficiency Breakdown Progress Bar */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-300 font-medium">Track Capacity Recovery Factor:</span>
              <span className="font-bold text-emerald-400">
                {comparison.possession_reduction_pct.toFixed(1)}% Time Efficiency Gain
              </span>
            </div>
            <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden flex">
              <div 
                className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full rounded-full transition-all duration-1000"
                style={{ width: `${Math.min(100, Math.max(0, comparison.possession_reduction_pct * 3.5))}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 mt-1.5">
              <span>0% Baseline (Unbundled)</span>
              <span>Target: 15-25% Hackathon Goal</span>
              <span className="text-emerald-400 font-bold">Achieved: {comparison.possession_reduction_pct.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
