import React, { useState } from 'react';
import {
  Activity,
  AlertOctagon,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  History,
  Layers,
  RefreshCw,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { EvalHistoryItem, EvalReport, ScenarioResult } from '../types';

interface EvalsProps {
  evalReport: EvalReport | null;
  evalHistory: EvalHistoryItem[];
  onRefresh: () => void;
  isLoading: boolean;
}

export const Evals: React.FC<EvalsProps> = ({
  evalReport,
  evalHistory,
  onRefresh,
  isLoading,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [expandedScenarios, setExpandedScenarios] = useState<Record<string, boolean>>({});

  if (!evalReport || evalReport.status === 'no_results') {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <Activity className="w-12 h-12 text-slate-600 mx-auto" />
        <h3 className="text-base font-bold text-white">No Benchmark Evaluations Found</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Execute the eval harness in terminal to generate benchmark reports:
        </p>
        <code className="inline-block bg-slate-950 px-4 py-2 rounded-lg border border-slate-800 font-mono text-emerald-400 text-xs">
          python -m evals.run --prompt-version v1
        </code>
        <div>
          <button
            onClick={onRefresh}
            className="mt-4 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-bold"
          >
            Refresh Benchmark
          </button>
        </div>
      </div>
    );
  }

  const { summary, by_category, by_check, diff, scenarios, prompt_version, model } = evalReport;

  const toggleScenario = (id: string) => {
    setExpandedScenarios((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredScenarios = scenarios.filter((s) => {
    if (selectedCategory === 'all') return true;
    return s.category === selectedCategory;
  });

  return (
    <div className="space-y-6">
      {/* Benchmark Header Summary */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-bold text-lg text-white">Evaluation Benchmark Report</span>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Prompt: {prompt_version}
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              {model}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            25 multi-domain scenarios evaluated against strict correctness, safety, and groundedness rubrics.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 uppercase font-semibold block">
              Overall Pass Rate
            </span>
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {summary.pass_rate.toFixed(1)}%
            </span>
          </div>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
            title="Refresh Evaluation"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Regression & Improvement Diff Alert (v1 vs v2 / previous) */}
      {diff && (diff.regressions?.length > 0 || diff.improvements?.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Regressions */}
          <div
            className={`p-4 rounded-xl border ${
              diff.regressions.length > 0
                ? 'bg-rose-950/20 border-rose-500/40 text-rose-300'
                : 'bg-slate-900/40 border-slate-800 text-slate-400'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5">
                <ArrowDownRight className="w-4 h-4 text-rose-400" />
                <span>Regressions vs Previous ({diff.regressions.length})</span>
              </span>
              <span className="text-[10px] font-mono">
                Prev: {diff.previous_run_id?.slice(0, 14)}
              </span>
            </div>
            {diff.regressions.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {diff.regressions.map((reg) => (
                  <span
                    key={reg}
                    className="font-mono text-[11px] px-2 py-0.5 rounded bg-rose-950 border border-rose-500/40 text-rose-200"
                  >
                    {reg}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-1">Zero regressions detected!</p>
            )}
          </div>

          {/* Improvements */}
          <div
            className={`p-4 rounded-xl border ${
              diff.improvements.length > 0
                ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
                : 'bg-slate-900/40 border-slate-800 text-slate-400'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5">
                <ArrowUpRight className="w-4 h-4 text-emerald-400" />
                <span>Improvements vs Previous ({diff.improvements.length})</span>
              </span>
              <span className="text-[10px] font-mono">
                Prev: {diff.previous_run_id?.slice(0, 14)}
              </span>
            </div>
            {diff.improvements.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {diff.improvements.map((imp) => (
                  <span
                    key={imp}
                    className="font-mono text-[11px] px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-200"
                  >
                    {imp}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-1">Consistent with previous benchmark.</p>
            )}
          </div>
        </div>
      )}

      {/* Per-Check Breakdown Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(by_check || {}).map(([checkName, checkStat]) => {
          const passRate = checkStat.pass_rate;
          return (
            <div
              key={checkName}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  {checkName.replace(/_/g, ' ')}
                </span>
                <span
                  className={`text-xs font-mono font-bold ${
                    passRate >= 80
                      ? 'text-emerald-400'
                      : passRate >= 50
                      ? 'text-amber-400'
                      : 'text-rose-400'
                  }`}
                >
                  {passRate.toFixed(1)}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    passRate >= 80
                      ? 'bg-emerald-500'
                      : passRate >= 50
                      ? 'bg-amber-500'
                      : 'bg-rose-500'
                  }`}
                  style={{ width: `${passRate}%` }}
                />
              </div>

              <div className="text-[10px] text-slate-500 flex justify-between">
                <span>{checkStat.passed} passed</span>
                <span>{checkStat.total} total</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Category Breakdown Cards */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          Category Performance Breakdown
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(by_category || {}).map(([catName, catStat]) => {
            const isSelected = selectedCategory === catName;
            return (
              <button
                key={catName}
                onClick={() => setSelectedCategory(isSelected ? 'all' : catName)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-emerald-500/15 border-emerald-500/50 shadow-sm'
                    : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <span className="text-[11px] font-semibold text-slate-300 uppercase block truncate">
                  {catName}
                </span>
                <span className="text-base font-bold font-mono text-emerald-400 mt-1 block">
                  {catStat.pass_rate.toFixed(0)}%
                </span>
                <span className="text-[10px] text-slate-500 block">
                  {catStat.passed}/{catStat.total} passed
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Scenario Explorer List */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Scenarios Explorer ({filteredScenarios.length} {selectedCategory !== 'all' ? `in ${selectedCategory}` : 'Total'})
            </h3>
            <p className="text-[11px] text-slate-500">
              Inspect test criteria, check decisions, and LLM reasoning snapshots
            </p>
          </div>

          {selectedCategory !== 'all' && (
            <button
              onClick={() => setSelectedCategory('all')}
              className="text-[11px] text-emerald-400 underline font-medium"
            >
              Reset to all ({scenarios.length})
            </button>
          )}
        </div>

        <div className="space-y-2">
          {filteredScenarios.map((sc) => {
            const isExpanded = !!expandedScenarios[sc.scenario_id];
            return (
              <div
                key={sc.scenario_id}
                className="rounded-xl bg-slate-950/80 border border-slate-800/90 overflow-hidden"
              >
                {/* Header */}
                <div
                  onClick={() => toggleScenario(sc.scenario_id)}
                  className="p-3.5 flex items-center justify-between cursor-pointer select-none hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    <span
                      className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                        sc.passed ? 'bg-emerald-400' : 'bg-rose-500'
                      }`}
                    />
                    <span className="font-mono text-xs font-bold text-slate-200">
                      {sc.scenario_id}
                    </span>
                    <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {sc.category}
                    </span>
                    {sc.shipment_id && (
                      <span className="text-[11px] font-mono text-emerald-400 hidden sm:inline">
                        {sc.shipment_id}
                      </span>
                    )}
                    <span className="text-xs text-slate-300 font-medium truncate max-w-md">
                      "{sc.user_request}"
                    </span>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0">
                    <span
                      className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                        sc.passed
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      }`}
                    >
                      {sc.passed ? 'PASSED' : 'FAILED'}
                    </span>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                </div>

                {/* Expanded Check Details */}
                {isExpanded && (
                  <div className="p-4 border-t border-slate-800 bg-slate-900/60 space-y-3 text-xs">
                    <span className="font-semibold text-slate-400 uppercase text-[10px] tracking-wider block">
                      Check Results:
                    </span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {Object.entries(sc.checks || {}).map(([checkKey, checkVal]) => (
                        <div
                          key={checkKey}
                          className={`p-2.5 rounded-lg border flex items-start space-x-2 ${
                            checkVal.passed
                              ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-200'
                              : 'bg-rose-950/20 border-rose-500/30 text-rose-200'
                          }`}
                        >
                          {checkVal.passed ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                          )}
                          <div>
                            <span className="font-mono text-[11px] font-bold uppercase block">
                              {checkKey}
                            </span>
                            <span className="text-[11px] text-slate-300 font-sans">
                              {checkVal.reason}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {sc.state_snapshot && (
                      <div className="mt-2">
                        <span className="font-semibold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">
                          Agent State Snapshot:
                        </span>
                        <pre className="text-[10px] font-mono text-slate-400 bg-slate-950 p-2.5 rounded border border-slate-800 overflow-x-auto max-h-40">
                          {JSON.stringify(sc.state_snapshot, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

