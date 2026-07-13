import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const alertService = {
  getAlerts: async (page: number = 1, pageSize: number = 20, severity?: string, type?: string) => {
    try {
      const params: any = { page, page_size: pageSize };
      if (severity && severity !== "All") params.severity = severity;
      if (type && type !== "All") params.alert_type = type;
      
      const res = await api.get(ENDPOINTS.ALERTS.LIST, { params });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  markRead: async (id: string) => {
    const res = await api.put(ENDPOINTS.ALERTS.MARK_READ(id));
    return res.data;
  },
  dismiss: async (id: string) => {
    const res = await api.delete(ENDPOINTS.ALERTS.DISMISS(id));
    return res.data;
  },
};
