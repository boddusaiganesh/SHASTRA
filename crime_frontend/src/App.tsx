import React, { useState, useEffect, Suspense } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, X } from "lucide-react";
import { RootState } from "./store/store";
import { setAlerts, addAlert } from "./store/alertsSlice";
import { alertService } from "./services/alertService";

import Navbar from "./components/common/Navbar";
import Sidebar from "./components/common/Sidebar";
import ErrorBoundary from "./components/common/ErrorBoundary";

import LoadingSpinner from "./components/common/LoadingSpinner";

const Login = React.lazy(() => import("./pages/Login"));
const LandingPage = React.lazy(() => import("./pages/LandingPage"));
const Dashboard = React.lazy(() => import("./pages/Dashboard"));
const CrimeMapPage = React.lazy(() => import("./pages/CrimeMapPage"));
const HotspotAnalysis = React.lazy(() => import("./pages/HotspotAnalysis"));
const CriminalNetwork = React.lazy(() => import("./pages/CriminalNetwork"));
const AnomalyDetection = React.lazy(() => import("./pages/AnomalyDetection"));
const PredictiveAnalytics = React.lazy(() => import("./pages/PredictiveAnalytics"));
const CrimeDatabase = React.lazy(() => import("./pages/CrimeDatabase"));
const OffenderDatabase = React.lazy(() => import("./pages/OffenderDatabase"));
const AlertsPage = React.lazy(() => import("./pages/AlertsPage"));
const ReportsPage = React.lazy(() => import("./pages/ReportsPage"));
const SettingsPage = React.lazy(() => import("./pages/SettingsPage"));
const VictimDatabase = React.lazy(() => import("./pages/VictimDatabase"));
const SocioEconomicInsights = React.lazy(() => import("./pages/SocioEconomicInsights"));
import AIChatWidget from "./components/common/AIChatWidget";
import AIMarkdown from "./components/common/AIMarkdown";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  const alerts = useSelector((state: RootState) => state.alerts);
  const dispatch = useDispatch();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(window.innerWidth < 768);
  const [toasts, setToasts] = useState<any[]>([]);

  const addToast = (alert: any) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { ...alert, _id: id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t._id !== id));
    }, 5000);
  };

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarCollapsed(true);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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

      alertService.getAlerts()
        .then((data) => dispatch(setAlerts(data)))
        .catch((e) => console.error("Failed to load initial alerts", e));
      
      let ws: WebSocket;
      let retryDelay = 1000;
      let closedByUs = false;

      const connect = () => {
        try {
          const rawUrl = import.meta.env.VITE_WS_URL;
          const base = rawUrl?.startsWith("ws")
            ? rawUrl
            : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${
                rawUrl || "/api/alerts/ws"
              }`;
          ws = new WebSocket(base);

          ws.onopen = () => { 
            retryDelay = 1000;
          };
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
          ws.onclose = (event) => {
            if (closedByUs || event.code === 1008) return;
            setTimeout(connect, retryDelay);
            retryDelay = Math.min(retryDelay * 2, 30000);
          };
        } catch (err) {
          console.error("Failed to construct WebSocket connection:", err);
          if (!closedByUs) {
            setTimeout(connect, retryDelay);
            retryDelay = Math.min(retryDelay * 2, 30000);
          }
        }
      };

      connect();
      return () => { closedByUs = true; ws?.close(); };
    }
  }, [isAuthenticated, dispatch]);

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
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
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-bold text-white mb-1 truncate">{t.title}</h4>
                    <div className="text-xs text-slate-400 line-clamp-2"><AIMarkdown text={typeof t.description === 'string' ? t.description : (t.description ? JSON.stringify(t.description) : '')} /></div>
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
      <Suspense fallback={<div className="h-screen w-screen flex items-center justify-center bg-slate-900"><LoadingSpinner size="lg" text="Loading module..." /></div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard" element={<ProtectedRoute><ErrorBoundary><Dashboard /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/map" element={<ProtectedRoute><ErrorBoundary><CrimeMapPage /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/crimes" element={<ProtectedRoute><ErrorBoundary><CrimeDatabase /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/hotspots" element={<ProtectedRoute><ErrorBoundary><HotspotAnalysis /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/network" element={<ProtectedRoute><ErrorBoundary><CriminalNetwork /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/anomalies" element={<ProtectedRoute><ErrorBoundary><AnomalyDetection /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/predictions" element={<ProtectedRoute><ErrorBoundary><PredictiveAnalytics /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/offenders" element={<ProtectedRoute><ErrorBoundary><OffenderDatabase /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/victims" element={<ProtectedRoute><ErrorBoundary><VictimDatabase /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/socioeconomic" element={<ProtectedRoute><ErrorBoundary><SocioEconomicInsights /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/alerts" element={<ProtectedRoute><ErrorBoundary><AlertsPage /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><ErrorBoundary><ReportsPage /></ErrorBoundary></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><ErrorBoundary><SettingsPage /></ErrorBoundary></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
