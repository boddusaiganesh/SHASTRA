import React from "react";

interface Props { size?: "sm" | "md" | "lg"; text?: string; }

const LoadingSpinner: React.FC<Props> = ({ size = "md", text = "Loading..." }) => {
  const sizes = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" };
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <div className={`${sizes[size]} animate-spin rounded-full border-4 border-blue-500/30 border-t-blue-500`} />
      {text && <p className="text-sm text-slate-400">{text}</p>}
    </div>
  );
};

export default LoadingSpinner;
