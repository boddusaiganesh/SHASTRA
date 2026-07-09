import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Flame, Filter, Users, Clock, Calendar, Brain, AlertTriangle } from "lucide-react";
import { crimeService } from "../services/crimeService";
import HotspotMap from "../components/maps/HotspotMap";
import TimePatternChart from "../components/charts/TimePatternChart";
import HotspotsTable from "../components/tables/HotspotsTable";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { CRIME_TYPES } from "../constants/crimeTypes";
import { useDistricts } from "../hooks/useDistricts";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const HotspotAnalysis: React.FC = () => {
  const [hotspots, setHotspots] = useState<unknown[]>([]);
  const [patterns, setPatterns] = useState<{ byHour: unknown[]; byDay: unknown[]; byMonth: unknown[] } | null>(null);
  const [deployment, setDeployment] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [district, setDistrict] = useState("All Districts");
  const districts = useDistricts();
  const [crimeType, setCrimeType] = useState("All");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetch = async (silent = false) => {
    if (!silent) setLoading(true);
    const params: any = {};
    if (district !== "All Districts") params.district_id = district;
    if (crimeType !== "All") params.crime_type = crimeType;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    try {
      const [h, p, d] = await Promise.all([
        crimeService.getHotspotClusters(params),
        crimeService.getTimePatterns(params),
        crimeService.getDeploymentSuggestions(params),
      ]);
      setHotspots(Array.isArray(h) ? h : (h?.hotspots || []));
      setPatterns(p as typeof patterns);
      setDeployment(d);
      setError(null);
    } catch (e: any) {
      console.error(e);
      setError(e.response?.data?.detail || "Failed to load hotspot data");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
    const interval = setInterval(() => fetch(true), 60000);
    return () => clearInterval(interval);
  }, [district, crimeType, dateFrom, dateTo]);

  const handleExport = async () => {
    const queryParams = new URLSearchParams({ file_format: "csv" });
    if (district !== "All Districts") queryParams.append("district_id", district);
    const { downloadAuthenticated } = await import("../utils/buildApiUrl");
    await downloadAuthenticated("/hotspots/clusters", Object.fromEntries(queryParams.entries()));
  };

  const selectClass = "bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500";

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Analyzing hotspots..." /></div>;
  if (error) return <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4"><AlertTriangle className="h-12 w-12 text-red-500" /><p>{error}</p><button onClick={() => fetch()} className="px-4 py-2 bg-slate-800 rounded-lg text-white hover:bg-slate-700">Retry</button></div>;

  const dep = deployment as { suggestions: { area: string; patrol_timing: string; officers_needed: number; priority: string; reason: string }[]; ai_summary: string } | null;

  return (
    <div className="flex-1 min-h-0 w-full overflow-y-auto custom-scrollbar p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Hotspot Analysis</h1>
          <p className="text-sm text-slate-400">Spatial crime concentration analysis across Karnataka</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-white">Filters</h3>
        </div>
        <div className="flex flex-wrap gap-3">
          <select value={district} onChange={(e) => setDistrict(e.target.value)} className={selectClass}>
            <option value="All Districts">All Districts</option>
            {districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
          </select>
          <select value={crimeType} onChange={(e) => setCrimeType(e.target.value)} className={selectClass}>
            {CRIME_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={selectClass} />
          <span className="text-slate-500 text-xs self-center">to</span>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={selectClass} />
          <button onClick={() => fetch()} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500 transition-colors">Apply Filters</button>
          <button onClick={handleExport} className="px-4 py-2 bg-slate-700 text-white text-sm rounded-lg hover:bg-slate-600 transition-colors ml-auto flex items-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            Export CSV
          </button>
        </div>
      </div>

      {/* Map + Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden" style={{ height: "400px" }}>
          <div className="p-3 border-b border-slate-700/50 flex items-center gap-2">
            <Flame className="h-4 w-4 text-red-400" />
            <h3 className="text-sm font-semibold text-white">Hotspot Heatmap — Karnataka</h3>
          </div>
          <div className="h-[calc(100%-44px)]">
            <HotspotMap hotspots={hotspots as Parameters<typeof HotspotMap>[0]["hotspots"]} />
          </div>
        </div>

        <div className="max-h-[400px] overflow-y-auto custom-scrollbar pr-1 space-y-3">
          {(hotspots as { hotspot_id: string; location: string; district: string; intensity: number; risk_level: string; crime_count: number; trend: string }[]).slice(0, 4).map((h, i) => (
            <motion.div key={h.hotspot_id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}
              className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="text-sm font-medium text-white">{h.location}</p>
                  <p className="text-xs text-slate-400">{h.district}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${h.risk_level === "High" ? "bg-red-900/40 text-red-400" : h.risk_level === "Medium" ? "bg-orange-900/40 text-orange-400" : "bg-green-900/40 text-green-400"}`}>
                  {h.risk_level}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-slate-700 rounded-full">
                  <div className="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500" style={{ width: `${h.intensity}%` }} />
                </div>
                <span className="text-xs text-slate-400">{h.crime_count} crimes</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Time Patterns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-white">Crimes by Hour of Day</h3>
          </div>
          {patterns && <TimePatternChart data={(patterns.byHour as { label: string; crimes: number }[])} color="#3b82f6" />}
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="h-4 w-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-white">Crimes by Day of Week</h3>
          </div>
          {patterns && (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={patterns.byDay as { day: string; crimes: number }[]}>
                <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 10 }} />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px", fontSize: "12px" }} />
                <Bar dataKey="crimes" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="h-4 w-4 text-green-400" />
            <h3 className="text-sm font-semibold text-white">Crimes by Month</h3>
          </div>
          {patterns && (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={patterns.byMonth as { month: string; crimes: number }[]}>
                <XAxis dataKey="month" tick={{ fill: "#64748b", fontSize: 10 }} />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px", fontSize: "12px" }} />
                <Bar dataKey="crimes" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top Hotspots Table */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Flame className="h-4 w-4 text-red-400" />
          <h3 className="text-sm font-semibold text-white">Top 10 Hotspots</h3>
        </div>
        <HotspotsTable hotspots={hotspots as Parameters<typeof HotspotsTable>[0]["hotspots"]} />
      </div>

      {/* Deployment Suggestions */}
      {dep && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-4 w-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-white">AI-Powered Resource Deployment Suggestions</h3>
            <span className="text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">Gemini AI</span>
          </div>
          <div className="bg-blue-950/30 border border-blue-500/20 rounded-lg p-3 mb-4">
            <p className="text-xs text-blue-200 leading-relaxed">{dep.ai_summary}</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(Array.isArray(dep?.suggestions) ? dep.suggestions : []).map((s, i) => (
              <div key={i} className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-white truncate">{s.area}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${s.priority === "Critical" ? "bg-red-900/40 text-red-400" : s.priority === "High" ? "bg-orange-900/40 text-orange-400" : "bg-yellow-900/40 text-yellow-400"}`}>{s.priority}</span>
                </div>
                <div className="space-y-1 text-xs text-slate-400">
                  <div className="flex items-center gap-2"><Clock className="h-3 w-3" />{s.patrol_timing}</div>
                  <div className="flex items-center gap-2"><Users className="h-3 w-3" />{s.officers_needed} officers needed</div>
                </div>
                <p className="text-xs text-slate-500 mt-2 italic">{s.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default HotspotAnalysis;
