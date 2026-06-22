import { mockRecentAlerts, mockUsers, mockDataSources, mockAlertThresholds, mockSavedReports } from "./mockData";

const delay = (ms = 600) => new Promise((r) => setTimeout(r, ms));

export const alertService = {
  getAlerts: async () => { await delay(); return mockRecentAlerts; },
  markRead: async (id: string) => { await delay(); return { success: true, alert_id: id }; },
};

export const settingsService = {
  getUsers: async () => { await delay(); return mockUsers; },
  addUser: async (user: Record<string, string>) => { await delay(); return { success: true, user }; },
  getDistricts: async () => { await delay(); return []; },
  getAlertThresholds: async () => { await delay(); return mockAlertThresholds; },
  updateAlertThresholds: async (thresholds: Record<string, unknown>) => { await delay(); return { success: true, thresholds }; },
  getDataSources: async () => { await delay(); return mockDataSources; },
};

export const reportService = {
  generateReport: async (params: Record<string, string>) => { await delay(1500); return { report_id: "RPT_NEW", ...params }; },
  getSavedList: async () => { await delay(); return mockSavedReports; },
  download: async (id: string) => { await delay(); return { report_id: id, url: "#" }; },
};
