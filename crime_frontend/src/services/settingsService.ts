import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const settingsService = {
  getUsers: async (page: number = 1, pageSize: number = 20) => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.USERS, { params: { page, page_size: pageSize } });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  addUser: async (user: Record<string, string>) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.USERS_ADD, user);
      return res.data;
    } catch (error) {
      throw error;
    }
  },
  getDistricts: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.DISTRICTS);
      return res.data?.data || res.data || [];
    } catch (error) {
      throw error;
    }
  },
  getAlertThresholds: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS);
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  updateAlertThresholds: async (thresholds: Record<string, unknown>) => {
    try {
      const res = await api.put(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS, thresholds);
      return res.data?.data || res.data;
    } catch (error) {
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
      throw error;
    }
  },
  syncDataSource: async (sourceId: string) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.DATASOURCE_SYNC(sourceId));
      return res.data;
    } catch (error) {
      throw error;
    }
  },
  getAuditLogs: async (page: number = 1, pageSize: number = 20) => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.AUDIT_LOGS, { params: { page, page_size: pageSize } });
      return res.data?.data || res.data || [];
    } catch (error) {
      throw error;
    }
  },
};
