import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { CheckCheck, Filter, RefreshCw } from "lucide-react";
import { RootState } from "../store/store";
import { setAlerts, markAlertRead } from "../store/alertsSlice";
import { alertService } from "../services/alertService";
import AlertsTable from "../components/tables/AlertsTable";
import LoadingSpinner from "../components/common/LoadingSpinner";

const AlertsPage: React.FC = () => {
  const dispatch = useDispatch();
  const { alerts, unreadCount } = useSelector((s: RootState) => s.alerts);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState("All");
  const [typeFilter, setTypeFilter] = useState("All");

  const load = async () => {
    setLoading(true);
    const data = await alertService.getAlerts();
    dispatch(setAlerts(data));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleMarkRead = async (id: string) => {
    await alertService.markRead(id);
    dispatch(markAlertRead(id));
  };

  const handleMarkAllRead = async () => {
    const unread = (alerts as { alert_id: string; is_read: boolean }[]).filter((a) => !a.is_read);
    for (const a of unread) {
      await alertService.markRead(a.alert_id);
      dispatch(markAlertRead(a.alert_id));
    }
  };

  const filtered = (alerts as { severity: string; alert_type: string }[]).filter((a) => {
    if (severityFilter !== "All" && a.severity !== severityFilter) return false;
    if (typeFilter !== "All" && a.alert_type !== typeFilter) return false;
    return true;
  });

  const alertTypes = Array.from(new Set((alerts as { alert_type: string }[]).map((a) => a.alert_type)));

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading alerts..." /></div>;

  return (
    <div className="flex-1 min-h-0 w-full overflow-y-auto custom-scrollbar p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">System Alerts</h1>
          <p className="text-sm text-slate-400">{unreadCount} unread · {alerts.length} total</p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button onClick={handleMarkAllRead}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-600/20 border border-blue-500/30 text-blue-400 text-sm rounded-lg hover:bg-blue-600/30 transition-colors">
              <CheckCheck className="h-4 w-4" /> Mark All Read
            </button>
          )}
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        {["Critical", "High", "Medium", "Low"].map((sev) => {
          const count = (alerts as { severity: string }[]).filter((a) => a.severity === sev).length;
          const colors: Record<string, string> = { Critical: "border-red-500/40 text-red-400", High: "border-orange-500/40 text-orange-400", Medium: "border-yellow-500/40 text-yellow-400", Low: "border-blue-500/40 text-blue-400" };
          return (
            <div key={sev} className={`bg-slate-800/50 border rounded-xl p-3 text-center ${colors[sev]}`}>
              <p className="text-2xl font-bold text-white">{count}</p>
              <p className="text-xs">{sev}</p>
            </div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Filter className="h-4 w-4 text-slate-500" />
        <div className="flex gap-2">
          {["All", "Critical", "High", "Medium", "Low"].map((s) => (
            <button key={s} onClick={() => setSeverityFilter(s)}
              className={`px-3 py-1 text-xs rounded-lg transition-colors ${severityFilter === s ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"}`}>
              {s}
            </button>
          ))}
        </div>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-slate-800 border border-slate-600 text-slate-300 text-xs rounded-lg px-3 py-1.5 focus:outline-none">
          <option value="All">All Types</option>
          {alertTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Alerts List */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 overflow-x-auto custom-scrollbar">
        <AlertsTable
          alerts={filtered as any}
          onMarkRead={handleMarkRead}
        />
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-500">No alerts match the current filter.</div>
        )}
      </div>
    </div>
  );
};

export default AlertsPage;
