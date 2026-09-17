import React from 'react';
import { PersonaType, SystemHealth } from '@/types/raksha';

interface NavbarProps {
  activePersona: PersonaType;
  onSelectPersona: (p: PersonaType) => void;
  systemHealth: SystemHealth | null;
  loading: boolean;
  onRefresh: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activePersona,
  onSelectPersona,
  systemHealth,
  loading,
  onRefresh,
}) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand & Identity */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 via-indigo-600 to-amber-500 flex items-center justify-center shadow-lg">
              <span className="text-white font-black text-xl tracking-tighter">RB</span>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-white text-lg tracking-wide">RAKSHA-BLOCK</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  SIH26027
                </span>
              </div>
              <p className="text-xs text-slate-400">AI-Powered Railway Maintenance Coordination</p>
            </div>
          </div>

          {/* Persona Toggle (Hardcoded, no real auth) */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => onSelectPersona('controller')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activePersona === 'controller'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              Section Controller
            </button>
            <button
              onClick={() => onSelectPersona('planner')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activePersona === 'planner'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              Department Planner
            </button>
            <button
              onClick={() => onSelectPersona('station_master')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activePersona === 'station_master'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              Station Master
            </button>
          </div>

          {/* System Health & Refresh */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  systemHealth?.status === 'healthy'
                    ? 'bg-emerald-400 animate-pulse'
                    : 'bg-amber-400'
                }`}
              />
              <span className="text-slate-300 font-mono text-[11px]">
                {systemHealth?.status === 'healthy' ? 'FastAPI :8000 LIVE' : 'FastAPI Connected'}
              </span>
            </div>

            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition"
              title="Refresh Data from Backend"
            >
              <svg
                className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
