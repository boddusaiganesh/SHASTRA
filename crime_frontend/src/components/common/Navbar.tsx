import React, { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "../../store/store";
import { logout } from "../../store/authSlice";
import { authService } from "../../services/authService";
import { clearUnreadCount } from "../../store/alertsSlice";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, User, Clock, Search, Languages } from "lucide-react";
import dayjs from "dayjs";
import { useTranslation } from "react-i18next";

interface Props { alertCount?: number; }

const Navbar: React.FC<Props> = ({ alertCount = 0 }) => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const auth = useSelector((s: RootState) => s.auth);
  const [now, setNow] = useState(dayjs());
  const { t, i18n } = useTranslation();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{crimes: any[], offenders: any[], victims: any[]}>({crimes: [], offenders: [], victims: []});
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setNow(dayjs()), 1000);
    return () => clearInterval(t);
  }, []);

  const handleLogout = async () => {
    try {
      await authService.logout();
    } catch (e) {
      console.error("Logout request failed, clearing local session anyway", e);
    } finally {
      dispatch(logout());
      navigate("/");
    }
  };

  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language === "en" ? "kn" : "en");
  };

  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults({crimes: [], offenders: [], victims: []});
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      setShowDropdown(true);
      try {
        const api = (await import("../../services/api")).default;
        const { ENDPOINTS } = await import("../../constants/apiEndpoints");
        const res = await api.get(ENDPOINTS.SEARCH.GLOBAL, { params: { q: searchQuery } });
        const unwrapped = res.data?.data || res.data;
        setSearchResults({
          crimes: Array.isArray(unwrapped?.crimes) ? unwrapped.crimes : [],
          offenders: Array.isArray(unwrapped?.offenders) ? unwrapped.offenders : [],
          victims: Array.isArray(unwrapped?.victims) ? unwrapped.victims : [],
        });
      } catch (e) {
        console.error(e);
      }
      setIsSearching(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchQuery, auth.auth_token]);

  return (
    <>
      <header className="h-14 bg-slate-900/95 backdrop-blur border-b border-slate-700/50 flex items-center px-4 gap-4 z-40 sticky top-0">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="h-9 w-9 rounded-full bg-slate-900 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 overflow-hidden shadow-[0_0_10px_rgba(79,70,229,0.3)]">
          <img src={`${import.meta.env.BASE_URL}shastra_logo.png`} alt="SHASTRA Logo" className="h-full w-full object-cover scale-110" />
        </div>
        <div className="hidden sm:block">
          <p className="text-xs font-bold text-white leading-tight">Karnataka Police</p>
          <p className="text-xs text-blue-400 leading-tight font-semibold tracking-wide">SHASTRA Platform</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative hidden md:block w-64 z-50">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input
          type="text"
          placeholder={t("navbar.search", "Search...")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => searchQuery.length >= 2 && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          className="w-full pl-10 pr-4 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
        />
        
        {showDropdown && (
          <div className="absolute top-full mt-2 w-80 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden flex flex-col">
            {isSearching && <div className="p-3 text-xs text-slate-400 text-center">Searching...</div>}
            {!isSearching && searchResults.crimes.length === 0 && searchResults.offenders.length === 0 && (
              <div className="p-3 text-xs text-slate-400 text-center">No results found</div>
            )}
            {!isSearching && searchResults.crimes.length > 0 && (
              <div className="flex flex-col">
                <div className="bg-slate-900/50 px-3 py-1.5 text-xs font-semibold text-slate-300">Crimes</div>
                {searchResults.crimes.map(c => (
                  <div key={c.crime_id} className="px-3 py-2 border-b border-slate-700/50 hover:bg-slate-700/50 cursor-pointer text-xs" onClick={() => navigate('/crimes')}>
                    <div className="text-white font-medium">{c.crime_id}</div>
                    <div className="text-slate-400">{c.crime_type} • {c.district}</div>
                  </div>
                ))}
              </div>
            )}
            {!isSearching && searchResults.offenders.length > 0 && (
              <div className="flex flex-col">
                <div className="bg-slate-900/50 px-3 py-1.5 text-xs font-semibold text-slate-300">Offenders</div>
                {searchResults.offenders.map(o => (
                  <div key={o.offender_id} className="px-3 py-2 border-b border-slate-700/50 hover:bg-slate-700/50 cursor-pointer text-xs" onClick={() => navigate('/offenders')}>
                    <div className="text-white font-medium">{o.first_name} {o.last_name}</div>
                    <div className="text-slate-400">{o.risk_level} Risk</div>
                  </div>
                ))}
              </div>
            )}
            {!isSearching && searchResults.victims && searchResults.victims.length > 0 && (
              <div className="flex flex-col">
                <div className="bg-slate-900/50 px-3 py-1.5 text-xs font-semibold text-slate-300">Victims</div>
                {searchResults.victims.map(v => (
                  <div key={v.victim_id} className="px-3 py-2 border-b border-slate-700/50 hover:bg-slate-700/50 cursor-pointer text-xs" onClick={() => navigate('/crimes')}>
                    <div className="text-white font-medium">{v.first_name} {v.last_name}</div>
                    <div className="text-slate-400">{v.phone_number || "No Phone"}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Language Toggle */}
      <button
        onClick={toggleLanguage}
        className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
        title="Toggle Language"
      >
        <Languages className="h-5 w-5" />
      </button>

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
  </>
);
};

export default Navbar;
