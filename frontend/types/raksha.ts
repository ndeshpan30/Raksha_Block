/**
 * RAKSHA-BLOCK: TypeScript Type Definitions
 * SIH26027 — AI-Powered Indian Railways Maintenance Block Coordination
 */

export type PersonaType = 'controller' | 'planner' | 'station_master';

export type Department = 'ENG' | 'S&T' | 'TRD';
export type UrgencyTier = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type CorridorSlot = 'SLOT_NIGHT' | 'SLOT_EARLY_MORN' | 'SLOT_MIDDAY' | 'SLOT_AFTERNOON';

export interface MaintenanceRequest {
  request_id: string;
  source_system: 'TMS' | 'SMMS' | 'TDMS' | 'COA' | string;
  department: Department | string;
  section_id: string;
  corridor_slot: CorridorSlot | string;
  chainage_start: number;
  chainage_end: number;
  requested_window_start: string;
  requested_window_end: string;
  required_duration_minutes: number;
  work_type: string;
  asset_id: string;
  asset_type: string;
  asset_age_years: number;
  last_maintenance_days_ago: number;
  past_breakdown_count: number;
  gross_million_tonnes: number;
  condition_score: number;
  urgency_category: UrgencyTier | string;
  risk_score?: number;
  requires_power_block: boolean;
  requires_traffic_block: boolean;
  status: 'PENDING' | 'BUNDLED' | 'SCHEDULED' | 'REJECTED' | 'COMPLETED' | string;
  asset_age_or_condition_features?: Record<string, any>;
  asset_condition_features?: Record<string, any>;
}

export interface MergedRequestDetail {
  request_id: string;
  department: Department | string;
  work_type: string;
  asset_id: string;
  asset_type: string;
  chainage_start: number;
  chainage_end: number;
  requested_window_start: string;
  requested_window_end: string;
  required_duration_minutes: number;
  scheduled_start: string;
  scheduled_end: string;
  risk_score: number;
  urgency_tier: UrgencyTier | string;
  requires_power_block: boolean;
  requires_traffic_block: boolean;
}

export interface PriorityReasoning {
  highest_risk_request_id: string;
  highest_risk_asset_id: string;
  highest_risk_score: number;
  highest_risk_department: string;
  highest_risk_work_type: string;
  risk_tier: UrgencyTier | string;
  average_risk_score: number;
  risk_spread: number;
  anchoring_reason: string;
}

export interface WindowBounds {
  earliest_requested_start: string;
  latest_requested_end: string;
  scheduled_start: string;
  scheduled_end: string;
  total_window_slack_minutes: number;
}

export interface ConstraintReasoning {
  spatial_chainage_overlap: boolean;
  spatial_proximity_km: number;
  actual_spatial_gap_km: number;
  enveloping_chainage_span_km: number;
  spatial_overlap_type: 'DIRECT_OVERLAP' | 'ADJACENT_PROXIMITY' | 'BRIDGED_CHAINAGE' | 'SINGLE_ISOLATED' | string;
  window_bounds: WindowBounds;
  corridor_slot: string;
  power_block_required: boolean;
  power_block_driver?: string | null;
  traffic_block_required: boolean;
  traffic_block_driver?: string | null;
  duration_savings_minutes: number;
  key_constraints_applied: string[];
}

export interface AlternativesReasoning {
  separate_possession_minutes: number;
  bundled_possession_minutes: number;
  possession_savings_minutes: number;
  possession_savings_pct: number;
  why_not_scheduled_separately: string;
  why_not_deferred: string;
  alternatives_evaluated: string[];
}

export interface BlockExplanation {
  summary: string;
  merged_requests: MergedRequestDetail[];
  driving_priority: PriorityReasoning;
  driving_constraints: ConstraintReasoning;
  alternatives_considered: AlternativesReasoning;
}

export interface ConstituentRequestSummary {
  request_id: string;
  department: string;
  work_type: string;
  asset_id: string;
  asset_type: string;
  chainage_start: number;
  chainage_end: number;
  requested_window_start: string;
  requested_window_end: string;
  required_duration_minutes: number;
  scheduled_start: string;
  scheduled_end: string;
  risk_score: number;
  requires_power_block: boolean;
  requires_traffic_block: boolean;
}

export interface BundledBlock {
  block_id: string;
  section_id: string;
  corridor_slot: string;
  start_km: number;
  end_km: number;
  scheduled_start: string;
  scheduled_end: string;
  total_duration_minutes: number;
  bundled_request_ids: string[];
  departments_involved: string[];
  power_block_granted: boolean;
  traffic_block_granted: boolean;
  savings_minutes: number;
  explanation_text: string;
  explanation_detail?: BlockExplanation;
  explanation?: BlockExplanation;
  approval_status: 'PROPOSED' | 'APPROVED_BY_CONTROLLER' | 'REJECTED_BY_CONTROLLER' | 'MODIFIED_BY_CONTROLLER' | string;
  constituent_requests?: ConstituentRequestSummary[];
  is_modified?: boolean;
  delta_type?: 'REOPTIMIZED' | 'SHIFTED' | 'URGENCY_CHANGED' | string;
}

export interface BaselineComparison {
  baseline_block_count: number;
  optimized_block_count: number;
  block_count_reduction: number;
  block_count_reduction_pct: number;
  baseline_possession_minutes: number;
  baseline_possession_hours: number;
  optimized_possession_minutes: number;
  optimized_possession_hours: number;
  possession_savings_minutes: number;
  possession_savings_hours: number;
  possession_reduction_pct: number;
  baseline_traffic_halts: number;
  optimized_traffic_halts: number;
  avoided_traffic_halts: number;
  coordinated_bundles_created: number;
  triple_department_bundles: number;
  dual_department_bundles: number;
}

export interface OptimizationPlan {
  status: string;
  total_requests_in: number;
  total_blocks_out: number;
  bundled_blocks_count: number;
  single_blocks_count: number;
  total_original_duration_minutes: number;
  total_bundled_duration_minutes: number;
  total_savings_minutes: number;
  savings_percentage: number;
  solve_time_seconds: number;
  blocks: BundledBlock[];
  reoptimization_mode?: 'FULL' | 'LOCALIZED_DELTA' | string;
  delta_request_ids?: string[];
  affected_blocks_count?: number;
  baseline_comparison?: BaselineComparison;
}

export interface BlockActionResponse {
  block_id: string;
  action: string;
  status: string;
  message: string;
}

export interface SystemHealth {
  status: string;
  service: string;
  version: string;
}
