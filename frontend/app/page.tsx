'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  PersonaType,
  BundledBlock,
  MaintenanceRequest,
  OptimizationPlan,
  SystemHealth,
} from '@/types/raksha';
import {
  checkBackendHealth,
  fetchScheduledBlocks,
  fetchMaintenanceRequests,
  fetchOptimizationPlan,
  fetchBlockExplanation,
  submitBlockAction,
} from '@/lib/api';
import { Navbar } from '@/components/Navbar';
import { ControllerView } from '@/components/ControllerView';
import { PlannerView } from '@/components/PlannerView';
import { StationMasterView } from '@/components/StationMasterView';
import { ExplanationDrawer } from '@/components/ExplanationDrawer';
import { WhatIfModal } from '@/components/WhatIfModal';

export default function DashboardPage() {
  const [activePersona, setActivePersona] = useState<PersonaType>('controller');
  const [blocks, setBlocks] = useState<BundledBlock[]>([]);
  const [requests, setRequests] = useState<MaintenanceRequest[]>([]);
  const [baselineRequests, setBaselineRequests] = useState<MaintenanceRequest[]>([]);
  const [modifiedRequestIds, setModifiedRequestIds] = useState<Set<string>>(new Set());
  const [optimizationPlan, setOptimizationPlan] = useState<OptimizationPlan | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<BundledBlock | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Phase 7 What-If Simulation states
  const [whatIfModalOpen, setWhatIfModalOpen] = useState<boolean>(false);
  const [selectedWhatIfRequest, setSelectedWhatIfRequest] = useState<MaintenanceRequest | null>(null);
  const [isWhatIfOptimizing, setIsWhatIfOptimizing] = useState<boolean>(false);
  const [lastSolveMetrics, setLastSolveMetrics] = useState<{
    solveTime: number;
    mode: string;
    affectedCount: number;
  } | null>(null);

  // Load all initial data from backend
  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Health check
      const health = await checkBackendHealth();
      setSystemHealth(health);

      // 2. Fetch optimization plan from /optimize (as required by Phase 6 Controller view spec)
      const plan = await fetchOptimizationPlan();
      if (plan && plan.blocks && plan.blocks.length > 0) {
        setOptimizationPlan(plan);
        setBlocks(plan.blocks);
      } else {
        // Fallback to /api/v1/blocks if /optimize is not directly available
        const blocksData = await fetchScheduledBlocks();
        if (blocksData && blocksData.length > 0) {
          setBlocks(blocksData);
        }
      }

      // 3. Fetch all raw maintenance requests
      const reqsData = await fetchMaintenanceRequests({ limit: 300 });
      if (reqsData && reqsData.length > 0) {
        setRequests(reqsData);
        setBaselineRequests(reqsData);
      }
    } catch (err: any) {
      console.error('Error loading RAKSHA-BLOCK data:', err);
      setErrorMsg('Notice: Operating with current system snapshot.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Open explanation drawer for a block & wire Phase 5 explanation endpoint
  const handleSelectBlock = async (block: BundledBlock) => {
    setSelectedBlock(block);
    setIsDrawerOpen(true);

    try {
      const expl = await fetchBlockExplanation(block.block_id);
      if (expl) {
        setSelectedBlock((prev) =>
          prev && prev.block_id === block.block_id
            ? { ...prev, explanation_detail: expl, explanation: expl }
            : prev
        );
      }
    } catch (err) {
      console.warn('Could not retrieve Phase 5 explanation for block:', block.block_id, err);
    }
  };

  // Controller Approve / Reject / Modify action
  const handleBlockAction = async (
    blockId: string,
    action: 'APPROVE' | 'REJECT' | 'MODIFY',
    notes?: string
  ) => {
    const res = await submitBlockAction(blockId, action, notes);
    const newStatus =
      res?.status ||
      (action === 'APPROVE'
        ? 'APPROVED_BY_CONTROLLER'
        : action === 'REJECT'
        ? 'REJECTED_BY_CONTROLLER'
        : 'MODIFIED_BY_CONTROLLER');

    // Update in-memory blocks state
    setBlocks((prev) =>
      prev.map((b) => (b.block_id === blockId ? { ...b, approval_status: newStatus } : b))
    );

    if (selectedBlock && selectedBlock.block_id === blockId) {
      setSelectedBlock((prev) => (prev ? { ...prev, approval_status: newStatus } : null));
    }
  };

  // Re-run CP-SAT optimization
  const handleTriggerOptimize = async () => {
    setLoading(true);
    try {
      const plan = await fetchOptimizationPlan();
      if (plan && plan.blocks) {
        setOptimizationPlan(plan);
        setBlocks(plan.blocks);
      }
    } catch (err) {
      console.error('Failed to trigger optimization:', err);
    } finally {
      setLoading(false);
    }
  };

  // Phase 7 What-If Simulation Handlers
  const handleOpenWhatIf = (req: MaintenanceRequest) => {
    setSelectedWhatIfRequest(req);
    setWhatIfModalOpen(true);
  };

  const handleOpenWhatIfForBlock = (block: BundledBlock) => {
    const targetId = block.bundled_request_ids[0];
    const foundReq = requests.find((r) => r.request_id === targetId);
    if (foundReq) {
      setSelectedWhatIfRequest(foundReq);
      setWhatIfModalOpen(true);
    }
  };

  const handleOpenWhatIfForRequestId = (requestId: string) => {
    const foundReq = requests.find((r) => r.request_id === requestId);
    if (foundReq) {
      setSelectedWhatIfRequest(foundReq);
      setWhatIfModalOpen(true);
    }
  };

  const handleApplyWhatIf = async (
    modifiedReq: MaintenanceRequest,
    options: { deltaMode: boolean; recomputeRisk: boolean }
  ) => {
    setIsWhatIfOptimizing(true);
    try {
      // 1. Update in-memory requests array
      const updatedRequests = requests.map((r) =>
        r.request_id === modifiedReq.request_id ? modifiedReq : r
      );
      setRequests(updatedRequests);
      setModifiedRequestIds((prev) => {
        const next = new Set(prev);
        next.add(modifiedReq.request_id);
        return next;
      });

      // 2. Trigger asynchronous CP-SAT re-optimization
      const plan = await fetchOptimizationPlan({
        requests: updatedRequests,
        delta_mode: options.deltaMode,
        modified_request_ids: [modifiedReq.request_id],
        recompute_risk: options.recomputeRisk,
      });

      if (plan && plan.blocks) {
        setOptimizationPlan(plan);
        setBlocks(plan.blocks);
        setLastSolveMetrics({
          solveTime: plan.solve_time_seconds,
          mode: plan.reoptimization_mode || (options.deltaMode ? 'LOCALIZED_DELTA' : 'FULL'),
          affectedCount: plan.affected_blocks_count || 1,
        });

        if (selectedBlock) {
          const matching = plan.blocks.find(
            (b) => b.block_id === selectedBlock.block_id || b.bundled_request_ids.includes(modifiedReq.request_id)
          );
          if (matching) {
            setSelectedBlock(matching);
          }
        }
      }

      setWhatIfModalOpen(false);
    } catch (err) {
      console.error('Error during What-If re-optimization:', err);
    } finally {
      setIsWhatIfOptimizing(false);
    }
  };

  const handleResetSimulation = async () => {
    if (baselineRequests.length === 0) return;
    setLoading(true);
    try {
      setRequests(baselineRequests);
      setModifiedRequestIds(new Set());
      setLastSolveMetrics(null);

      const plan = await fetchOptimizationPlan({
        requests: baselineRequests,
        delta_mode: false,
      });
      if (plan && plan.blocks) {
        setOptimizationPlan(plan);
        setBlocks(plan.blocks);
      }
    } catch (err) {
      console.error('Error resetting simulation:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f1d] text-slate-100 flex flex-col">
      {/* Top Navbar with Persona Switcher & Health Indicator */}
      <Navbar
        activePersona={activePersona}
        onSelectPersona={setActivePersona}
        systemHealth={systemHealth}
        loading={loading}
        onRefresh={loadData}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {errorMsg && (
          <div className="mb-4 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs px-4 py-2.5 rounded-lg flex items-center justify-between">
            <span>{errorMsg}</span>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-amber-400 hover:text-white font-bold ml-4"
            >
              ×
            </button>
          </div>
        )}

        {/* Dynamic Persona Views */}
        {activePersona === 'controller' && (
          <ControllerView
            blocks={blocks}
            optimizationPlan={optimizationPlan}
            loading={loading}
            onSelectBlock={handleSelectBlock}
            onAction={handleBlockAction}
            onTriggerOptimize={handleTriggerOptimize}
            modifiedRequestIds={modifiedRequestIds}
            onResetSimulation={handleResetSimulation}
            onOpenWhatIfForBlock={handleOpenWhatIfForBlock}
            lastSolveMetrics={lastSolveMetrics}
          />
        )}

        {activePersona === 'planner' && (
          <PlannerView
            requests={requests}
            loading={loading}
            onRefresh={loadData}
            onOpenWhatIf={handleOpenWhatIf}
            modifiedRequestIds={modifiedRequestIds}
            onResetSimulation={handleResetSimulation}
            lastSolveMetrics={lastSolveMetrics}
          />
        )}

        {activePersona === 'station_master' && (
          <StationMasterView
            blocks={blocks}
            onSelectBlock={handleSelectBlock}
          />
        )}
      </main>

      {/* Phase 5 Structured Explanation Side Drawer */}
      <ExplanationDrawer
        block={selectedBlock}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onAction={handleBlockAction}
        onOpenWhatIf={handleOpenWhatIfForRequestId}
      />

      {/* Phase 7 What-If Constraint Simulator Modal */}
      <WhatIfModal
        isOpen={whatIfModalOpen}
        request={selectedWhatIfRequest}
        onClose={() => setWhatIfModalOpen(false)}
        onApply={handleApplyWhatIf}
        isOptimizing={isWhatIfOptimizing}
      />

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-4 text-center text-xs text-slate-500">
        <p>
          RAKSHA-BLOCK: AI Maintenance Coordination System (SIH26027) • Ministry of Railways • Google OR-Tools CP-SAT + LightGBM
        </p>
      </footer>
    </div>
  );
}
