import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, Search, Shield, ChevronRight, MapPin, AlertTriangle } from "lucide-react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { offenderService } from "../services/offenderService";
import LoadingSpinner from "../components/common/LoadingSpinner";
import ExplainabilityPanel from "../components/common/ExplainabilityPanel";

interface Offender {
  offender_id: string; offender_name: string; age: number; offender_age?: number; district: string;
  crime_count: number; primary_crime_type: string; risk_score: number;
  status: string; offender_status?: string; last_known_location: string; modus_operandi: any;
  photo_url?: string; risk_factors?: string[];
}

const OffenderDatabase: React.FC = () => {
  const [offenders, setOffenders] = useState<Offender[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Offender | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modusOperandi, setModusOperandi] = useState<Record<string, unknown> | null>(null);
  const [offenderRisk, setOffenderRisk] = useState<any>(null);

  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    offenderService.searchOffenders("").then((d: any) => {
      const list = Array.isArray(d) ? d : (d?.offenders || []);
      setOffenders(list);
      setError(null);
      
      const deepLinkId = searchParams.get("offender_id");
      if (deepLinkId && list.length > 0) {
        const match = list.find((o: any) => o.offender_id === deepLinkId);
        if (match) handleSelectOffender(match);
      }
    }).catch(e => {
      console.error(e);
      setError(e.response?.data?.detail || "Failed to connect to backend");
    }).finally(() => {
      setLoading(false);
    });
  }, [searchParams]);

  const handleSelectOffender = async (o: Offender) => {
    setSelected(o);
    setModusOperandi(null);
    try {
      const mo = await offenderService.getModusOperandi(o.offender_id);
      if (mo) setModusOperandi(mo as Record<string, unknown>);
    } catch {
      // fallback handled below
    }
    
    try {
      const risk = await offenderService.getRisk(o.offender_id);
      if (risk) setOffenderRisk(risk);
    } catch {
      // ignore
    }
  };

  const handleSearch = async (q: string) => {
    setSearch(q);
    try {
      const data: any = await offenderService.searchOffenders(q);
      setOffenders(Array.isArray(data) ? data : (data?.offenders || []));
      setError(null);
    } catch (e: any) {
      console.error(e);
      setError(e.response?.data?.detail || "Failed to search offenders");
    }
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading offender database..." /></div>;
  if (error) return <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4"><AlertTriangle className="h-12 w-12 text-red-500" /><p>{error}</p><button onClick={() => window.location.reload()} className="px-4 py-2 bg-slate-800 rounded-lg text-white hover:bg-slate-700">Retry</button></div>;

  return (
    <div className="flex-1 min-h-0 overflow-hidden flex flex-col w-full">
      <div className="p-6 border-b border-slate-700/50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-white">Offender Database</h1>
            <p className="text-sm text-slate-400">{offenders.length} records · Active monitoring</p>
          </div>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text" placeholder="Search by name, district, crime type..."
            value={search} onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-600 text-slate-200 rounded-xl focus:outline-none focus:border-blue-500 text-sm"
          />
        </div>
      </div>

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-2">
          {(Array.isArray(offenders) ? offenders : []).map((o, i) => {
             const statusVal = o.status || o.offender_status;
             return (
            <motion.div key={o.offender_id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
              onClick={() => handleSelectOffender(o)}
              className={`flex items-center gap-4 p-3 rounded-xl cursor-pointer transition-colors border ${
                selected?.offender_id === o.offender_id
                  ? "bg-blue-900/30 border-blue-500/40"
                  : "bg-slate-800/50 border-slate-700/50 hover:bg-slate-800"
              }`}>
              <div className="h-10 w-10 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                <Users className="h-5 w-5 text-slate-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <p className="text-sm font-semibold text-white">{o.offender_name}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    statusVal === "ACTIVE" || statusVal === "Active" ? "bg-red-900/40 text-red-400" :
                    statusVal === "IMPRISONED" || statusVal === "Arrested" || statusVal === "Imprisoned" ? "bg-green-900/40 text-green-400" :
                    statusVal === "ABSCONDING" ? "bg-orange-900/40 text-orange-400" :
                    statusVal === "DECEASED" ? "bg-slate-700 text-slate-400" :
                    "bg-yellow-900/40 text-yellow-400"
                  }`}>{statusVal}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span>{o.age || o.offender_age} yrs</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{o.district}</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><AlertTriangle className="h-3 w-3 text-red-400" />{(o as any).dominant_crime || (o as any).crime_type || o.primary_crime_type}</span>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-600" />
            </motion.div>
          )})}
        </div>

        {/* Detail Panel */}
        {selected && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            className="w-80 min-h-0 border-l border-slate-700/50 overflow-y-auto custom-scrollbar p-4 bg-slate-900/50">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-14 w-14 rounded-full bg-slate-700 flex items-center justify-center">
                <Users className="h-7 w-7 text-slate-400" />
              </div>
              <div>
                <p className="text-sm font-bold text-white">{selected.offender_name}</p>
                <p className="text-xs text-slate-400">ID: {selected.offender_id}</p>
              </div>
            </div>
            <div className="space-y-3">
              <div className="bg-slate-800/60 rounded-lg p-3 space-y-2 text-xs">
                {[
                  ["Age", selected.age || selected.offender_age],
                  ["District", selected.district],
                  ["Crime Count", selected.crime_count || (selected as any).crime_history?.length],
                  ["Primary Crime", selected.primary_crime_type || selected.modus_operandi?.preferred_crime_types?.[0]],
                  ["Last Known Location", selected.last_known_location || "Unknown"],
                ].map(([label, val]) => (
                  <div key={String(label)} className="flex justify-between">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-slate-200 font-medium">{String(val)}</span>
                  </div>
                ))}
              </div>
              {selected.modus_operandi && !modusOperandi && (
                 <div className="bg-slate-800/60 rounded-lg p-3">
                   <p className="text-xs text-slate-400 mb-1 flex items-center gap-1"><Shield className="h-3 w-3" />Modus Operandi</p>
                   <p className="text-xs text-slate-200 leading-relaxed">
                     {typeof selected.modus_operandi === 'string' ? selected.modus_operandi : selected.modus_operandi.typical_target || "N/A"}
                   </p>
                 </div>
              )}
              {modusOperandi && (
                <div className="bg-slate-800/60 rounded-lg p-3 space-y-1">
                  <p className="text-xs font-semibold text-purple-400 mb-2 flex items-center gap-1"><Shield className="h-3 w-3" />Modus Operandi Analysis</p>
                  {Object.entries(modusOperandi).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
                      <span className="text-slate-200 text-right max-w-[60%]">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Risk Score</span>
                  <span className={`font-bold ${selected.risk_score >= 80 ? "text-red-400" : "text-orange-400"}`}>{selected.risk_score}/100</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full">
                  <div className="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500" style={{ width: `${selected.risk_score}%` }} />
                </div>
                <ExplainabilityPanel points={offenderRisk?.risk_factors || selected.risk_factors || []} />
              </div>
              <button
                onClick={() => navigate(`/network?focus=${selected.offender_id}`)}
                className="mt-3 w-full text-xs px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors"
              >
                View in Criminal Network →
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OffenderDatabase;
