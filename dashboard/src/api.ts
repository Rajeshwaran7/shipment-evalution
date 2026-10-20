import {
  ApprovalData,
  EvalHistoryItem,
  EvalReport,
  RunDetail,
  RunSummary,
  Shipment,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '';

export async function checkHealth(): Promise<{ status: string; service: string }> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { status: 'error', service: 'Disconnected' };
  }
}

export async function fetchShipments(): Promise<Shipment[]> {
  const res = await fetch(`${API_BASE}/shipments`);
  if (!res.ok) {
    throw new Error(`Failed to fetch shipments: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function startRun(
  shipment_id: string,
  request: string
): Promise<{ run_id: string; shipment_id: string; status: string; started_at: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ shipment_id, request }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to start run: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function submitApproval(
  run_id: string,
  decision: boolean,
  comment = ''
): Promise<{ run_id: string; status: string; decision: boolean; resumed_at: string }> {
  const res = await fetch(`${API_BASE}/runs/${run_id}/approval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, comment }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to submit approval: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchRuns(limit = 50): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/runs?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch runs: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchRunTrace(run_id: string): Promise<RunDetail> {
  const res = await fetch(`${API_BASE}/runs/${run_id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch run trace: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchLatestEvals(): Promise<EvalReport> {
  const res = await fetch(`${API_BASE}/evals/latest`);
  if (!res.ok) {
    throw new Error(`Failed to fetch latest evals: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchEvalsHistory(limit = 20): Promise<EvalHistoryItem[]> {
  const res = await fetch(`${API_BASE}/evals/history?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch eval history: HTTP ${res.status}`);
  }
  return await res.json();
}

export function getStreamUrl(run_id: string): string {
  return `${API_BASE}/runs/${run_id}/stream`;
}

