import api from './api';

export const predictionService = {
  getPredictions: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.FORECAST, { params: filters });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getAnomalies: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST, { params: filters });
      return res.data?.data || res.data || [];
    } catch (error) {
      throw error;
    }
  },
  getRiskMap: async (districtId?: string, dateFrom?: string, dateTo?: string) => {
    try {
      const params: any = {};
      if (districtId && districtId !== "All") params.district_id = districtId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get(ENDPOINTS.PREDICTIONS.RISK_MAP, { params });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getHighRiskAreas: async (districtId?: string, dateFrom?: string, dateTo?: string) => {
    try {
      const params: any = {};
      if (districtId && districtId !== "All") params.district_id = districtId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get(ENDPOINTS.PREDICTIONS.HIGH_RISK_AREAS, { params });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getForecast: async (districtId?: string, dateFrom?: string, dateTo?: string) => {
    try {
      const params: any = {};
      if (districtId && districtId !== "All") params.district_id = districtId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get(ENDPOINTS.PREDICTIONS.FORECAST, { params });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getEmergingTypologies: async (districtId?: string, dateFrom?: string, dateTo?: string) => {
    try {
      const params: any = {};
      if (districtId && districtId !== "All") params.district_id = districtId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get(ENDPOINTS.PREDICTIONS.EMERGING_TYPOLOGIES, { params });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getSocioeconomicData: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.SOCIOECONOMIC, { params: filters });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
};

export const anomalyService = {
  getList: async (page: number = 1, pageSize: number = 20, severity?: string, status?: string, districtId?: string) => {
    try {
      const params: any = { page, page_size: pageSize };
      if (severity && severity !== "All") params.severity = severity;
      if (status && status !== "All") params.status = status;
      if (districtId && districtId !== "All") params.district_id = districtId;
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST, { params });
      return res.data?.data || res.data || {};
    } catch (error) {
      throw error;
    }
  },
  getDetail: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.DETAIL(id));
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  updateStatus: async (id: string, status: string) => {
    try {
      const res = await api.patch(ENDPOINTS.ANOMALIES.UPDATE_STATUS(id), { status });
      return res.data?.data || res.data;
    } catch (error) {; }
      throw error;
    }
  },
};
