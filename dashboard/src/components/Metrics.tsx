import React, { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Activity,
  ArrowUpRight,
  Clock,
  Coins,
  Cpu,
  DollarSign,
  Eye,
  FileCheck2,
  RefreshCw,
  Search,
  Zap,
} from 'lucide-react';
import { RunDetail, RunSummary } from '../types';

interface MetricsProps {
  runs: RunSummary[];
  onRefresh: () => void;
  onSelectRun: (runId: string) => void;
  isLoading: boolean;
}

export const Metrics: React.FC<MetricsProps> = ({
  runs,
  onRefresh,
  onSelectRun,
  isLoading,
}) => {
  const [filterText, setFilterText] = useState('');

  // Compute aggregated KPIs
  const totalRuns = runs.length;
  const completedRuns = runs.filter((r) => r.status === 'completed');
  const pausedRuns = runs.filter((r) => r.status === 'paused');
  const failedRuns = runs.filter((r) => r.status === 'failed');

  const totalCost = runs.reduce((acc, r) => acc + (r.cost_usd || 0), 0);
  const totalTokens = runs.reduce(
    (acc, r) => acc + (r.input_tokens || 0) + (r.output_tokens || 0),
    0
  );

  const completedWithDuration = completedRuns.filter((r) => r.duration_ms && r.duration_ms > 0);
  const avgLatency =
    completedWithDuration.length > 0
      ? completedWithDuration.reduce((acc, r) => acc + (r.duration_ms || 0), 0) /
        completedWithDuration.length
      : 0;

  const avgCostPerResolved =
    completedRuns.length > 0
      ? completedRuns.reduce((acc, r) => acc + (r.cost_usd || 0), 0) / completedRuns.length
      : 0;

  // Chart data: chronological order (oldest to newest)
  const chartData = [...runs]
    .reverse()
    .slice(-15)
    .map((r, idx) => ({
      name: `#${idx + 1} (${r.shipment_id})`,
      cost: Number((r.cost_usd || 0).toFixed(4)),
      latency: Math.round(r.duration_ms || 0),
      tokens: (r.input_tokens || 0) + (r.output_tokens || 0),
      status: r.status,
    }));

  const filteredRuns = runs.filter(
    (r) =>
      r.run_id.toLowerCase().includes(filterText.toLowerCase()) ||
      r.shipment_id.toLowerCase().includes(filterText.toLowerCase()) ||
      r.user_request.toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Runs */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Total Agent Runs
            </span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-white">{totalRuns}</span>
              <span className="text-[11px] text-emerald-400 font-medium">
                {completedRuns.length} resolved
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        {/* Avg Latency */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Avg Latency (Resolved)
            </span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-white">
                {Math.round(avgLatency)}
                <span className="text-xs text-slate-400 font-normal"> ms</span>
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        {/* Total Tokens Consumed */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Telemetry Tokens
            </span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-white">
                {totalTokens.toLocaleString()}
              </span>
              <span className="text-[11px] text-slate-400 font-mono">tokens</span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Cpu className="w-5 h-5" />
          </div>
        </div>

        {/* Cost per Resolved Exception */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Cost / Resolution
            </span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-emerald-400">
                ${avgCostPerResolved.toFixed(4)}
              </span>
              <span className="text-[11px] text-slate-400">
                (Total: ${totalCost.toFixed(4)})
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <DollarSign className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Observability Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Per Run Bar Chart */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Cost Per Run ($ USD)
              </h3>
              <p className="text-[11px] text-slate-500">
                Token consumption priced via multi-provider cost table
              </p>
            </div>
            <Coins className="w-4 h-4 text-emerald-400" />
          </div>

          <div className="h-60 w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Bar dataKey="cost" fill="#10b981" radius={[4, 4, 0, 0]} name="Cost ($)" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No runs recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Latency Over Time Line Chart */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Latency Over Time (Milliseconds)
              </h3>
              <p className="text-[11px] text-slate-500">
                End-to-end multi-step workflow response time
              </p>
            </div>
            <Zap className="w-4 h-4 text-blue-400" />
          </div>

          <div className="h-60 w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={{ fill: '#38bdf8', r: 3 }}
                    name="Latency (ms)"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No runs recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Runs History Table */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Runs History & Trace Observability
            </h3>
            <p className="text-[11px] text-slate-500">
              Audit log of all agent runs, checkpointer states, and costs
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Filter shipment or run..."
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                className="text-xs pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              title="Refresh Runs"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider text-[10px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Run ID</th>
                <th className="py-3 px-4">Shipment</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Tokens</th>
                <th className="py-3 px-4">Cost ($)</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {filteredRuns.length > 0 ? (
                filteredRuns.map((r) => (
                  <tr key={r.run_id} className="hover:bg-slate-850/40 transition-colors font-sans">
                    <td className="py-3 px-4 font-mono font-medium text-slate-200">
                      {r.run_id}
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-400 font-semibold">
                      {r.shipment_id}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          r.status === 'completed'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : r.status === 'paused'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                            : r.status === 'running'
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30 animate-pulse'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">
                      {r.duration_ms ? `${Math.round(r.duration_ms)}ms` : '-'}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">
                      {(r.input_tokens || 0) + (r.output_tokens || 0)}
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-400">
                      ${r.cost_usd ? r.cost_usd.toFixed(4) : '0.0000'}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {r.started_at ? new Date(r.started_at).toLocaleTimeString() : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => onSelectRun(r.run_id)}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium transition-colors"
                      >
                        <Eye className="w-3 h-3 text-slate-400" />
                        <span>Trace</span>
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 text-xs font-sans">
                    No runs found matching query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

