import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockRecentAlerts, mockUsers, mockDataSources, mockAlertThresholds, mockSavedReports } from "./mockData";

export const alertService = {
  getAlerts: async () => {
    try {
      const res = await api.get(ENDPOINTS.ALERTS.LIST);
      return res.data.data;
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
      return res.data.data;
    } catch {
      return mockUsers;
    }
  },
  addUser: async (user: Record<string, string>) => {
    try {
      const res = await api.post(ENDPOINTS.SETTINGS.USERS_ADD, user);
      return res.data;
    } catch {
      return { success: true, user };
    }
  },
  getDistricts: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.DISTRICTS);
      return res.data.data;
    } catch {
      return [];
    }
  },
  getAlertThresholds: async () => {
    try {
      const res = await api.get(ENDPOINTS.SETTINGS.ALERT_THRESHOLDS);
      return res.data.data;
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
  getDataSources: async () => mockDataSources,
};

export const reportService = {
  generateReport: async (params: Record<string, string>) => {
    try {
      const res = await api.post(ENDPOINTS.REPORTS.GENERATE, params);
      return res.data;
    } catch {
      return { report_id: "RPT_NEW", ...params };
    }
  },
  getSavedList: async () => {
    try {
      const res = await api.get(ENDPOINTS.REPORTS.SAVED_LIST);
      return res.data.data;
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
