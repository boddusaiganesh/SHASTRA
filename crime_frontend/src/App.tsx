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

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/map" element={<ProtectedRoute><CrimeMapPage /></ProtectedRoute>} />
        <Route path="/hotspots" element={<ProtectedRoute><HotspotAnalysis /></ProtectedRoute>} />
        <Route path="/network" element={<ProtectedRoute><CriminalNetwork /></ProtectedRoute>} />
        
        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
