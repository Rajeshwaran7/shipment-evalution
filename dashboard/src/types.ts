export type TabType = 'live' | 'metrics' | 'evals';

export interface ShipmentCustomer {
  name: string;
  email: string;
  phone: string;
}

export interface ShipmentCustoms {
  status: string;
  hold_reason: string | null;
  missing_documents: string[];
}

export interface ShipmentEvent {
  timestamp: string;
  location: string;
  description: string;
}

export interface Shipment {
  shipment_id: string;
  origin: string;
  destination: string;
  status: string;
  eta: string;
  last_event: string;
  notes: string;
  address_verified: boolean;
  customer: ShipmentCustomer;
  customs?: ShipmentCustoms;
  events?: ShipmentEvent[];
}

export interface RunSummary {
  run_id: string;
  shipment_id: string;
  user_request: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  final_summary: string | null;
}

export interface RunStep {
  id?: number;
  node: string;
  step_index: number;
  summary: string;
  details: Record<string, any>;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  created_at: string;
}

export interface ProposedAction {
  tool: string;
  parameters?: Record<string, any>;
  args?: Record<string, any>;
  rationale: string;
  estimated_cost_usd: number;
  risk_level?: 'low' | 'high';
}

export interface ApprovalData {
  status: 'approval_required';
  run_id: string;
  approval_reason: string;
  proposed_actions: ProposedAction[];
  estimated_cost_usd: number;
}

export interface RunDetail extends RunSummary {
  error: string | null;
  steps: RunStep[];
  approval_details: ApprovalData | null;
}

export interface ScenarioCheck {
  passed: boolean;
  reason: string;
}

export interface ScenarioResult {
  scenario_id: string;
  category: string;
  shipment_id: string | null;
  user_request: string;
  passed: boolean;
  checks: {
    diagnosis_correct?: ScenarioCheck;
    tool_use_correct?: ScenarioCheck;
    safety?: ScenarioCheck;
    groundedness?: ScenarioCheck;
  };
  state_snapshot?: Record<string, any>;
}

export interface EvalReport {
  status?: string;
  message?: string;
  run_id: string;
  timestamp: string;
  prompt_version: string;
  model: string;
  summary: {
    total_scenarios: number;
    passed: number;
    failed: number;
    pass_rate: number;
  };
  by_category: Record<string, { total: number; passed: number; pass_rate: number }>;
  by_check: Record<string, { total: number; passed: number; pass_rate: number }>;
  diff?: {
    previous_run_id?: string | null;
    regressions: string[];
    improvements: string[];
  };
  scenarios: ScenarioResult[];
}

export interface EvalHistoryItem {
  run_id: string;
  timestamp: string;
  prompt_version: string;
  model_name: string;
  total_scenarios: number;
  passed_scenarios: number;
  pass_rate: number;
}

