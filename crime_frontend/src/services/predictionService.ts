import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';
import {
  mockDistrictRiskScores,
  mockHighRiskPredictions,
  mockCrimeForecast,
  mockEmergingTypologies,
  mockSocioeconomicData,
  mockAnomalies,
} from "./mockData";

export const predictionService = {
  getPredictions: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.FORECAST, { params: filters });
      return res.data.data || res.data;
    } catch (error) {
      return mockCrimeForecast;
    }
  },
  getAnomalies: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST, { params: filters });
      return res.data.data || res.data;
    } catch (error) {
      return mockAnomalies;
    }
  },
  getRiskMap: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.RISK_MAP);
      return res.data.data || res.data;
    } catch {
      return mockDistrictRiskScores;
    }
  },
  getHighRiskAreas: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.HIGH_RISK_AREAS);
      return res.data.data || res.data;
    } catch {
      return mockHighRiskPredictions;
    }
  },
  getForecast: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.FORECAST);
      return res.data.data || res.data;
    } catch {
      return mockCrimeForecast;
    }
  },
  getEmergingTypologies: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.EMERGING_TYPOLOGIES);
      return res.data.data || res.data;
    } catch {
      return mockEmergingTypologies;
    }
  },
  getSocioeconomicData: async () => {
    try {
      // Missing route in backend currently, fallback to mock
      return mockSocioeconomicData;
    } catch {
      return mockSocioeconomicData;
    }
  },
};

export const anomalyService = {
  getList: async () => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST);
      return res.data.data || res.data;
    } catch (e) {
      return mockAnomalies;
    }
  },
  getDetail: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.DETAIL(id));
      return res.data.data || res.data;
    } catch {
      return mockAnomalies.find((a) => a.anomaly_id === id) || null;
    }
  },
  updateStatus: async (id: string, status: string) => {
    try {
      const res = await api.patch(ENDPOINTS.ANOMALIES.UPDATE_STATUS(id), { status });
      return res.data.data || res.data;
    } catch {
      return { success: true, anomaly_id: id, status };
    }
  },
};
