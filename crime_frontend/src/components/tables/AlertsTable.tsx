import React from "react";
import { AlertTriangle, AlertCircle, Info, CheckCircle } from "lucide-react";
import { formatRelative } from "../../utils/dateFormatter";

interface Alert {
  alert_id: string; alert_type: string; severity: string; location: string;
  district: string; datetime: string; description: string; is_read: boolean;
}

interface Props { alerts: Alert[]; onMarkRead?: (id: string) => void; compact?: boolean }

const severityConfig: Record<string, { icon: React.FC<{ className?: string }>, cls: string }> = {
  Critical: { icon: AlertTriangle, cls: "text-red-400" },
  High: { icon: AlertCircle, cls: "text-orange-400" },
  Medium: { icon: Info, cls: "text-yellow-400" },
  Low: { icon: CheckCircle, cls: "text-blue-400" },
};

const severityBg: Record<string, string> = {
  Critical: "bg-red-900/20 border-l-2 border-red-500",
  High: "bg-orange-900/20 border-l-2 border-orange-500",
  Medium: "bg-yellow-900/20 border-l-2 border-yellow-500",
  Low: "bg-blue-900/20 border-l-2 border-blue-500",
};

const AlertsTable: React.FC<Props> = ({ alerts, onMarkRead, compact }) => (
  <div className="space-y-2">
    {alerts.map((a) => {
      const cfg = severityConfig[a.severity] || severityConfig.Low;
      const Icon = cfg.icon;
      return (
        <div key={a.alert_id} className={`flex items-start gap-3 p-3 rounded-lg ${severityBg[a.severity] || ""} ${!a.is_read ? "ring-1 ring-white/10" : "opacity-70"}`}>
          <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${cfg.cls}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className={`text-xs font-bold ${cfg.cls}`}>{a.severity.toUpperCase()}</span>
              <span className="text-xs text-slate-500">•</span>
              <span className="text-xs text-slate-400">{a.alert_type}</span>
              {!a.is_read && <span className="ml-auto text-xs bg-blue-600/30 text-blue-400 px-1.5 py-0.5 rounded-full">NEW</span>}
            </div>
            <p className="text-xs text-slate-200 mb-0.5 truncate">{a.description}</p>
            {!compact && <p className="text-xs text-slate-500">{a.location} • {a.district}</p>}
            <div className="flex items-center justify-between mt-1">
              <span className="text-xs text-slate-600">{formatRelative(a.datetime)}</span>
              {!a.is_read && onMarkRead && (
                <button onClick={() => onMarkRead(a.alert_id)} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Mark read</button>
              )}
            </div>
          </div>
        </div>
      );
    })}
  </div>
);

export default AlertsTable;
