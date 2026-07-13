import React, { useState, useEffect } from "react";

interface Props { size?: "sm" | "md" | "lg"; text?: string; showProgress?: boolean; }

const LoadingSpinner: React.FC<Props> = ({ size = "md", text = "Loading...", showProgress }) => {
  const sizes = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" };
  const [progress, setProgress] = useState(0);

  const isProgressEnabled = showProgress !== undefined ? showProgress : size === "lg";

  useEffect(() => {
    if (!isProgressEnabled) return;
    const interval = setInterval(() => {
      setProgress(p => {
        const remaining = 95 - p;
        if (remaining <= 0) return p;
        const step = Math.max(0.5, remaining * (Math.random() * 0.15));
        return Math.min(95, p + step);
      });
    }, 150);
    return () => clearInterval(interval);
  }, [isProgressEnabled]);

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <div className={`${sizes[size]} animate-spin rounded-full border-4 border-blue-500/30 border-t-blue-500`} />
      {text && (
        <div className="flex flex-col items-center gap-2 mt-2">
          <p className="text-sm text-slate-400">
            {text} {isProgressEnabled && <span className="text-blue-400 font-medium ml-1">{Math.round(progress)}%</span>}
          </p>
          {isProgressEnabled && (
            <div className="w-48 h-1.5 bg-slate-800 rounded-full overflow-hidden shadow-inner">
               <div 
                 className="h-full bg-blue-500 rounded-full transition-all duration-300 ease-out shadow-[0_0_8px_rgba(59,130,246,0.5)]"
                 style={{ width: `${progress}%` }}
               />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LoadingSpinner;
