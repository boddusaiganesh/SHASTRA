import React from "react";
import { Layers, MapPin, Flame, Download } from "lucide-react";
import { CRIME_TYPES, TIME_OF_DAY } from "../../constants/crimeTypes";
import { useDistricts } from "../../hooks/useDistricts";

interface Props {
  viewMode: "heatmap" | "cluster" | "pins";
  onViewModeChange: (mode: "heatmap" | "cluster" | "pins") => void;
  crimeType: string;
  onCrimeTypeChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  timeOfDay: string;
  onTimeOfDayChange: (v: string) => void;
  dateFrom: string;
  onDateFromChange: (v: string) => void;
  dateTo: string;
  onDateToChange: (v: string) => void;
  onExport?: () => void;
}

const MapControls: React.FC<Props> = ({
  viewMode, onViewModeChange, crimeType, onCrimeTypeChange,
  district, onDistrictChange, timeOfDay, onTimeOfDayChange,
  dateFrom, onDateFromChange, dateTo, onDateToChange, onExport
}) => {
  const selectClass = "bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500";
  const inputClass = "bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500";
  const districts = useDistricts();
  const btnClass = (active: boolean) =>
    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${active ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white"}`;

  return (
    <div className="flex items-center gap-2 p-3 bg-slate-900/90 backdrop-blur border-b border-slate-700/50 overflow-x-auto custom-scrollbar whitespace-nowrap">
      <input type="date" value={dateFrom} onChange={(e) => onDateFromChange(e.target.value)} className={inputClass} />
      <span className="text-slate-500 text-xs">to</span>
      <input type="date" value={dateTo} onChange={(e) => onDateToChange(e.target.value)} className={inputClass} />
      <select value={crimeType} onChange={(e) => onCrimeTypeChange(e.target.value)} className={selectClass}>
        {CRIME_TYPES.map((t) => <option key={t}>{t}</option>)}
      </select>
      <select value={district} onChange={(e) => onDistrictChange(e.target.value)} className={selectClass}>
        <option value="All Districts">All Districts</option>
        {districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
      </select>
      <select value={timeOfDay} onChange={(e) => onTimeOfDayChange(e.target.value)} className={selectClass}>
        {TIME_OF_DAY.map((t) => <option key={t}>{t}</option>)}
      </select>
      <div className="flex items-center gap-1 ml-2">
        <button onClick={() => onViewModeChange("heatmap")} className={btnClass(viewMode === "heatmap")}><Flame className="h-3.5 w-3.5" />Heatmap</button>
        <button onClick={() => onViewModeChange("cluster")} className={btnClass(viewMode === "cluster")}><Layers className="h-3.5 w-3.5" />Cluster</button>
        <button onClick={() => onViewModeChange("pins")} className={btnClass(viewMode === "pins")}><MapPin className="h-3.5 w-3.5" />Pins</button>
      </div>
      <button 
        onClick={onExport}
        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 text-slate-300 text-xs rounded-lg hover:bg-slate-600 transition-colors"
      >
        <Download className="h-3.5 w-3.5" />Export
      </button>
    </div>
  );
};

export default MapControls;
