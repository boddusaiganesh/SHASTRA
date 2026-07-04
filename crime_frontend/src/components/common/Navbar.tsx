import React, { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "../../store/store";
import { logout } from "../../store/authSlice";
import { clearUnreadCount } from "../../store/alertsSlice";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Shield, User, Clock, AlertTriangle, Search, Languages } from "lucide-react";
import dayjs from "dayjs";
import { useTranslation } from "react-i18next";

interface Props { alertCount?: number; }

const Navbar: React.FC<Props> = ({ alertCount = 0 }) => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const auth = useSelector((s: RootState) => s.auth);
  const [now, setNow] = useState(dayjs());
  const { t, i18n } = useTranslation();

  const [usingMockData, setUsingMockData] = useState((window as any).__using_mock_data || false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{crimes: any[], offenders: any[]}>({crimes: [], offenders: []});
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    const handleMockData = () => setUsingMockData(true);
    window.addEventListener("mock-data-detected", handleMockData);
    return () => window.removeEventListener("mock-data-detected", handleMockData);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNow(dayjs()), 1000);
    return () => clearInterval(t);
  }, []);

  const handleLogout = () => {
    dispatch(logout());
    navigate("/login");
  };

  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language === "en" ? "kn" : "en");
  };

  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults({crimes: [], offenders: []});
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      setShowDropdown(true);
      try {
        const res = await fetch(`http://localhost:8000/api/search/global?q=${searchQuery}`, {
          headers: { "Authorization": `Bearer ${auth.token}` }
        });
        if (res.ok) {
          const json = await res.json();
          setSearchResults(json.data);
        }
      } catch (e) {
        console.error(e);
      }
      setIsSearching(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchQuery, auth.token]);

  return (
    <>
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
    {usingMockData && (
      <div className="bg-amber-500/10 border-b border-amber-500/30 text-amber-400 text-xs py-1.5 px-4 text-center font-medium z-30 flex items-center justify-center gap-1.5 backdrop-blur-sm flex-shrink-0">
        <AlertTriangle className="h-3.5 w-3.5 text-amber-500 animate-pulse" />
        <span>Offline Mode: Backend connection unavailable. Displaying simulated mock intelligence data.</span>
      </div>
    )}
  </>
);
};

export default Navbar;
