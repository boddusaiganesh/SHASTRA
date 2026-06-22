import React, { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { motion } from "framer-motion";
import {
  Shield, TrendingUp, TrendingDown, Flame, AlertTriangle,
  Users, CheckCircle, Bell, Activity, BarChart2, RefreshCw,
} from "lucide-react";
import { RootState } from "../store/store";
import { crimeService } from "../services/crimeService";
import CrimeTrendChart from "../components/charts/CrimeTrendChart";
import CrimeTypeChart from "../components/charts/CrimeTypeChart";
import AlertsTable from "../components/tables/AlertsTable";
import CrimesTable from "../components/tables/CrimesTable";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const StatCard: React.FC<{
  title: string; value: string | number; subtitle?: string; icon: React.FC<{ className?: string }>;
  trend?: string; positive?: boolean; color: string; delay?: number; isCritical?: boolean;
}> = ({ title, value, subtitle, icon: Icon, trend, positive, color, delay = 0, isCritical }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }} 
    animate={isCritical ? { opacity: 1, y: 0, boxShadow: ["0px 0px 0px rgba(239,68,68,0)", "0px 0px 20px rgba(239,68,68,0.5)", "0px 0px 0px rgba(239,68,68,0)"] } : { opacity: 1, y: 0 }} 
    transition={isCritical ? { opacity: { delay }, y: { delay }, boxShadow: { repeat: Infinity, duration: 2, ease: "easeInOut" } } : { delay }}
    className={`bg-slate-800/50 border ${isCritical ? 'border-red-500/50' : 'border-slate-700/50'} rounded-xl p-4 transition-all`}
  >
    <div className="flex items-start justify-between mb-3">
      <div className={`h-10 w-10 rounded-xl flex items-center justify-center`} style={{ background: color + "20" }}>
        <Icon className="h-5 w-5" />
      </div>
      {trend && (
        <div className={`flex items-center gap-1 text-xs font-medium ${positive ? "text-green-400" : "text-red-400"}`}>
          {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {trend}
        </div>
      )}
    </div>
    <p className="text-2xl font-bold text-white mb-0.5">{typeof value === "number" ? value.toLocaleString() : value}</p>
    <p className="text-xs font-medium text-slate-300">{title}</p>
    {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
  </motion.div>
);

const Dashboard: React.FC = () => {
  const auth = useSelector((s: RootState) => s.auth);
  const [summary, setSummary] = useState<Record<string, number | string> | null>(null);
  const [trends, setTrends] = useState<{ month: string; crimes: number; solved: number }[]>([]);
  const [crimeTypes, setCrimeTypes] = useState<{ type: string; count: number; percentage: number }[]>([]);
  const [districtData, setDistrictData] = useState<{ district: string; count: number }[]>([]);
  const [recentCrimes, setRecentCrimes] = useState<unknown[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [s, t, c, ra] = await Promise.all([
        crimeService.getDashboardSummary(),
        crimeService.getCrimeTrends(),
        crimeService.getRecentCrimes(),
        crimeService.getRecentAlerts(),
      ]);
      setSummary(s as Record<string, number | string>);
      setTrends(t.trends);
      setCrimeTypes(t.byType);
      setDistrictData(t.byDistrict);
      setRecentCrimes(c);
      setRecentAlerts(ra || []);
      setLastRefresh(new Date());
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => { 
    fetchData(); 
    const interval = setInterval(() => fetchData(true), 30000);
    return () => clearInterval(interval);
  }, []);

  const stats = summary ? [
    { title: "Total Crimes This Month", value: summary.total_crimes_month as number, icon: Shield, trend: summary.total_crimes_trend as string, positive: false, color: "#EF4444", subtitle: "All reported cases" },
    { title: "Active Hotspots", value: summary.active_hotspots_count as number, icon: Flame, trend: summary.hotspots_trend as string, positive: true, color: "#F97316", subtitle: "Across Karnataka", isCritical: true },
    { title: "High Risk Areas", value: summary.high_risk_areas_count as number, icon: AlertTriangle, trend: summary.high_risk_trend as string, positive: false, color: "#EF4444", subtitle: "Immediate attention", isCritical: true },
    { title: "Repeat Offenders Tracked", value: summary.repeat_offenders_count as number, icon: Users, trend: summary.offenders_trend as string, positive: false, color: "#8B5CF6", subtitle: "Active monitoring" },
    { title: "Pending Alerts", value: summary.pending_alerts_count as number, icon: Bell, color: "#F59E0B", subtitle: "Requires action" },
    { title: "Cases Solved This Month", value: summary.cases_solved_month as number, icon: CheckCircle, color: "#22C55E", subtitle: "Closed successfully" },
  ] : [];

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading dashboard..." /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Command Dashboard</h1>
          <p className="text-sm text-slate-400">Welcome back, <span className="text-blue-400">{auth.user_name}</span> · {auth.user_role}</p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-slate-500">Last updated: {lastRefresh.toLocaleTimeString()}</p>
          <button onClick={fetchData} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg transition-colors">
            <RefreshCw className="h-3.5 w-3.5" />Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((s, i) => <StatCard key={s.title} {...s} delay={i * 0.08} />)}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="lg:col-span-1 bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-4 w-4 text-blue-400" />
            <h2 className="text-sm font-semibold text-white">Crime Trend (12 Months)</h2>
          </div>
          <CrimeTrendChart data={trends} />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="h-4 w-4 text-purple-400" />
            <h2 className="text-sm font-semibold text-white">Crime Type Breakdown</h2>
          </div>
          <CrimeTypeChart data={crimeTypes} />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="h-4 w-4 text-green-400" />
            <h2 className="text-sm font-semibold text-white">Top Districts by Crime</h2>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={districtData.slice(0, 8)} layout="vertical" margin={{ left: 10, right: 10 }}>
              <XAxis type="number" tick={{ fill: "#64748b", fontSize: 10 }} />
              <YAxis type="category" dataKey="district" tick={{ fill: "#94a3b8", fontSize: 10 }} width={100} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px", fontSize: "12px" }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {districtData.slice(0, 8).map((_, i) => <Cell key={i} fill={i === 0 ? "#EF4444" : i === 1 ? "#F97316" : "#3B82F6"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Bottom Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-red-400" />
              <h2 className="text-sm font-semibold text-white">Recent Alerts</h2>
            </div>
            <span className="text-xs text-slate-500">Last 10</span>
          </div>
          <AlertsTable alerts={recentAlerts.slice(0, 8) as Parameters<typeof AlertsTable>[0]["alerts"]} compact />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9 }} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-400" />
              <h2 className="text-sm font-semibold text-white">Recent Crimes Feed</h2>
            </div>
            <span className="text-xs text-green-400 flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />Live</span>
          </div>
          <CrimesTable crimes={recentCrimes.slice(0, 8) as Parameters<typeof CrimesTable>[0]["crimes"]} compact />
        </motion.div>
      </div>
    </div>
  );
};

export default Dashboard;
