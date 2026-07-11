import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const reportService = {
  generateReport: async (params: Record<string, string>) => {
    try {
      const queryParams: Record<string, string> = {
        report_type: params.report_type,
        report_name: params.report_name || `${params.report_type}_${Date.now()}`,
      };
      if (params.district_id) queryParams.district_id = params.district_id;
      if (params.date_from) queryParams.date_from = params.date_from;
      if (params.date_to) queryParams.date_to = params.date_to;

      const res = await api.post(
        `${ENDPOINTS.REPORTS.GENERATE}?${new URLSearchParams(queryParams).toString()}`
      );
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getSavedList: async (page = 1, pageSize = 20) => {
    try {
      const res = await api.get(ENDPOINTS.REPORTS.SAVED_LIST, { params: { page, limit: pageSize } });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  download: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.REPORTS.DOWNLOAD(id), { responseType: 'blob' });
      return res.data;
    } catch {
      return null;
    }
  },
};
