import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertOctagon, RefreshCw, CheckCircle, Clock, Eye } from "lucide-react";
import { anomalyService } from "../services/predictionService";
import LoadingSpinner from "../components/common/LoadingSpinner";
import ExplainabilityPanel from "../components/common/ExplainabilityPanel";

interface Anomaly {
  anomaly_id: string; anomaly_type: string; description: string;
  district: string; location: string; severity: string;
  detected_at: string; status: string; confidence_score: number;
  affected_crimes_count: number; evidence_points?: string[];
  anomaly_score?: number;
}

const severityColors: Record<string, string> = {
  Critical: "bg-red-900/30 border-red-500/40 text-red-400",
  High: "bg-orange-900/30 border-orange-500/40 text-orange-400",
  Medium: "bg-yellow-900/30 border-yellow-500/40 text-yellow-400",
  Low: "bg-blue-900/30 border-blue-500/40 text-blue-400",
};

const AnomalyDetection: React.FC = () => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("All");

  const fetch = async () => {
    setLoading(true);
    const data: any = await anomalyService.getList();
    setAnomalies(Array.isArray(data) ? data : (data?.anomalies || []));
    setLoading(false);
  };

  useEffect(() => { fetch(); }, []);

  const handleUpdateStatus = async (id: string, status: string) => {
    await anomalyService.updateStatus(id, status);
    setAnomalies((prev) => prev.map((a) => a.anomaly_id === id ? { ...a, status } : a));
  };

  const safeAnomalies = Array.isArray(anomalies) ? anomalies : [];
  const filtered = statusFilter === "All"
    ? safeAnomalies
    : safeAnomalies.filter((a) => a.status === statusFilter);

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Running anomaly detection..." /></div>;

  return (
    <div className="flex-1 min-h-0 w-full overflow-y-auto custom-scrollbar p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Anomaly Detection</h1>
          <p className="text-sm text-slate-400">AI-detected statistical deviations in crime patterns</p>
        </div>
        <button onClick={fetch} className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {["Critical", "High", "Medium", "Low"].map((sev) => {
          const count = safeAnomalies.filter((a) => a.severity === sev).length;
          return (
            <div key={sev} className={`rounded-xl border p-4 ${severityColors[sev]}`}>
              <p className="text-2xl font-bold text-white">{count}</p>
              <p className="text-xs mt-1">{sev} Severity</p>
            </div>
          );
        })}
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {["All", "Active", "Investigating", "Resolved"].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${statusFilter === s ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"}`}>
            {s}
          </button>
        ))}
      </div>

      {/* Anomaly List */}
      <div className="space-y-3">
        {filtered.map((a, i) => (
          <motion.div key={a.anomaly_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
            className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertOctagon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${
                  a.severity === "Critical" ? "text-red-400" : a.severity === "High" ? "text-orange-400" : "text-yellow-400"
                }`} />
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-slate-500">{a.anomaly_id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${severityColors[a.severity]}`}>{a.severity}</span>
                    <span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded-full">{a.anomaly_type}</span>
                  </div>
                  <p className="text-sm text-white font-medium mb-1">{a.description}</p>
                  <ExplainabilityPanel points={a.evidence_points || []} score={a.anomaly_score} />
                  <p className="text-xs text-slate-400 mt-1">{a.location} · {a.district}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(a.detected_at || new Date()).toLocaleString()}</span>
                    <span>Confidence: <span className="text-blue-400 font-bold">{(a.confidence_score * 100).toFixed(0)}%</span></span>
                    <span>{a.affected_crimes_count} crimes affected</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className={`text-xs px-2 py-1 rounded-full ${a.status === "Resolved" ? "bg-green-900/40 text-green-400" : a.status === "Investigating" ? "bg-blue-900/40 text-blue-400" : "bg-orange-900/40 text-orange-400"}`}>
                  {a.status}
                </span>
                {a.status !== "Resolved" && (
                  <button onClick={() => handleUpdateStatus(a.anomaly_id, a.status === "Active" ? "Investigating" : "Resolved")}
                    className="flex items-center gap-1 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded-lg transition-colors">
                    {a.status === "Active" ? <><Eye className="h-3 w-3" /> Investigate</> : <><CheckCircle className="h-3 w-3" /> Resolve</>}
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-slate-500">No anomalies match the current filter.</div>
        )}
      </div>
    </div>
  );
};

export default AnomalyDetection;
