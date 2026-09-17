import React from 'react';

interface UrgencyBadgeProps {
  tier: string;
  score?: number;
}

export const UrgencyBadge: React.FC<UrgencyBadgeProps> = ({ tier, score }) => {
  const upper = (tier || '').toUpperCase();
  const numScore = typeof score === 'number' && !isNaN(score) ? score : null;

  let bgClass = 'bg-slate-700 text-slate-300 border-slate-600';
  if (upper === 'CRITICAL' || (numScore !== null && numScore >= 75)) {
    bgClass = 'bg-red-500/20 text-red-400 border-red-500/40';
  } else if (upper === 'HIGH' || (numScore !== null && numScore >= 50)) {
    bgClass = 'bg-orange-500/20 text-orange-400 border-orange-500/40';
  } else if (upper === 'MEDIUM' || (numScore !== null && numScore >= 25)) {
    bgClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  } else if (upper === 'LOW' || (numScore !== null && numScore < 25)) {
    bgClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${bgClass}`}>
      {upper || 'LOW'}
      {numScore !== null && <span className="ml-1.5 opacity-80">({numScore.toFixed(1)})</span>}
    </span>
  );
};

export const DeptBadge: React.FC<{ dept: string }> = ({ dept }) => {
  const upper = (dept || '').toUpperCase();
  let bgClass = 'bg-slate-700 text-slate-300 border-slate-600';

  if (upper === 'ENG') {
    bgClass = 'bg-blue-500/20 text-blue-400 border-blue-500/40';
  } else if (upper === 'S&T') {
    bgClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  } else if (upper === 'TRD') {
    bgClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${bgClass}`}>
      {upper}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const upper = (status || '').toUpperCase();
  let bg = 'bg-slate-700 text-slate-300 border-slate-600';

  if (upper.includes('APPROVED')) {
    bg = 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50';
  } else if (upper.includes('REJECTED')) {
    bg = 'bg-red-500/25 text-red-300 border-red-500/50';
  } else if (upper.includes('MODIFIED')) {
    bg = 'bg-purple-500/25 text-purple-300 border-purple-500/50';
  } else if (upper.includes('BUNDLED') || upper.includes('SCHEDULED')) {
    bg = 'bg-blue-500/25 text-blue-300 border-blue-500/50';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${bg}`}>
      {upper}
    </span>
  );
};
