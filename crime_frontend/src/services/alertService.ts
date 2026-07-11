import api from "./api";

export const alertService = {
  getAlerts: async (page: number = 1, pageSize: number = 20, severity?: string, type?: string) => {
    try {
      const res = await api.get(ENDPOINTS.ALERTS.LIST, { params: { page, page_size: pageSize, severity, alert_type: type } });
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
