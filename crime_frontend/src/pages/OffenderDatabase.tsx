import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, Search, Shield, ChevronRight } from "lucide-react";
import { offenderService } from "../services/predictionService";
import LoadingSpinner from "../components/common/LoadingSpinner";

interface Offender {
  offender_id: string; offender_name: string; age: number; offender_age?: number; district: string;
  crime_count: number; primary_crime_type: string; risk_score: number;
  status: string; offender_status?: string; last_known_location: string; modus_operandi: any;
  photo_url?: string;
}

const OffenderDatabase: React.FC = () => {
  const [offenders, setOffenders] = useState<Offender[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Offender | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    offenderService.searchOffenders().then((d) => {
      setOffenders(d as unknown as Offender[]);
      setLoading(false);
    });
  }, []);

  const handleSearch = async (q: string) => {
    setSearch(q);
    const data = await offenderService.searchOffenders(q);
    setOffenders(data as unknown as Offender[]);
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading offender database..." /></div>;

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
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

      <div className="flex-1 overflow-hidden flex">
        {/* List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {offenders.map((o, i) => {
             const statusVal = o.status || o.offender_status;
             return (
            <motion.div key={o.offender_id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
              onClick={() => setSelected(o)}
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
                    statusVal === "Active" ? "bg-red-900/40 text-red-400" :
                    statusVal === "Arrested" || statusVal === "Imprisoned" ? "bg-green-900/40 text-green-400" :
                    "bg-yellow-900/40 text-yellow-400"
                  }`}>{statusVal}</span>
                </div>
                <p className="text-xs text-slate-400">{o.primary_crime_type || (o.modus_operandi?.preferred_crime_types?.[0])} · {o.district}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className={`text-sm font-bold ${o.risk_score >= 80 ? "text-red-400" : o.risk_score >= 60 ? "text-orange-400" : "text-yellow-400"}`}>{o.risk_score}</p>
                <p className="text-xs text-slate-500">Risk</p>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-600" />
            </motion.div>
          )})}
        </div>

        {/* Detail Panel */}
        {selected && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            className="w-80 border-l border-slate-700/50 overflow-y-auto p-4 bg-slate-900/50">
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
              {selected.modus_operandi && (
                 <div className="bg-slate-800/60 rounded-lg p-3">
                   <p className="text-xs text-slate-400 mb-1 flex items-center gap-1"><Shield className="h-3 w-3" />Modus Operandi</p>
                   <p className="text-xs text-slate-200 leading-relaxed">
                     {typeof selected.modus_operandi === 'string' ? selected.modus_operandi : selected.modus_operandi.typical_target || "N/A"}
                   </p>
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
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OffenderDatabase;
