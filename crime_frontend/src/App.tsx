import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useSelector } from "react-redux";
import { RootState } from "./store/store";

import Navbar from "./components/common/Navbar";
import Sidebar from "./components/common/Sidebar";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import CrimeMapPage from "./pages/CrimeMapPage";
import HotspotAnalysis from "./pages/HotspotAnalysis";
import CriminalNetwork from "./pages/CriminalNetwork";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return (
    <div className="flex h-screen bg-slate-900 overflow-hidden text-slate-200">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-hidden bg-slate-900">
          {children}
        </main>
      </div>
    </div>
  );
};

const PlaceholderPage = ({ title }: { title: string }) => (
  <div className="flex-1 p-8">
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
      <h2 className="text-2xl font-bold text-white mb-2">{title}</h2>
      <p className="text-slate-400">This module is currently under development or integration.</p>
    </div>
  </div>
);

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/map" element={<ProtectedRoute><CrimeMapPage /></ProtectedRoute>} />
        <Route path="/hotspots" element={<ProtectedRoute><HotspotAnalysis /></ProtectedRoute>} />
        <Route path="/network" element={<ProtectedRoute><CriminalNetwork /></ProtectedRoute>} />
        
        {/* Missing Routes mapped to Placeholder */}
        <Route path="/anomalies" element={<ProtectedRoute><PlaceholderPage title="Anomaly Detection" /></ProtectedRoute>} />
        <Route path="/predictions" element={<ProtectedRoute><PlaceholderPage title="Predictive Analytics" /></ProtectedRoute>} />
        <Route path="/offenders" element={<ProtectedRoute><PlaceholderPage title="Offender Database" /></ProtectedRoute>} />
        <Route path="/alerts" element={<ProtectedRoute><PlaceholderPage title="System Alerts" /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute><PlaceholderPage title="Executive Reports" /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><PlaceholderPage title="Platform Settings" /></ProtectedRoute>} />
        
        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
