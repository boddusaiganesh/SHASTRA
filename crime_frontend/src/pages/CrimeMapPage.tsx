import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { motion } from "framer-motion";
import { MapPin, Info, X } from "lucide-react";
import { RootState } from "../store/store";
import { setMapCrimes, setFilters } from "../store/crimesSlice";
import { crimeService } from "../services/crimeService";
import MapControls from "../components/maps/MapControls";
import CrimeMap from "../components/maps/CrimeMap";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { CRIME_TYPE_COLORS } from "../constants/crimeTypes";
import { formatDateTime } from "../utils/dateFormatter";

interface Crime {
  crime_id: string; crime_type: string; date_time: string; location: string;
  district: string; police_station?: string; status: string; latitude: number; longitude: number;
  victim_id?: string; suspect_id?: string;
}

const CrimeMapPage: React.FC = () => {
  const dispatch = useDispatch();
  const { mapCrimes, filters } = useSelector((s: RootState) => s.crimes);
  const [loading, setLoading] = useState(true);
  const [selectedCrime, setSelectedCrime] = useState<Crime | null>(null);
  const [showCaseModal, setShowCaseModal] = useState(false);
  const [caseDetail, setCaseDetail] = useState<Record<string, unknown> | null>(null);
  const [rightPanelData, setRightPanelData] = useState<{ total: number; byType: Record<string, number> }>({ total: 0, byType: {} });

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await crimeService.getMapData();
      dispatch(setMapCrimes(data));
      setLoading(false);
    };
    fetch();
  }, []);

  useEffect(() => {
    const crimes = mapCrimes as Crime[];
    const byType: Record<string, number> = {};
    crimes.forEach((c) => { byType[c.crime_type] = (byType[c.crime_type] || 0) + 1; });
    setRightPanelData({ total: crimes.length, byType });
  }, [mapCrimes]);

  const filteredCrimes = (mapCrimes as Crime[]).filter((c) => {
    if (filters.crimeType !== "All" && c.crime_type !== filters.crimeType) return false;
    if (filters.district !== "All Districts" && c.district !== filters.district) return false;
    if (filters.dateFrom && new Date(c.date_time) < new Date(filters.dateFrom)) return false;
    if (filters.dateTo && new Date(c.date_time) > new Date(filters.dateTo)) return false;
    if (filters.timeOfDay && filters.timeOfDay !== "All Times") {
       const hour = new Date(c.date_time).getHours();
       if (filters.timeOfDay === "Morning (6AM-12PM)" && (hour < 6 || hour >= 12)) return false;
       if (filters.timeOfDay === "Afternoon (12PM-6PM)" && (hour < 12 || hour >= 18)) return false;
       if (filters.timeOfDay === "Evening (6PM-10PM)" && (hour < 18 || hour >= 22)) return false;
       if (filters.timeOfDay === "Night (10PM-6AM)" && (hour < 22 && hour >= 6)) return false;
    }
    return true;
  });

  const statusColor: Record<string, string> = {
    "Under Investigation": "bg-yellow-900/40 text-yellow-400",
    "FIR Filed": "bg-blue-900/40 text-blue-400",
    "Arrested": "bg-green-900/40 text-green-400",
    "Solved": "bg-green-900/60 text-green-300",
    "Active Search": "bg-red-900/40 text-red-400",
  };

  const handleExport = () => {
    const csv = [
      ["crime_id","crime_type","date_time","location","district","status","latitude","longitude"].join(","),
      ...filteredCrimes.map((c) =>
        [c.crime_id, c.crime_type, c.date_time, `"${c.location?.replace(/"/g, '""') || ''}"`, c.district, c.status, c.latitude, c.longitude].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `crimes_export_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleViewCase = async (crime: Crime) => {
    setShowCaseModal(true);
    setCaseDetail(null);
    const detail = await crimeService.getCrimeDetail(crime.crime_id);
    setCaseDetail(detail as Record<string, unknown>);
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 w-full overflow-hidden">
      {/* Controls */}
      <MapControls
        viewMode={filters.viewMode}
        onViewModeChange={(v) => dispatch(setFilters({ viewMode: v }))}
        crimeType={filters.crimeType}
        onCrimeTypeChange={(v) => dispatch(setFilters({ crimeType: v }))}
        district={filters.district}
        onDistrictChange={(v) => dispatch(setFilters({ district: v }))}
        timeOfDay={filters.timeOfDay}
        onTimeOfDayChange={(v) => dispatch(setFilters({ timeOfDay: v }))}
        dateFrom={filters.dateFrom}
        onDateFromChange={(v) => dispatch(setFilters({ dateFrom: v }))}
        dateTo={filters.dateTo}
        onDateToChange={(v) => dispatch(setFilters({ dateTo: v }))}
        onExport={handleExport}
      />

      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        {/* Map */}
        <div className="flex-1 relative">
          {loading ? (
            <div className="h-full flex items-center justify-center bg-slate-900">
              <LoadingSpinner size="lg" text="Loading crime map data..." />
            </div>
          ) : (
            <CrimeMap crimes={filteredCrimes} viewMode={filters.viewMode} onCrimeSelect={setSelectedCrime} />
          )}

          {/* Crime count badge */}
          <div className="absolute top-3 left-3 z-10 bg-slate-900/90 backdrop-blur border border-slate-700/50 rounded-lg px-3 py-2">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-red-400" />
              <span className="text-sm font-bold text-white">{filteredCrimes.length}</span>
              <span className="text-xs text-slate-400">crimes displayed</span>
            </div>
          </div>

          {/* Legend */}
          <div className="absolute bottom-3 left-3 z-10 bg-slate-900/90 backdrop-blur border border-slate-700/50 rounded-lg p-3">
            <p className="text-xs font-medium text-slate-400 mb-2">Crime Types</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(CRIME_TYPE_COLORS).slice(0, 8).map(([type, color]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full" style={{ background: color }} />
                  <span className="text-xs text-slate-400">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Panel */}
        <div className="w-72 bg-slate-900/95 border-l border-slate-700/50 flex flex-col overflow-y-auto custom-scrollbar">
          <div className="p-4 border-b border-slate-700/50">
            <h3 className="text-sm font-semibold text-white mb-3">Map Statistics</h3>
            <div className="grid grid-cols-2 gap-2 mb-4">
              <div className="bg-slate-800/60 rounded-lg p-2 text-center">
                <p className="text-xl font-bold text-white">{filteredCrimes.length}</p>
                <p className="text-xs text-slate-400">Total Shown</p>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-2 text-center">
                <p className="text-xl font-bold text-green-400">{filteredCrimes.filter(c => c.status === "Solved" || c.status === "Arrested").length}</p>
                <p className="text-xs text-slate-400">Resolved</p>
              </div>
            </div>
            <h4 className="text-xs text-slate-400 mb-2">By Crime Type</h4>
            <div className="space-y-1.5">
              {Object.entries(rightPanelData.byType).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full" style={{ background: CRIME_TYPE_COLORS[type] || "#6366f1" }} />
                    <span className="text-xs text-slate-300">{type}</span>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Selected Crime Detail */}
          {selectedCrime && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Crime Detail</h3>
                <button onClick={() => setSelectedCrime(null)}><X className="h-4 w-4 text-slate-400" /></button>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-blue-400 font-mono font-bold">{selectedCrime.crime_id}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: (CRIME_TYPE_COLORS[selectedCrime.crime_type] || "#6366f1") + "40", color: CRIME_TYPE_COLORS[selectedCrime.crime_type] || "#818cf8" }}>
                    {selectedCrime.crime_type}
                  </span>
                </div>
                <p className="text-sm font-semibold text-white">{selectedCrime.location}</p>
                <p className="text-xs text-slate-400">{selectedCrime.district}</p>
                {selectedCrime.police_station && <p className="text-xs text-slate-500">PS: {selectedCrime.police_station}</p>}
                <p className="text-xs text-slate-400">{formatDateTime(selectedCrime.date_time)}</p>
                <div className="pt-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[selectedCrime.status] || "bg-slate-700 text-slate-400"}`}>
                    {selectedCrime.status}
                  </span>
                </div>
                {selectedCrime.victim_id && <p className="text-xs text-slate-500">Victim: {selectedCrime.victim_id}</p>}
                {selectedCrime.suspect_id && <p className="text-xs text-slate-500">Suspect: {selectedCrime.suspect_id}</p>}
              </div>
              <div className="mt-3 flex gap-2">
                <button onClick={() => handleViewCase(selectedCrime)} className="flex-1 py-1.5 bg-blue-600/20 border border-blue-500/30 text-blue-400 text-xs rounded-lg hover:bg-blue-600/30 transition-colors">View Full Case</button>
                <button className="flex items-center gap-1 py-1.5 px-2 bg-slate-800 text-slate-400 text-xs rounded-lg hover:bg-slate-700 transition-colors">
                  <Info className="h-3 w-3" />
                </button>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {showCaseModal && selectedCrime && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl max-w-2xl w-full p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-white">Case File: {selectedCrime.crime_id}</h2>
              <button onClick={() => setShowCaseModal(false)} className="text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-4">
              {caseDetail ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm max-h-[70vh] overflow-y-auto custom-scrollbar pr-2">
                  {Object.entries(caseDetail)
                    .filter(([k]) => !["latitude","longitude"].includes(k))
                    .map(([k, v]) => (
                      <div key={k} className="bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
                        <span className="block text-xs text-slate-400 capitalize mb-1">{k.replace(/_/g," ")}</span>
                        <span className="block text-slate-200 font-medium break-words">{String(v ?? "—")}</span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="flex justify-center py-8">
                  <div className="h-8 w-8 rounded-full border-2 border-blue-400/30 border-t-blue-400 animate-spin" />
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setShowCaseModal(false)} className="px-4 py-2 bg-slate-700 text-white text-sm rounded-lg hover:bg-slate-600">Close</button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
};

export default CrimeMapPage;
