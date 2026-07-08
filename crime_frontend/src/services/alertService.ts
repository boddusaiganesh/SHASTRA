import { flagMockDataUsed } from '../utils/mockDataFlag';
import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockRecentAlerts } from "./mockData";

export const alertService = {
  getAlerts: async () => {
    try {
      const res = await api.get(ENDPOINTS.ALERTS.LIST);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockRecentAlerts; }
      throw error;
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
  dismiss: async (id: string) => {
    try {
      const res = await api.delete(ENDPOINTS.ALERTS.DISMISS(id));
      return res.data;
    } catch {
      return { success: true, alert_id: id };
    }
  },
};
