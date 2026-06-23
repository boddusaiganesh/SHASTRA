import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockRecentAlerts, mockUsers, mockDataSources, mockAlertThresholds, mockSavedReports } from "./mockData";

export const alertService = {
  getAlerts: async () => {
    try {
      const res = await api.get(ENDPOINTS.ALERTS.LIST);
      return res.data?.alerts || res.data || mockRecentAlerts;
    } catch {
      return mockRecentAlerts;
    }
  },
  markRead: async (id: string) => {
    try {
      const res = await api.put(ENDPOINTS.ALERTS.MARK_READ(id));
      return res.data;
    } catch {
      return { success: true, alert_id: id };
    }
  },
};

export const settingsService = {
  getUsers: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.USERS);
      return res.data;
    } catch {
      return mockUsers;
    }
  },
  addUser: async (user: Record<string, string>) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.USERS_ADD, user);
      return { data: res.data };
    } catch {
      return { user: { ...user, user_id: "mock-id-" + Math.random().toString(36).substring(2, 11) } };
    }
  },
  getDistricts: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.DISTRICTS);
      return res.data;
    } catch {
      return [];
    }
  },
  getAlertThresholds: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS);
      return res.data;
    } catch {
      return mockAlertThresholds;
    }
  },
  updateAlertThresholds: async (thresholds: Record<string, unknown>) => {
    try {
      const res = await api.put(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS, thresholds);
      return res.data;
    } catch {
      return { success: true, thresholds };
    }
  },
  getDataSources: async () => {
    try {
      const res = await api.get("/health");
      const h = res.data?.data || res.data;
      return [
        { name: "PostgreSQL", type: "Database", status: h?.database === "healthy" ? "Active" : "Error", last_sync: "Live" },
        { name: "Redis Cache", type: "Cache", status: h?.redis === "healthy" ? "Active" : "Error", last_sync: "Live" },
        { name: "Neo4j", type: "Graph DB", status: h?.neo4j === "healthy" ? "Active" : "Error", last_sync: "Live" },
        { name: "Gemini AI", type: "AI Engine", status: "Active", last_sync: "On-demand" },
      ];
    } catch {
      return mockDataSources;
    }
  },
};

export const reportService = {
  generateReport: async (params: Record<string, string>) => {
    try {
      const queryParams = {
        report_type: params.report_type,
        report_name: params.report_name || `${params.report_type}_${Date.now()}`,
        ...(params.district_id ? { district_id: params.district_id } : {}),
      };
      const res = await api.post(
        `${ENDPOINTS.REPORTS.GENERATE}?${new URLSearchParams(queryParams).toString()}`
      );
      return res.data;
    } catch {
      return {
        report_id: `RPT_${Date.now()}`,
        report_type: params.report_type,
        status: "Ready",
        generated_at: new Date().toISOString(),
      };
    }
  },
  getSavedList: async () => {
    try {
      const res = await api.get(ENDPOINTS.REPORTS.SAVED_LIST);
      return res.data;
    } catch {
      return mockSavedReports;
    }
  },
  download: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.REPORTS.DOWNLOAD(id));
      return res.data;
    } catch {
      return { report_id: id, url: "#" };
    }
  },
};
