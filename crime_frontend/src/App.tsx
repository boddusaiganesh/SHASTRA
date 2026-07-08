import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, X } from "lucide-react";
import { RootState } from "./store/store";
import { setAlerts, addAlert } from "./store/alertsSlice";
import { alertService } from "./services/alertService";

import Navbar from "./components/common/Navbar";
import Sidebar from "./components/common/Sidebar";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import CrimeMapPage from "./pages/CrimeMapPage";
import HotspotAnalysis from "./pages/HotspotAnalysis";
import CriminalNetwork from "./pages/CriminalNetwork";
import AnomalyDetection from "./pages/AnomalyDetection";
import PredictiveAnalytics from "./pages/PredictiveAnalytics";
import CrimeDatabase from "./pages/CrimeDatabase";
import OffenderDatabase from "./pages/OffenderDatabase";
import AlertsPage from "./pages/AlertsPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import VictimDatabase from "./pages/VictimDatabase";
import SocioEconomicInsights from "./pages/SocioEconomicInsights";
import AIChatWidget from "./components/common/AIChatWidget";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  const alerts = useSelector((state: RootState) => state.alerts);
  const dispatch = useDispatch();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [toasts, setToasts] = useState<any[]>([]);

  const addToast = (alert: any) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { ...alert, _id: id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t._id !== id));
    }, 5000);
  };

  useEffect(() => {
    if (isAuthenticated) {
      // Validate session on mount
      import("./services/authService").then(({ authService }) => {
        authService.verifyToken().catch(() => {
          import("./store/authSlice").then(({ logout }) => {
            dispatch(logout());
          });
        });
      });

      alertService.getAlerts().then((data) => dispatch(setAlerts(data)));
      
      let ws: WebSocket;
      let retryDelay = 1000;
      let closedByUs = false;

      const connect = () => {
        const token = localStorage.getItem("auth_token");
        const base = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/alerts/ws";
        ws = new WebSocket(`${base}?token=${encodeURIComponent(token || "")}`);

        ws.onopen = () => { retryDelay = 1000; };
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "NEW_ALERT") {
              dispatch(addAlert(msg.data));
              addToast(msg.data);
            }
          } catch (e) {
            console.error("WS message parse error", e);
          }
        };
        ws.onclose = () => {
          if (closedByUs) return;
          setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30000);
        };
      };

      connect();
      return () => { closedByUs = true; ws?.close(); };
    }
  }, [isAuthenticated, dispatch]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen bg-slate-900 overflow-hidden text-slate-200">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        alertCount={alerts?.unreadCount || 0}
      />
      <div className="flex flex-col flex-1 overflow-hidden min-w-0 min-h-0">
        <Navbar alertCount={alerts?.unreadCount || 0} />
        <main className="flex-1 overflow-y-auto custom-scrollbar bg-slate-900 flex flex-col min-h-0 min-w-0 relative">
          {children}
          {/* Floating UI Elements */}
          <AIChatWidget />
          
          {/* Toasts */}
          <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2">
            <AnimatePresence>
              {toasts.map((t) => (
                <motion.div
                  key={t._id}
                  initial={{ opacity: 0, y: 20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-slate-800 border-l-4 border-red-500 shadow-xl rounded-lg p-4 w-80 flex items-start gap-3"
                >
                  <div className="bg-red-500/20 p-2 rounded-full mt-1">
                    <Bell className="h-4 w-4 text-red-400" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-white mb-1">{t.title}</h4>
                    <p className="text-xs text-slate-400 line-clamp-2">{t.description}</p>
                  </div>
                  <button onClick={() => setToasts(prev => prev.filter(x => x._id !== t._id))} className="text-slate-500 hover:text-white">
                    <X className="h-4 w-4" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/map" element={<ProtectedRoute><CrimeMapPage /></ProtectedRoute>} />
        <Route path="/crimes" element={<ProtectedRoute><CrimeDatabase /></ProtectedRoute>} />
        <Route path="/hotspots" element={<ProtectedRoute><HotspotAnalysis /></ProtectedRoute>} />
        <Route path="/network" element={<ProtectedRoute><CriminalNetwork /></ProtectedRoute>} />
        <Route path="/anomalies" element={<ProtectedRoute><AnomalyDetection /></ProtectedRoute>} />
        <Route path="/predictions" element={<ProtectedRoute><PredictiveAnalytics /></ProtectedRoute>} />
        <Route path="/offenders" element={<ProtectedRoute><OffenderDatabase /></ProtectedRoute>} />
        <Route path="/victims" element={<ProtectedRoute><VictimDatabase /></ProtectedRoute>} />
        <Route path="/socioeconomic" element={<ProtectedRoute><SocioEconomicInsights /></ProtectedRoute>} />
        <Route path="/alerts" element={<ProtectedRoute><AlertsPage /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
