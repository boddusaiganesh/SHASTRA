import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./store/store";
import { setAlerts } from "./store/alertsSlice";
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
import OffenderDatabase from "./pages/OffenderDatabase";
import AlertsPage from "./pages/AlertsPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  const alerts = useSelector((state: RootState) => state.alerts);
  const dispatch = useDispatch();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      alertService.getAlerts().then((data) => dispatch(setAlerts(data)));
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
      <div className="flex flex-col flex-1 overflow-hidden">
        <Navbar alertCount={alerts?.unreadCount || 0} />
        <main className="flex-1 overflow-hidden bg-slate-900">
          {children}
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
        <Route path="/hotspots" element={<ProtectedRoute><HotspotAnalysis /></ProtectedRoute>} />
        <Route path="/network" element={<ProtectedRoute><CriminalNetwork /></ProtectedRoute>} />
        <Route path="/anomalies" element={<ProtectedRoute><AnomalyDetection /></ProtectedRoute>} />
        <Route path="/predictions" element={<ProtectedRoute><PredictiveAnalytics /></ProtectedRoute>} />
        <Route path="/offenders" element={<ProtectedRoute><OffenderDatabase /></ProtectedRoute>} />
        <Route path="/alerts" element={<ProtectedRoute><AlertsPage /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
