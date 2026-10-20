import React, { useState } from 'react';
import { AlertCircle, Check, DollarSign, ShieldAlert, X } from 'lucide-react';
import { ApprovalData } from '../types';

interface ApprovalCardProps {
  approvalData: ApprovalData;
  onSubmitDecision: (decision: boolean, comment: string) => Promise<void>;
  isSubmitting: boolean;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approvalData,
  onSubmitDecision,
  isSubmitting,
}) => {
  const [comment, setComment] = useState('');

  return (
    <div className="rounded-xl border border-amber-300 dark:border-amber-500/40 bg-amber-50/60 dark:bg-amber-950/20 p-4 shadow-sm transition-all animate-pulse-subtle">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-700 dark:text-amber-400">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-900 dark:text-amber-200 uppercase tracking-wider">
              Operator Approval Required
            </h4>
            <p className="text-[11px] text-slate-600 dark:text-slate-400">
              {approvalData.approval_reason || 'High-risk tool invocation paused for verification.'}
            </p>
          </div>
        </div>

        <div className="text-right shrink-0">
          <span className="text-[10px] text-slate-500 dark:text-slate-400 block uppercase">
            Cost Impact
          </span>
          <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
            +${approvalData.estimated_cost_usd?.toFixed(2) ?? '0.00'}
          </span>
        </div>
      </div>

      {/* Proposed Actions */}
      <div className="mt-3 space-y-2">
        {approvalData.proposed_actions?.map((action, idx) => (
          <div
            key={idx}
            className="p-2.5 rounded-lg bg-white dark:bg-slate-900/80 border border-amber-200/80 dark:border-slate-800 text-xs space-y-1.5"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono font-semibold text-[11px] text-amber-700 dark:text-amber-400">
                {action.tool}
              </span>
              <span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-300 dark:border-amber-500/20">
                High Risk
              </span>
            </div>

            {action.rationale && (
              <p className="text-[11px] text-slate-700 dark:text-slate-300">
                {action.rationale}
              </p>
            )}

            <div className="text-[10px] font-mono text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 p-1.5 rounded border border-slate-200 dark:border-slate-800 overflow-x-auto">
              {JSON.stringify(action.args || action.parameters || {}, null, 1)}
            </div>
          </div>
        ))}
      </div>

      {/* Comment Input */}
      <div className="mt-3">
        <input
          type="text"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Operator audit note (optional)..."
          className="w-full text-xs px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-amber-500"
        />
      </div>

      {/* Action Buttons */}
      <div className="mt-3 flex items-center justify-end space-x-2">
        <button
          onClick={() => onSubmitDecision(false, comment)}
          disabled={isSubmitting}
          className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-rose-600 dark:hover:text-rose-400 text-xs font-medium transition-colors disabled:opacity-50"
        >
          <X className="w-3.5 h-3.5 text-rose-500" />
          <span>Reject</span>
        </button>

        <button
          onClick={() => onSubmitDecision(true, comment)}
          disabled={isSubmitting}
          className="flex items-center space-x-1 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
        >
          <Check className="w-3.5 h-3.5" />
          <span>{isSubmitting ? 'Resuming...' : 'Approve & Execute'}</span>
        </button>
      </div>
    </div>
  );
};
