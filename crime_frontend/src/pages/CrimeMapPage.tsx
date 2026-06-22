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
    return true;
  });

  const statusColor: Record<string, string> = {
    "Under Investigation": "bg-yellow-900/40 text-yellow-400",
    "FIR Filed": "bg-blue-900/40 text-blue-400",
    "Arrested": "bg-green-900/40 text-green-400",
    "Solved": "bg-green-900/60 text-green-300",
    "Active Search": "bg-red-900/40 text-red-400",
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
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
      />

      <div className="flex flex-1 overflow-hidden relative">
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
        <div className="w-72 bg-slate-900/95 border-l border-slate-700/50 flex flex-col overflow-y-auto">
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
                <button className="flex-1 py-1.5 bg-blue-600/20 border border-blue-500/30 text-blue-400 text-xs rounded-lg hover:bg-blue-600/30 transition-colors">View Full Case</button>
                <button className="flex items-center gap-1 py-1.5 px-2 bg-slate-800 text-slate-400 text-xs rounded-lg hover:bg-slate-700 transition-colors">
                  <Info className="h-3 w-3" />
                </button>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CrimeMapPage;
