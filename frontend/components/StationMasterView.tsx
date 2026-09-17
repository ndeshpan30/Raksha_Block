import React, { useState, useMemo } from 'react';
import { BundledBlock } from '@/types/raksha';
import { DeptBadge, StatusBadge, UrgencyBadge } from './StatBadge';

interface StationMasterViewProps {
  blocks: BundledBlock[];
  onSelectBlock: (b: BundledBlock) => void;
}

const STATIONS = [
  { code: 'GZB', name: 'Ghaziabad Junction', km: 24.5 },
  { code: 'ALJN', name: 'Aligarh Junction', km: 126.0 },
  { code: 'TDL', name: 'Tundla Junction', km: 204.0 },
  { code: 'CNB', name: 'Kanpur Central', km: 435.0 },
  { code: 'PRYJ', name: 'Prayagraj Junction', km: 630.0 },
  { code: 'DDU', name: 'Pt. Deen Dayal Upadhyaya Junction', km: 780.0 },
  { code: 'TKJ', name: 'Tilak Bridge', km: 5.0 },
  { code: 'MB', name: 'Moradabad Junction', km: 165.0 },
  { code: 'NDLS', name: 'New Delhi', km: 0.0 },
];

export const StationMasterView: React.FC<StationMasterViewProps> = ({
  blocks,
  onSelectBlock,
}) => {
  const [selectedStation, setSelectedStation] = useState<string>('ALJN');
  const [checklist, setChecklist] = useState<Record<string, boolean>>({
    disconnection_memo: true,
    ohe_permit_received: true,
    caution_order_issued: false,
    track_fit_certified: false,
  });

  // Filter blocks relevant to selected station
  const stationBlocks = useMemo(() => {
    return blocks.filter((b) => {
      // Matches section names or chainage near station
      return b.section_id.includes(selectedStation);
    });
  }, [blocks, selectedStation]);

  const toggleChecklist = (key: string) => {
    setChecklist((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const powerBlocksCount = stationBlocks.filter((b) => b.power_block_granted).length;
  const trafficBlocksCount = stationBlocks.filter((b) => b.traffic_block_granted).length;

  return (
    <div className="space-y-6">
      {/* Station Master Header Banner */}
      <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-400">Station Control Console</span>
            <span className="text-slate-600">•</span>
            <span className="text-xs text-slate-400">Station Yard & Block Section Possessions</span>
          </div>
          <h2 className="text-2xl font-black text-white mt-1">
            Station: {selectedStation} —{' '}
            {STATIONS.find((s) => s.code === selectedStation)?.name || selectedStation}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time yard interlocking, traction power status, and line possession monitoring
          </p>
        </div>

        {/* Station Selector */}
        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400 font-semibold">Select Station:</span>
          <select
            value={selectedStation}
            onChange={(e) => setSelectedStation(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-white font-bold rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATIONS.map((s) => (
              <option key={s.code} value={s.code}>
                {s.code} ({s.name})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Operational Impact Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Scheduled Yard Blocks</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-white">{stationBlocks.length}</span>
            <span className="text-xs text-slate-400">Windows</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Impacting station approaches</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <span className="text-amber-400 text-xs font-semibold uppercase tracking-wider">25kV OHE Power Cuts</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-amber-400">{powerBlocksCount}</span>
            <span className="text-xs text-amber-400/80">Dead Sections</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Traction isolation active</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <span className="text-red-400 text-xs font-semibold uppercase tracking-wider">Train Traffic Possessions</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-red-400">{trafficBlocksCount}</span>
            <span className="text-xs text-red-400/80">Absolute Stops</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Movements suspended</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <span className="text-emerald-400 text-xs font-semibold uppercase tracking-wider">Line Hours Saved</span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-black text-emerald-400">
              {(stationBlocks.reduce((acc, b) => acc + (b.savings_minutes || 0), 0) / 60).toFixed(1)} h
            </span>
            <span className="text-xs text-emerald-400/80">Bundling</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Fewer train detention cycles</p>
        </div>
      </div>

      {/* Interlocking & Clearance Checklist */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center space-x-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          <span>Station Master Possession Clearance & Interlocking Verification</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <label className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={checklist.disconnection_memo}
              onChange={() => toggleChecklist('disconnection_memo')}
              className="rounded border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-200">S&T Disconnection Memo (S&T T/351)</span>
          </label>

          <label className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={checklist.ohe_permit_received}
              onChange={() => toggleChecklist('ohe_permit_received')}
              className="rounded border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-200">TRD Permit-to-Work (PTW-25kV)</span>
          </label>

          <label className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={checklist.caution_order_issued}
              onChange={() => toggleChecklist('caution_order_issued')}
              className="rounded border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-200">Caution Order (T/409) to Drivers</span>
          </label>

          <label className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={checklist.track_fit_certified}
              onChange={() => toggleChecklist('track_fit_certified')}
              className="rounded border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-200">P-Way Track Fit Certificate</span>
          </label>
        </div>
      </div>

      {/* Station Blocks Schedule List */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Confirmed Block Windows Affecting {selectedStation} Yard ({stationBlocks.length})
          </h3>
          <span className="text-xs text-slate-400">Click any block to view coordination breakdown</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 font-semibold">Block ID</th>
                <th className="px-4 py-3 font-semibold">Section & Corridor</th>
                <th className="px-4 py-3 font-semibold">Chainage Span</th>
                <th className="px-4 py-3 font-semibold">Scheduled Window</th>
                <th className="px-4 py-3 font-semibold">Active Crews</th>
                <th className="px-4 py-3 font-semibold">Traction / Traffic</th>
                <th className="px-4 py-3 font-semibold">Savings</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {stationBlocks.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-400">
                    No scheduled blocks currently assigned to {selectedStation} section.
                  </td>
                </tr>
              ) : (
                stationBlocks.map((block) => (
                  <tr
                    key={block.block_id}
                    onClick={() => onSelectBlock(block)}
                    className="hover:bg-slate-800/50 cursor-pointer transition"
                  >
                    <td className="px-4 py-3 font-mono font-bold text-white whitespace-nowrap">
                      {block.block_id}
                    </td>

                    <td className="px-4 py-3">
                      <span className="font-semibold text-slate-200 block">{block.section_id}</span>
                      <span className="text-[10px] text-slate-400">{block.corridor_slot}</span>
                    </td>

                    <td className="px-4 py-3 font-mono">
                      KM {typeof block.start_km === 'number' ? block.start_km.toFixed(1) : block.start_km} - {typeof block.end_km === 'number' ? block.end_km.toFixed(1) : block.end_km}
                    </td>

                    <td className="px-4 py-3">
                      <span className="font-bold text-white block">
                        {block.scheduled_start?.slice(11, 16)} - {block.scheduled_end?.slice(11, 16)}
                      </span>
                      <span className="text-[10px] text-slate-400">{block.total_duration_minutes} min duration</span>
                    </td>

                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {block.departments_involved.map((dept) => (
                          <DeptBadge key={dept} dept={dept} />
                        ))}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="flex items-center space-x-1.5">
                        {block.power_block_granted && (
                          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 text-[11px]">
                            ⚡ OHE Dead
                          </span>
                        )}
                        {block.traffic_block_granted && (
                          <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-bold border border-red-500/30 text-[11px]">
                            🛑 Line Block
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="px-4 py-3 font-bold text-emerald-400">
                      {block.savings_minutes > 0 ? `+${block.savings_minutes}m` : '0m'}
                    </td>

                    <td className="px-4 py-3">
                      <StatusBadge status={block.approval_status || 'PROPOSED'} />
                    </td>

                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectBlock(block);
                        }}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-blue-400 rounded text-xs font-semibold border border-slate-700 transition"
                      >
                        Inspect
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
