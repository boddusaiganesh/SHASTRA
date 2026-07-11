import api from "./api";

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
      return res.data?.data || res.data;
    } catch (error) {`,
          report_type: params.report_type,
          status: "Ready",
          generated_at: new Date().toISOString(),
        };
      }
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
