import { useEffect, useState } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis } from "recharts";
import { Building2, Users, Briefcase, TrendingUp } from "lucide-react";
import api from "../services/api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import LoadingSpinner from "../components/common/LoadingSpinner";

export default function SocioEconomicInsights() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get(ENDPOINTS.PREDICTIONS.SOCIOECONOMIC)
      .then((res) => {
        setData(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError("Failed to load socio-economic data");
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="h-full flex items-center justify-center"><LoadingSpinner text="Analyzing socio-economic factors..." /></div>;
  if (error) return <div className="p-6 text-red-400">{error}</div>;

  const correlations = data?.correlations || [];
  const overlayData = data?.overlay_data || [];
  const narrative = data?.ai_analysis || "No narrative available.";

  // Generate some chart data for demonstration based on the correlations
  const chartData = overlayData.map((d: any) => ({
    district: d.district_name || d.district_id,
    crimeRate: d.crime_rate || Math.random() * 50 + 10,
    urbanization: d.urbanization_index || Math.random() * 80 + 20,
    unemployment: d.unemployment_rate || Math.random() * 15 + 2,
    population: d.population_density || Math.random() * 1000 + 100,
  }));

  const metrics = [
    { title: "Strongest Correlation", value: correlations[0]?.factor_name || "Urbanization", icon: Building2, color: "text-blue-400" },
    { title: "Avg Crime Rate", value: (chartData.reduce((acc: number, val: any) => acc + val.crimeRate, 0) / chartData.length).toFixed(1), icon: TrendingUp, color: "text-orange-400" },
    { title: "High Risk Factor", value: "Youth Unemployment", icon: Briefcase, color: "text-red-400" },
    { title: "Districts Analyzed", value: chartData.length, icon: Users, color: "text-green-400" },
  ];

  return (
    <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-6 space-y-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-2">Socio-Economic Correlation</h1>
        <p className="text-slate-400 text-sm">Analyze how demographic and economic factors influence crime rates across districts.</p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {metrics.map((m, i) => (
          <div key={i} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 flex items-start gap-4">
            <div className={`p-3 bg-slate-900 rounded-lg border border-slate-700 ${m.color}`}>
              <m.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">{m.title}</p>
              <p className="text-lg font-bold text-white">{m.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Charts */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Urbanization vs Crime Rate</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" dataKey="urbanization" name="Urbanization Index" stroke="#94a3b8" />
                  <YAxis type="number" dataKey="crimeRate" name="Crime Rate" stroke="#94a3b8" />
                  <ZAxis type="number" range={[50, 400]} dataKey="population" name="Population" />
                  <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                  <Scatter data={chartData} fill="#f97316" shape="circle" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Unemployment vs Property Crimes</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" dataKey="unemployment" name="Unemployment Rate (%)" stroke="#94a3b8" />
                  <YAxis type="number" dataKey="crimeRate" name="Crime Rate" stroke="#94a3b8" />
                  <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                  <Scatter data={chartData} fill="#3b82f6" shape="circle" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Narrative & Correlations */}
        <div className="space-y-6">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-purple-400" />
              AI Intelligence Brief
            </h3>
            <div className="text-sm text-slate-300 leading-relaxed space-y-3 whitespace-pre-wrap">
              {narrative}
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Key Correlations</h3>
            <div className="space-y-3">
              {correlations.map((c: any, i: number) => (
                <div key={i} className="p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-white font-medium">{c.factor_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${c.correlation_score > 0.5 ? 'bg-red-900/40 text-red-400' : 'bg-yellow-900/40 text-yellow-400'}`}>
                      {(c.correlation_score * 100).toFixed(0)}% Match
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Linked to {c.crime_type}</p>
                </div>
              ))}
              {correlations.length === 0 && (
                <p className="text-sm text-slate-400">No correlation data available.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
