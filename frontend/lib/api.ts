/**
 * RAKSHA-BLOCK: Frontend API Client
 * Interfaces with FastAPI backend (port 8000) or internal Next.js proxy routes.
 */

import {
  BundledBlock,
  OptimizationPlan,
  MaintenanceRequest,
  BlockExplanation,
  BlockActionResponse,
  SystemHealth,
} from '@/types/raksha';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * Check backend health status
 */
export async function checkBackendHealth(): Promise<SystemHealth | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/health`, { cache: 'no-store' });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback 1: Next.js rewrite proxy
    try {
      const resProxy = await fetch('/backend-api/api/v1/health', { cache: 'no-store' });
      if (resProxy.ok) return await resProxy.json();
    } catch {
      // Fallback 2: Next.js internal API route handler
      try {
        const resRoute = await fetch('/api/health', { cache: 'no-store' });
        if (resRoute.ok) return await resRoute.json();
      } catch {
        // Backend not currently reachable
      }
    }
  }
  return null;
}

/**
 * Fetch all maintenance requests (GET /requests)
 */
export async function fetchMaintenanceRequests(params?: {
  department?: string;
  section_id?: string;
  limit?: number;
  offset?: number;
}): Promise<MaintenanceRequest[]> {
  const query = new URLSearchParams();
  if (params?.department) query.set('department', params.department);
  if (params?.section_id) query.set('section_id', params.section_id);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));

  const queryString = query.toString() ? `?${query.toString()}` : '';
  const url = `${BACKEND_URL}/requests${queryString}`;
  const proxyUrl = `/backend-api/requests${queryString}`;
  const routeUrl = `/api/requests${queryString}`;

  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, { cache: 'no-store' });
      if (res.ok) return await res.json();
    } catch {
      try {
        const res = await fetch(routeUrl, { cache: 'no-store' });
        if (res.ok) return await res.json();
      } catch {
        console.warn('Backend requests endpoint not reachable, using fallback');
      }
    }
  }
  return [];
}

export interface OptimizationRequestOptions {
  section_id?: string;
  department?: string;
  requests?: MaintenanceRequest[];
  delta_mode?: boolean;
  modified_request_ids?: string[];
  recompute_risk?: boolean;
  spatial_proximity_km?: number;
  max_block_km_span?: number;
}

/**
 * Trigger optimizer to generate bundled block plan (POST /optimize)
 * Supports Phase 7 localized delta re-optimization for interactive What-If simulations.
 */
export async function fetchOptimizationPlan(options?: OptimizationRequestOptions): Promise<OptimizationPlan | null> {
  const query = new URLSearchParams();
  if (options?.section_id) query.set('section_id', options.section_id);
  if (options?.department) query.set('department', options.department);
  if (options?.delta_mode !== undefined) query.set('delta_mode', String(options.delta_mode));

  const queryString = query.toString() ? `?${query.toString()}` : '';
  const url = `${BACKEND_URL}/optimize${queryString}`;
  const proxyUrl = `/backend-api/optimize${queryString}`;
  const routeUrl = `/api/optimize${queryString}`;

  const bodyPayload: Record<string, any> = {};
  if (options?.requests) bodyPayload.requests = options.requests;
  if (options?.delta_mode !== undefined) bodyPayload.delta_mode = options.delta_mode;
  if (options?.modified_request_ids) bodyPayload.modified_request_ids = options.modified_request_ids;
  if (options?.recompute_risk !== undefined) bodyPayload.recompute_risk = options.recompute_risk;
  if (options?.spatial_proximity_km !== undefined) bodyPayload.spatial_proximity_km = options.spatial_proximity_km;
  if (options?.max_block_km_span !== undefined) bodyPayload.max_block_km_span = options.max_block_km_span;

  const reqOptions: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyPayload),
    cache: 'no-store',
  };

  try {
    const res = await fetch(url, reqOptions);
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, reqOptions);
      if (res.ok) return await res.json();
    } catch {
      try {
        const res = await fetch(routeUrl, reqOptions);
        if (res.ok) return await res.json();
      } catch {
        console.warn('Backend optimize endpoint not reachable');
      }
    }
  }
  return null;
}

/**
 * Run on-demand tabular inference for risk scoring (POST /api/v1/risk/score)
 */
export async function calculateRiskScore(
  requestData: Partial<MaintenanceRequest>
): Promise<{ risk_score: number; risk_tier: string } | null> {
  const payload = {
    asset_age_years: requestData.asset_age_years ?? 5.0,
    last_maintenance_days_ago: requestData.last_maintenance_days_ago ?? 90,
    past_breakdown_count: requestData.past_breakdown_count ?? 1,
    gross_million_tonnes: requestData.gross_million_tonnes ?? 45.0,
    condition_score: requestData.condition_score ?? 5.0,
    urgency_category: requestData.urgency_category || 'MEDIUM',
    request_id: requestData.request_id,
  };

  const url = `${BACKEND_URL}/api/v1/risk/score`;
  const proxyUrl = `/backend-api/api/v1/risk/score`;

  const reqOptions: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    cache: 'no-store',
  };

  try {
    const res = await fetch(url, reqOptions);
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, reqOptions);
      if (res.ok) return await res.json();
    } catch {
      // Fallback heuristic if offline
    }
  }

  // Fallback heuristic
  const urgencyMap: Record<string, number> = { LOW: 15, MEDIUM: 40, HIGH: 65, CRITICAL: 90 };
  const baseScore = urgencyMap[String(payload.urgency_category).toUpperCase()] || 40;
  const tier = baseScore >= 75 ? 'CRITICAL' : baseScore >= 50 ? 'HIGH' : baseScore >= 25 ? 'MEDIUM' : 'LOW';
  return { risk_score: baseScore, risk_tier: tier };
}

/**
 * Fetch all scheduled blocks (GET /api/v1/blocks)
 */
export async function fetchScheduledBlocks(filters?: {
  section_id?: string;
  department?: string;
}): Promise<BundledBlock[]> {
  const query = new URLSearchParams();
  if (filters?.section_id) query.set('section_id', filters.section_id);
  if (filters?.department) query.set('department', filters.department);

  const queryString = query.toString() ? `?${query.toString()}` : '';
  const url = `${BACKEND_URL}/api/v1/blocks${queryString}`;
  const proxyUrl = `/backend-api/api/v1/blocks${queryString}`;
  const routeUrl = `/api/blocks${queryString}`;

  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, { cache: 'no-store' });
      if (res.ok) return await res.json();
    } catch {
      try {
        const res = await fetch(routeUrl, { cache: 'no-store' });
        if (res.ok) return await res.json();
      } catch {
        console.warn('Backend blocks endpoint not reachable');
      }
    }
  }
  return [];
}

/**
 * Fetch detailed structured explanation for a block (GET /api/v1/blocks/{block_id}/explain)
 */
export async function fetchBlockExplanation(blockId: string): Promise<BlockExplanation | null> {
  const encodedId = encodeURIComponent(blockId);
  const url = `${BACKEND_URL}/api/v1/blocks/${encodedId}/explain`;
  const proxyUrl = `/backend-api/api/v1/blocks/${encodedId}/explain`;
  const routeUrl = `/api/explain/${encodedId}`;

  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      return data.explanation_detail || data.explanation || null;
    }
  } catch {
    try {
      const res = await fetch(proxyUrl, { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();
        return data.explanation_detail || data.explanation || null;
      }
    } catch {
      try {
        const res = await fetch(routeUrl, { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          return data.explanation_detail || data.explanation || null;
        }
      } catch {
        console.warn('Backend explain endpoint not reachable');
      }
    }
  }
  return null;
}

/**
 * Submit Controller block action (APPROVE, REJECT, MODIFY)
 */
export async function submitBlockAction(
  blockId: string,
  action: 'APPROVE' | 'REJECT' | 'MODIFY',
  notes?: string
): Promise<BlockActionResponse | null> {
  const encodedId = encodeURIComponent(blockId);
  const url = `${BACKEND_URL}/api/v1/blocks/${encodedId}/action`;
  const proxyUrl = `/backend-api/api/v1/blocks/${encodedId}/action`;
  const routeUrl = `/api/action/${encodedId}`;

  const payload = {
    action,
    controller_notes: notes || '',
  };

  const reqOptions: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  };

  try {
    const res = await fetch(url, reqOptions);
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, reqOptions);
      if (res.ok) return await res.json();
    } catch {
      try {
        const res = await fetch(routeUrl, reqOptions);
        if (res.ok) return await res.json();
      } catch {
        console.warn('Backend action endpoint not reachable');
      }
    }
  }
  return null;
}

/**
 * Fetch quantitative baseline vs optimized comparison metrics (GET /api/v1/optimizer/comparison)
 */
export async function fetchBaselineComparison(): Promise<BaselineComparison | null> {
  const url = `${BACKEND_URL}/api/v1/optimizer/comparison`;
  const proxyUrl = `/backend-api/api/v1/optimizer/comparison`;

  const reqOptions: RequestInit = {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
  };

  try {
    const res = await fetch(url, reqOptions);
    if (res.ok) return await res.json();
  } catch {
    try {
      const res = await fetch(proxyUrl, reqOptions);
      if (res.ok) return await res.json();
    } catch {
      console.warn('Backend comparison endpoint not reachable');
    }
  }
  return null;
}

