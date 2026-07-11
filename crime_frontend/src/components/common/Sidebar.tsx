import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Map, Flame, Network, Users, Brain,
  AlertOctagon, Bell, FileText, Settings, Shield, ChevronLeft, ChevronRight, PieChart, Database,
} from "lucide-react";

const navItems = [
  { path: "/",          label: "Dashboard",             icon: LayoutDashboard },
  { path: "/map",       label: "Crime Map",             icon: Map },
  { path: "/hotspots",  label: "Hotspot Analysis",      icon: Flame },
  { path: "/crimes",    label: "Crime Database",        icon: Database },
  { path: "/network",   label: "Criminal Network",      icon: Network },
  { path: "/offenders", label: "Offender Profiles",     icon: Users },
  { path: "/victims",   label: "Victim Database",       icon: Users },
  { path: "/predictions",label:"Predictive Intelligence",icon: Brain },
  { path: "/anomalies", label: "Anomaly Detection",     icon: AlertOctagon },
  { path: "/alerts",    label: "Alerts",                icon: Bell },
  { path: "/reports",   label: "Intelligence Reports",  icon: FileText },
  { path: "/socioeconomic", label: "Socio-Economic",    icon: PieChart },
  { path: "/settings",  label: "Settings",              icon: Settings },
];

interface Props { collapsed: boolean; onToggle: () => void; alertCount?: number; }

const Sidebar: React.FC<Props> = ({ collapsed, onToggle, alertCount = 0 }) => {
  return (
    <>
      {/* Mobile overlay */}
      {!collapsed && (
        <div 
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={onToggle}
        />
      )}
      <aside className={`
        ${collapsed ? "w-16 -translate-x-full md:translate-x-0" : "w-64 translate-x-0"} 
        transition-all duration-300 bg-slate-900 border-r border-slate-700/50 flex flex-col h-full
        fixed md:relative z-50
      `}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-slate-700/50">
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
          <Shield className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <p className="text-xs font-bold text-white leading-tight">Karnataka</p>
            <p className="text-xs text-blue-400 leading-tight font-semibold tracking-wide">SHASTRA</p>
          </div>
        )}
        <button onClick={onToggle} className="ml-auto text-slate-400 hover:text-white transition-colors">
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto custom-scrollbar">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 mx-2 rounded-lg mb-1 transition-all duration-200 group relative
              ${isActive
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-slate-400 hover:bg-slate-800 hover:text-white"}`
            }
          >
            <div className="relative flex-shrink-0">
              <Icon className="h-5 w-5" />
              {path === "/alerts" && alertCount > 0 && (
                <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-red-500 text-xs flex items-center justify-center text-white" style={{ fontSize: "8px" }}>{alertCount > 9 ? "9+" : alertCount}</span>
              )}
            </div>
            {!collapsed && <span className="text-sm font-medium truncate">{label}</span>}
            {collapsed && (
              <div className="absolute left-full ml-2 px-2 py-1 bg-slate-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none">
                {label}
              </div>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
    </>
  );
};

export default Sidebar;
