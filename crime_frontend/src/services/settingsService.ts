import { flagMockDataUsed } from '../utils/mockDataFlag';
import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockUsers, mockDataSources, mockAlertThresholds } from "./mockData";

export const settingsService = {
  getUsers: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.USERS);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockUsers; }
      throw error;
    }
  },
  addUser: async (user: Record<string, string>) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.USERS_ADD, user);
      return res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return { user: { ...user, user_id: "mock-id-" + Math.random().toString(36).substring(2, 11) } }; }
      throw error;
    }
  },
  getDistricts: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.DISTRICTS);
      return res.data?.data || res.data || [];
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return []; }
      throw error;
    }
  },
  getAlertThresholds: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockAlertThresholds; }
      throw error;
    }
  },
  updateAlertThresholds: async (thresholds: Record<string, unknown>) => {
    try {
      const res = await api.put(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS, thresholds);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return { success: true, thresholds }; }
      throw error;
    }
  },
  getDataSources: async () => {
    try {
      const res = await api.get("/health");
      const h = res.data?.data || res.data;
      return [
        { name: "PostgreSQL", type: "Database", status: h?.database === "healthy" ? "Active" : "Error", last_sync: "Live", source_id: "postgres" },
        { name: "Redis Cache", type: "Cache", status: h?.redis === "healthy" ? "Active" : "Error", last_sync: "Live", source_id: "redis" },
        { name: "Neo4j", type: "Graph DB", status: h?.neo4j === "healthy" ? "Active" : "Error", last_sync: "Live", source_id: "neo4j" },
        { name: "Gemini AI", type: "AI Engine", status: "Active", last_sync: "On-demand", source_id: "gemini" },
      ];
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockDataSources; }
      throw error;
    }
  },
  syncDataSource: async (sourceId: string) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.DATASOURCE_SYNC(sourceId));
      return res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
        flagMockDataUsed();
        return { status: "success", message: `Synced ${sourceId}` };
      }
      throw error;
    }
  },
  getAuditLogs: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.AUDIT_LOGS);
      return res.data?.data || res.data || [];
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return []; }
      throw error;
    }
  },
};
