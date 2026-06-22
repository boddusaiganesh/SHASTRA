import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Brain, TrendingUp, MapPin, AlertTriangle, Users } from "lucide-react";
import { predictionService } from "../services/predictionService";
import ForecastChart from "../components/charts/ForecastChart";
import RiskMap from "../components/maps/RiskMap";
import LoadingSpinner from "../components/common/LoadingSpinner";

const PredictiveAnalytics: React.FC = () => {
  const [forecast, setForecast] = useState<unknown[]>([]);
  const [riskAreas, setRiskAreas] = useState<unknown[]>([]);
  const [typologies, setTypologies] = useState<unknown[]>([]);
  const [riskMapData, setRiskMapData] = useState<unknown[]>([]);
  const [socioData, setSocioData] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [f, r, t, rm] = await Promise.all([
        predictionService.getForecast(),
        predictionService.getHighRiskAreas(),
        predictionService.getEmergingTypologies(),
        predictionService.getRiskMap(),
        predictionService.getSocioeconomicData(),
      ]);
      setForecast(f as unknown[]);
      setRiskAreas(r as unknown[]);
      setTypologies(t as unknown[]);
      setRiskMapData(rm as unknown[]);
      setSocioData(s as unknown[]);
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Running predictive models..." /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Predictive Intelligence</h1>
        <p className="text-sm text-slate-400">AI/ML-powered crime forecasting and risk assessment</p>
      </div>

      {/* 30-day forecast */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-4 w-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-white">30-Day Crime Forecast</h2>
          <span className="text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">Prophet Model</span>
        </div>
        {forecast && forecast.length > 0 ? (
           <ForecastChart data={forecast as any} />
        ) : (
           <div className="text-center py-4 text-slate-500">No forecast data available</div>
        )}
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="h-4 w-4 text-purple-400" />
          <h2 className="text-sm font-semibold text-white">District Risk Map</h2>
        </div>
        <div style={{ height: "380px" }}>
          <RiskMap districts={riskMapData as any} />
        </div>
      </div>

      {/* High Risk Areas */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="h-4 w-4 text-red-400" />
          <h2 className="text-sm font-semibold text-white">High-Risk Areas (Next 72 Hours)</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(riskAreas as { area: string; location: string; district: string; risk_score: number; risk_percentage: number; predicted_crime_type: string; probability: number }[]).map((r, i) => {
             const areaName = r.area || r.location;
             const riskVal = r.risk_score || r.risk_percentage || 0;
             return (
            <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-white">{areaName}</p>
                <span className={`text-xs font-bold ${riskVal >= 80 ? "text-red-400" : riskVal >= 60 ? "text-orange-400" : "text-yellow-400"}`}>
                  {riskVal}/100
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-1">{r.district}</p>
              <p className="text-xs text-orange-300">Expected: {r.predicted_crime_type}</p>
              <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
                <div className="h-full rounded-full bg-gradient-to-r from-yellow-500 to-red-500" style={{ width: `${riskVal}%` }} />
              </div>
            </motion.div>
          )})}
        </div>
      </div>

      {/* Emerging Typologies */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="h-4 w-4 text-orange-400" />
          <h2 className="text-sm font-semibold text-white">Emerging Crime Typologies</h2>
        </div>
        <div className="space-y-3">
          {(typologies as { typology: string; description: string; trend: string; growth_rate: string; districts: string[] }[]).map((t, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
              <Brain className="h-4 w-4 text-purple-400 mt-0.5 flex-shrink-0" />
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-medium text-white">{t.typology}</p>
                  <span className="text-xs bg-red-900/40 text-red-400 px-2 py-0.5 rounded-full">{t.trend || t.growth_rate}</span>
                </div>
                <p className="text-xs text-slate-400">{t.description}</p>
                {t.districts && <p className="text-xs text-slate-500 mt-1">Districts: {t.districts.join(", ")}</p>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Socioeconomic Factors */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Users className="h-4 w-4 text-green-400" />
          <h2 className="text-sm font-semibold text-white">Socioeconomic Correlations</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(socioData as { district: string; unemployment_rate: number; population_density: number; urbanization: number; poverty_index: number }[]).slice(0, 6).map((sd, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-3">
              <p className="text-sm font-medium text-white mb-2">{sd.district}</p>
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Unemployment</span>
                  <span className="text-slate-200">{sd.unemployment_rate}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Pop. Density</span>
                  <span className="text-slate-200">{sd.population_density}/sqkm</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Poverty Index</span>
                  <span className="text-slate-200">{sd.poverty_index}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PredictiveAnalytics;
