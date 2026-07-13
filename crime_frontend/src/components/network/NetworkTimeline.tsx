import React, { useMemo } from "react";
import { CRIME_TYPE_COLORS } from "../../constants/crimeTypes";

interface TimelineEvent { crime_id: string; date: string; crime_type: string; district_id: string; status: string; }
interface Props {
  events: TimelineEvent[];
  onSelectDate?: (date: string | null) => void;
  selectedDate?: string | null;
}

const NetworkTimeline: React.FC<Props> = ({ events, onSelectDate, selectedDate }) => {
  const sorted = useMemo(() => [...events].sort((a, b) => a.date.localeCompare(b.date)), [events]);
  if (sorted.length === 0) return null;

  const minTime = new Date(sorted[0].date).getTime();
  const maxTime = new Date(sorted[sorted.length - 1].date).getTime();
  const span = Math.max(1, maxTime - minTime);

  return (
    <div className="h-20 bg-slate-900/95 border-t border-slate-700/50 px-4 py-2 relative">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-400">Timeline · {sorted.length} linked crimes</span>
        {selectedDate && (
          <button onClick={() => onSelectDate?.(null)} className="text-xs text-blue-400 hover:underline">Clear selection</button>
        )}
      </div>
      <div className="relative h-8 bg-slate-800/50 rounded-full">
        {sorted.map((e) => {
          const pct = span === 0 ? 50 : ((new Date(e.date).getTime() - minTime) / span) * 100;
          const isSelected = selectedDate === e.date;
          return (
            <button
              key={e.crime_id}
              title={`${e.crime_type} — ${new Date(e.date).toLocaleDateString()}`}
              onClick={() => onSelectDate?.(isSelected ? null : e.date)}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 transition-transform hover:scale-125"
              style={{
                left: `${pct}%`,
                width: isSelected ? 14 : 10,
                height: isSelected ? 14 : 10,
                background: (CRIME_TYPE_COLORS as any)[e.crime_type] || "#6366f1",
                borderColor: isSelected ? "#fff" : "transparent",
                zIndex: isSelected ? 10 : 1,
              }}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-slate-500">
        <span>{new Date(sorted[0].date).toLocaleDateString()}</span>
        <span>{new Date(sorted[sorted.length - 1].date).toLocaleDateString()}</span>
      </div>
    </div>
  );
};

export default NetworkTimeline;
