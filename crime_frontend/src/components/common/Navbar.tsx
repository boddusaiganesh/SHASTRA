import React, { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "../../store/store";
import { logout } from "../../store/authSlice";
import { clearUnreadCount } from "../../store/alertsSlice";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Shield, User, Clock } from "lucide-react";
import dayjs from "dayjs";

interface Props { alertCount?: number; }

const Navbar: React.FC<Props> = ({ alertCount = 0 }) => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const auth = useSelector((s: RootState) => s.auth);
  const [now, setNow] = useState(dayjs());

  useEffect(() => {
    const t = setInterval(() => setNow(dayjs()), 1000);
    return () => clearInterval(t);
  }, []);

  const handleLogout = () => {
    dispatch(logout());
    navigate("/login");
  };

  return (
    <header className="h-14 bg-slate-900/95 backdrop-blur border-b border-slate-700/50 flex items-center px-4 gap-4 z-40 sticky top-0">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
          <Shield className="h-4 w-4 text-white" />
        </div>
        <div className="hidden sm:block">
          <p className="text-xs font-bold text-white leading-tight">Karnataka Police</p>
          <p className="text-xs text-blue-400 leading-tight font-semibold tracking-wide">SHASTRA Platform</p>
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Date/Time */}
      <div className="hidden md:flex items-center gap-1.5 text-slate-400 text-xs">
        <Clock className="h-3.5 w-3.5" />
        <span>{now.format("DD MMM YYYY, HH:mm:ss")}</span>
      </div>

      {/* User */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
        <User className="h-4 w-4 text-blue-400" />
        <div className="hidden sm:block">
          <p className="text-xs text-white font-medium leading-tight">{auth.user_name}</p>
          <p className="text-xs text-slate-400 leading-tight">{auth.user_role}</p>
        </div>
      </div>

      {/* Notifications */}
      <button
        onClick={() => {
          dispatch(clearUnreadCount());
          navigate("/alerts");
        }}
        className="relative p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
      >
        <Bell className="h-5 w-5" />
        {alertCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-red-500 text-xs flex items-center justify-center text-white animate-pulse">
            {alertCount > 9 ? "9+" : alertCount}
          </span>
        )}
      </button>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:text-white hover:bg-red-600 rounded-lg transition-all"
      >
        <LogOut className="h-4 w-4" />
        <span className="hidden sm:inline">Logout</span>
      </button>
    </header>
  );
};

export default Navbar;
