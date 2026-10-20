import React, { useEffect, useState } from 'react';
import {
  checkHealth,
  fetchEvalsHistory,
  fetchLatestEvals,
  fetchRuns,
  fetchShipments,
} from './api';
import { Evals } from './components/Evals';
import { LiveRun } from './components/LiveRun';
import { Metrics } from './components/Metrics';
import { Navbar } from './components/Navbar';
import { RunTraceModal } from './components/RunTraceModal';
import {
  EvalHistoryItem,
  EvalReport,
  RunSummary,
  Shipment,
  TabType,
} from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('live');
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(true);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('exceptionops_theme') as 'dark' | 'light') || 'dark';
  });

  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>('SHP-1001');
  const [presetRequest, setPresetRequest] = useState<string>(
    'Why is my package delayed in Chicago ORD and what is the current ETA?'
  );

  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(false);
  const [selectedRunIdForTrace, setSelectedRunIdForTrace] = useState<string | null>(null);

  const [evalReport, setEvalReport] = useState<EvalReport | null>(null);
  const [evalHistory, setEvalHistory] = useState<EvalHistoryItem[]>([]);
  const [isLoadingEvals, setIsLoadingEvals] = useState<boolean>(false);

  // Apply theme to <html>
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
    localStorage.setItem('exceptionops_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Initial load
  useEffect(() => {
    const verifyHealth = async () => {
      const res = await checkHealth();
      setIsBackendOnline(res.status === 'ok');
    };
    verifyHealth();
    const interval = setInterval(verifyHealth, 15000);

    fetchShipments()
      .then((data) => {
        setShipments(data);
        if (data.length > 0 && !selectedShipmentId) {
          setSelectedShipmentId(data[0].shipment_id);
        }
      })
      .catch((err) => console.warn('Could not load shipments:', err));

    loadRuns();
    loadEvals();

    return () => clearInterval(interval);
  }, []);

  const loadRuns = async () => {
    setIsLoadingRuns(true);
    try {
      const data = await fetchRuns(50);
      setRuns(data);
    } catch (err) {
      console.warn('Could not load runs:', err);
    } finally {
      setIsLoadingRuns(false);
    }
  };

  const loadEvals = async () => {
    setIsLoadingEvals(true);
    try {
      const latest = await fetchLatestEvals();
      setEvalReport(latest);
      const history = await fetchEvalsHistory(10);
      setEvalHistory(history);
    } catch (err) {
      console.warn('Could not load evals:', err);
    } finally {
      setIsLoadingEvals(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors">
      {/* Clean Navbar with Theme Switcher */}
      <Navbar
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          if (tab === 'metrics') loadRuns();
          if (tab === 'evals') loadEvals();
        }}
        isBackendOnline={isBackendOnline}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {activeTab === 'live' && (
          <LiveRun
            shipments={shipments}
            selectedShipmentId={selectedShipmentId}
            onSelectShipmentId={setSelectedShipmentId}
            presetRequest={presetRequest}
          />
        )}

        {activeTab === 'metrics' && (
          <Metrics
            runs={runs}
            onRefresh={loadRuns}
            onSelectRun={(runId) => setSelectedRunIdForTrace(runId)}
            isLoading={isLoadingRuns}
          />
        )}

        {activeTab === 'evals' && (
          <Evals
            evalReport={evalReport}
            evalHistory={evalHistory}
            onRefresh={loadEvals}
            isLoading={isLoadingEvals}
          />
        )}
      </main>

      {/* Trace Inspection Modal */}
      {selectedRunIdForTrace && (
        <RunTraceModal
          runId={selectedRunIdForTrace}
          onClose={() => setSelectedRunIdForTrace(null)}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 py-4 text-xs text-slate-500 dark:text-slate-400 transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            ExceptionOps &middot; FastMCP &middot; LangGraph &middot; Human-in-the-Loop &middot; Groq
          </div>
          <div className="font-mono text-[11px] text-slate-400 dark:text-slate-500">
            Hardened Safety &middot; PII Redacted
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
