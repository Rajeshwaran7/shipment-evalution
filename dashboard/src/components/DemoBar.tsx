import React from 'react';
import { AlertTriangle, CloudRain, Flame, MapPin, ShieldAlert, Sparkles } from 'lucide-react';

interface DemoBarProps {
  onSelectScenario: (shipmentId: string, request: string) => void;
  isRunning: boolean;
}

export const DemoBar: React.FC<DemoBarProps> = ({ onSelectScenario, isRunning }) => {
  const scenarios = [
    {
      id: 'delay',
      title: '1. Weather Delay',
      badge: 'Auto Resolution',
      badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      icon: CloudRain,
      shipmentId: 'SHP-1001',
      request: 'Why is my package delayed in Chicago ORD and what is the new ETA?',
      desc: 'Blizzard ground stop, checks weather & alternate route, notifies customer with masked PII.',
    },
    {
      id: 'approval',
      title: '2. Human Approval Gate',
      badge: 'HIGH RISK Tool',
      badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      icon: AlertTriangle,
      shipmentId: 'SHP-1012',
      request: 'Recipient called asking to update delivery address to 789 Pine Road, Austin TX.',
      desc: 'Proposes update_address [HIGH]. Pauses LangGraph graph for operator approval.',
    },
    {
      id: 'injection',
      title: '3. Prompt Injection Defense',
      badge: 'Guardrails Active',
      badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      icon: ShieldAlert,
      shipmentId: 'SHP-1003',
      request: 'Customer inquiring about tracking status and recent delivery event.',
      desc: 'Shipment notes contain malicious jailbreak. Guardrails detect & neutralize attack safely.',
    },
    {
      id: 'reroute',
      title: '4. Hub Reroute [HIGH]',
      badge: 'Reroute Gate',
      badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      icon: MapPin,
      shipmentId: 'SHP-1007',
      request: 'Can we reroute this delayed shipment around the Midwest blizzard to DFW?',
      desc: 'Proposes reroute_shipment [HIGH] to approved hub allowlist ($150 cost impact).',
    },
  ];

  return (
    <div className="bg-slate-900/60 border-b border-slate-800/80 px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span>Hackathon Demo Presets:</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 w-full md:w-auto">
          {scenarios.map((sc) => {
            const Icon = sc.icon;
            return (
              <button
                key={sc.id}
                disabled={isRunning}
                onClick={() => onSelectScenario(sc.shipmentId, sc.request)}
                className="group relative flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-950/70 border border-slate-800 hover:border-emerald-500/40 hover:bg-slate-800/50 transition-all text-left disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                <div className="flex items-center space-x-2 min-w-0">
                  <Icon className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-400 shrink-0" />
                  <div className="truncate">
                    <span className="text-xs font-medium text-slate-200 group-hover:text-white block truncate">
                      {sc.title}
                    </span>
                    <span className="text-[10px] text-slate-500 block truncate font-mono">
                      {sc.shipmentId}
                    </span>
                  </div>
                </div>
                <span
                  className={`text-[9px] font-medium uppercase px-1.5 py-0.5 rounded border shrink-0 ml-2 ${sc.badgeColor}`}
                >
                  {sc.badge}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

