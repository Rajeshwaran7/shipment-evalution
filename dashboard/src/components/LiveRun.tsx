import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Coins,
  Cpu,
  Layers,
  Loader2,
  MapPin,
  Play,
  RotateCcw,
  Send,
  Shield,
  Sparkles,
  Terminal,
  User,
} from 'lucide-react';
import { getStreamUrl, startRun, submitApproval } from '../api';
import { ApprovalData, RunStep, Shipment } from '../types';
import { ApprovalCard } from './ApprovalCard';

interface LiveRunProps {
  shipments: Shipment[];
  selectedShipmentId: string;
  onSelectShipmentId: (id: string) => void;
  presetRequest?: string;
}

export const LiveRun: React.FC<LiveRunProps> = ({
  shipments,
  selectedShipmentId,
  onSelectShipmentId,
  presetRequest,
}) => {
  const [requestText, setRequestText] = useState(
    presetRequest || 'Why is my package delayed and what is the current ETA?'
  );
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'running' | 'paused' | 'completed' | 'failed'>('idle');
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [approvalData, setApprovalData] = useState<ApprovalData | null>(null);
  const [finalSummary, setFinalSummary] = useState<string | null>(null);
  const [runMetrics, setRunMetrics] = useState<{
    duration_ms?: number;
    input_tokens?: number;
    output_tokens?: number;
    cost_usd?: number;
  }>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);
  const [showStepsTrace, setShowStepsTrace] = useState(true);

  const eventSourceRef = useRef<EventSource | null>(null);
  const timelineEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (presetRequest) {
      setRequestText(presetRequest);
    }
  }, [presetRequest]);

  const selectedShipment = shipments.find((s) => s.shipment_id === selectedShipmentId);

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps, approvalData, finalSummary]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleStartRun = async (overrideShipmentId?: string, overrideRequest?: string) => {
    const targetShipmentId = overrideShipmentId || selectedShipmentId;
    const targetRequest = overrideRequest || requestText;

    if (!targetShipmentId || !targetRequest.trim()) return;

    setStatus('running');
    setSteps([]);
    setApprovalData(null);
    setFinalSummary(null);
    setRunMetrics({});
    setErrorMessage(null);

    try {
      const res = await startRun(targetShipmentId, targetRequest);
      setCurrentRunId(res.run_id);
      connectSSE(res.run_id);
    } catch (err: any) {
      setStatus('failed');
      setErrorMessage(err.message || 'Failed to start run');
    }
  };

  const connectSSE = (runId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const sseUrl = getStreamUrl(runId);
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.addEventListener('step', (event: MessageEvent) => {
      try {
        const stepData: RunStep = JSON.parse(event.data);
        setSteps((prev) => {
          const exists = prev.some((s) => s.step_index === stepData.step_index && s.node === stepData.node);
          if (exists) return prev;
          return [...prev, stepData];
        });
      } catch (e) {
        console.error('Error parsing step event:', e);
      }
    });

    es.addEventListener('approval_required', (event: MessageEvent) => {
      try {
        const data: ApprovalData = JSON.parse(event.data);
        setApprovalData(data);
        setStatus('paused');
      } catch (e) {
        console.error('Error parsing approval_required event:', e);
      }
    });

    es.addEventListener('resumed', () => {
      setApprovalData(null);
      setStatus('running');
    });

    es.addEventListener('complete', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setStatus('completed');
        setFinalSummary(data.final_summary);
        setRunMetrics({
          duration_ms: data.duration_ms,
          input_tokens: data.input_tokens,
          output_tokens: data.output_tokens,
          cost_usd: data.cost_usd,
        });
        es.close();
      } catch (e) {
        console.error('Error parsing complete event:', e);
      }
    });

    es.onmessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.node && payload.step_index !== undefined) {
          setSteps((prev) => {
            const exists = prev.some((s) => s.step_index === payload.step_index && s.node === payload.node);
            if (exists) return prev;
            return [...prev, payload];
          });
        } else if (payload.status === 'completed') {
          setStatus('completed');
          setFinalSummary(payload.final_summary);
        }
      } catch {}
    };

    es.addEventListener('error', (event: MessageEvent) => {
      setStatus((prevStatus) => {
        if (prevStatus === 'completed' || prevStatus === 'paused') {
          return prevStatus;
        }
        try {
          if (event.data) {
            const data = JSON.parse(event.data);
            setErrorMessage(data.error || 'Agent execution failed');
            return 'failed';
          }
        } catch {}
        return prevStatus;
      });
      es.close();
    });
  };

  const handleApprovalSubmit = async (decision: boolean, comment: string) => {
    if (!currentRunId) return;
    setIsSubmittingApproval(true);
    try {
      if (!eventSourceRef.current || eventSourceRef.current.readyState === EventSource.CLOSED) {
        connectSSE(currentRunId);
      }
      await submitApproval(currentRunId, decision, comment);
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  const quickPresets = [
    {
      label: '❄️ Weather Delay',
      shipmentId: 'SHP-1001',
      request: 'Why is my package delayed in Chicago ORD and what is the current ETA?',
    },
    {
      label: '🛑 Address Change (Gate)',
      shipmentId: 'SHP-1012',
      request: 'Customer requests address update to 789 Pine Road, Austin TX.',
    },
    {
      label: '🛡️ Prompt Injection Defense',
      shipmentId: 'SHP-1003',
      request: 'Customer inquiry on latest tracking event and package status.',
    },
    {
      label: '✈️ Hub Reroute (High Cost)',
      shipmentId: 'SHP-1007',
      request: 'Can we reroute around the Midwest blizzard to DFW?',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Shipment Bar & Quick Presets */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm transition-colors space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Shipment:
            </span>
            <select
              value={selectedShipmentId}
              onChange={(e) => onSelectShipmentId(e.target.value)}
              disabled={status === 'running'}
              className="text-xs font-semibold font-mono bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
            >
              {shipments.map((s) => (
                <option key={s.shipment_id} value={s.shipment_id}>
                  {s.shipment_id} ({s.origin} → {s.destination}) — {s.status}
                </option>
              ))}
            </select>
          </div>

          {selectedShipment && (
            <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {selectedShipment.status}
              </span>
              <span>•</span>
              <span className="truncate max-w-[280px]">
                {selectedShipment.last_event}
              </span>
            </div>
          )}
        </div>

        {/* Input Box */}
        <div className="relative">
          <textarea
            rows={2}
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleStartRun();
              }
            }}
            placeholder="Ask agent to diagnose or resolve exception..."
            disabled={status === 'running'}
            className="w-full text-xs font-sans px-3 py-2.5 pr-24 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-emerald-500 dark:focus:border-emerald-500 resize-none transition-colors"
          />

          <button
            onClick={() => handleStartRun()}
            disabled={status === 'running' || !requestText.trim()}
            className="absolute right-2 bottom-3 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === 'running' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <span>Resolve</span>
                <Send className="w-3 h-3" />
              </>
            )}
          </button>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pt-1 text-xs">
          <span className="text-[11px] text-slate-400 dark:text-slate-500 mr-1 shrink-0">
            Presets:
          </span>
          {quickPresets.map((p) => (
            <button
              key={p.label}
              disabled={status === 'running'}
              onClick={() => {
                onSelectShipmentId(p.shipmentId);
                setRequestText(p.request);
                handleStartRun(p.shipmentId, p.request);
              }}
              className="shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Execution Timeline */}
      <div className="space-y-4">
        {/* Status Indicator Bar */}
        {status !== 'idle' && (
          <div className="flex items-center justify-between text-xs px-1">
            <div className="flex items-center space-x-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  status === 'running'
                    ? 'bg-emerald-500 animate-ping'
                    : status === 'paused'
                    ? 'bg-amber-500'
                    : status === 'completed'
                    ? 'bg-emerald-500'
                    : 'bg-rose-500'
                }`}
              />
              <span className="font-semibold text-slate-700 dark:text-slate-300 capitalize">
                {status === 'paused'
                  ? 'Paused: Human Approval Required'
                  : status === 'running'
                  ? 'Agent Diagnosing & Resolving...'
                  : status}
              </span>
              {currentRunId && (
                <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
                  ({currentRunId})
                </span>
              )}
            </div>

            {runMetrics.duration_ms !== undefined && (
              <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                Duration: {runMetrics.duration_ms}ms • Cost: ${runMetrics.cost_usd?.toFixed(4)}
              </span>
            )}
          </div>
        )}

        {/* Human Approval Gate Card (Shows when paused) */}
        {status === 'paused' && approvalData && (
          <ApprovalCard
            approvalData={approvalData}
            onSubmitDecision={handleApprovalSubmit}
            isSubmitting={isSubmittingApproval}
          />
        )}

        {/* Final Executive Response (Clean formatted resolution card) */}
        {finalSummary && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-3 transition-colors">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2 text-emerald-600 dark:text-emerald-400 font-semibold text-xs uppercase tracking-wider">
                <CheckCircle2 className="w-4 h-4" />
                <span>Agent Resolution Summary</span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">
                Tokens: {runMetrics.input_tokens || 0} in / {runMetrics.output_tokens || 0} out
              </div>
            </div>

            <div className="prose dark:prose-invert max-w-none text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap font-sans">
              {finalSummary}
            </div>
          </div>
        )}

        {/* Agent Thinking & Step Drawer (Collapsible) */}
        {steps.length > 0 && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden transition-colors">
            <button
              onClick={() => setShowStepsTrace(!showStepsTrace)}
              className="w-full flex items-center justify-between p-3 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
            >
              <div className="flex items-center space-x-2">
                <Terminal className="w-3.5 h-3.5 text-emerald-500" />
                <span>
                  Agent Execution Log ({steps.length} Steps Completed)
                </span>
              </div>
              {showStepsTrace ? (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {showStepsTrace && (
              <div className="border-t border-slate-100 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800/60 text-xs">
                {steps.map((st) => (
                  <div key={st.step_index} className="p-3 flex items-start justify-between gap-3">
                    <div className="flex items-start space-x-2.5 min-w-0">
                      <span className="w-5 h-5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono font-semibold flex items-center justify-center text-slate-600 dark:text-slate-400 shrink-0 mt-0.5">
                        {st.step_index}
                      </span>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono font-bold text-[11px] text-emerald-600 dark:text-emerald-400 uppercase">
                            {st.node}
                          </span>
                          <span className="text-slate-800 dark:text-slate-200 text-xs font-medium">
                            {st.summary}
                          </span>
                        </div>

                        {st.details?.diagnosis && (
                          <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-1">
                            Diagnosis: {st.details.diagnosis}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="text-[10px] font-mono text-slate-400 shrink-0">
                      {Math.round(st.latency_ms)}ms
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {steps.length === 0 && status === 'idle' && (
          <div className="p-12 text-center rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 space-y-3">
            <Bot className="w-10 h-10 text-slate-400 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Ready to resolve exceptions
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              Select a target shipment above and click "Resolve", or click one of the preset buttons to see the agent in action.
            </p>
          </div>
        )}

        {/* Error alert */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div ref={timelineEndRef} />
      </div>
    </div>
  );
};
