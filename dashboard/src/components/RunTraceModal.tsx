import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  DollarSign,
  Loader2,
  Terminal,
  X,
} from 'lucide-react';
import { fetchRunTrace } from '../api';
import { RunDetail } from '../types';

interface RunTraceModalProps {
  runId: string | null;
  onClose: () => void;
}

export const RunTraceModal: React.FC<RunTraceModalProps> = ({ runId, onClose }) => {
  const [trace, setTrace] = useState<RunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (!runId) return;
    setIsLoading(true);
    setError(null);
    fetchRunTrace(runId)
      .then((data) => {
        setTrace(data);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load trace');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [runId]);

  if (!runId) return null;

  const toggleStep = (idx: number) => {
    setExpandedSteps((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white font-mono">{runId}</h3>
                {trace && (
                  <span
                    className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                      trace.status === 'completed'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : trace.status === 'paused'
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                        : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    }`}
                  >
                    {trace.status}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Shipment: <strong className="font-mono text-emerald-400">{trace?.shipment_id}</strong>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1 text-xs">
          {isLoading && (
            <div className="py-12 flex flex-col items-center justify-center space-y-2 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
              <span>Fetching full run execution trace...</span>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-300 flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {trace && (
            <>
              {/* Telemetry bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-center font-mono">
                <div>
                  <span className="text-[10px] text-slate-500 block">Duration</span>
                  <span className="font-bold text-slate-200">
                    {trace.duration_ms ? `${Math.round(trace.duration_ms)}ms` : '-'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Total Tokens</span>
                  <span className="font-bold text-slate-200">
                    {trace.input_tokens + trace.output_tokens}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Estimated Cost</span>
                  <span className="font-bold text-emerald-400">
                    ${trace.cost_usd ? trace.cost_usd.toFixed(4) : '0.0000'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Steps Recorded</span>
                  <span className="font-bold text-slate-200">{trace.steps?.length || 0}</span>
                </div>
              </div>

              {/* User Inquiry */}
              <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
                <span className="font-semibold text-slate-400 uppercase text-[10px] block mb-1">
                  User Inquiry
                </span>
                <p className="text-slate-200">{trace.user_request}</p>
              </div>

              {/* Final Summary */}
              {trace.final_summary && (
                <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-1">
                  <span className="font-semibold text-emerald-400 uppercase text-[10px] block">
                    Final Resolution Summary
                  </span>
                  <p className="text-slate-200 leading-relaxed font-sans">{trace.final_summary}</p>
                </div>
              )}

              {/* Steps list */}
              <div className="space-y-2 pt-2">
                <span className="font-semibold text-slate-400 uppercase text-[10px] tracking-wider block">
                  Workflow Execution Trace
                </span>
                {trace.steps?.map((st, sIdx) => {
                  const isExp = !!expandedSteps[sIdx];
                  const toolCalls = st.details?.tool_calls || [];
                  const warnings = st.details?.warnings || [];

                  return (
                    <div
                      key={sIdx}
                      className="rounded-xl bg-slate-950 border border-slate-800 overflow-hidden"
                    >
                      <div
                        onClick={() => toggleStep(sIdx)}
                        className="p-3 flex items-center justify-between cursor-pointer hover:bg-slate-900/50"
                      >
                        <div className="flex items-center space-x-2.5">
                          <span className="w-5 h-5 rounded bg-slate-800 text-[10px] font-mono flex items-center justify-center text-slate-400">
                            {st.step_index}
                          </span>
                          <span className="font-mono text-xs font-bold text-emerald-400 uppercase">
                            {st.node}
                          </span>
                          <span className="text-xs text-slate-300 truncate max-w-md">
                            {st.summary}
                          </span>
                        </div>

                        <div className="flex items-center space-x-2 text-slate-500 text-[10px] font-mono">
                          <span>{Math.round(st.latency_ms)}ms</span>
                          {isExp ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </div>
                      </div>

                      {warnings.length > 0 && (
                        <div className="px-3 py-1.5 bg-rose-950/30 border-t border-b border-rose-500/20 text-[10px] text-rose-300">
                          {warnings.join(', ')}
                        </div>
                      )}

                      {isExp && (
                        <div className="p-3 border-t border-slate-800 bg-slate-900/40 space-y-2">
                          {toolCalls.length > 0 && (
                            <div className="space-y-1">
                              <span className="text-[10px] text-slate-400 font-semibold block uppercase">
                                Tools Called:
                              </span>
                              {toolCalls.map((tc: any, i: number) => (
                                <div key={i} className="p-2 rounded bg-slate-950 border border-slate-800 font-mono text-[10px]">
                                  <strong className="text-amber-400">{tc.tool_name || tc.tool}:</strong>{' '}
                                  {JSON.stringify(tc.arguments || tc.parameters)}
                                </div>
                              ))}
                            </div>
                          )}
                          <pre className="text-[10px] font-mono text-slate-400 bg-slate-950 p-2.5 rounded border border-slate-800 overflow-x-auto max-h-48">
                            {JSON.stringify(st.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

