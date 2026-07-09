import { flagMockDataUsed } from '../utils/mockDataFlag';
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
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockCrimeForecast; }
      throw error;
    }
  },
  getAnomalies: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST, { params: filters });
      return res.data?.data || res.data || [];
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockAnomalies; }
      throw error;
    }
  },
  getRiskMap: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.RISK_MAP);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockDistrictRiskScores; }
      throw error;
    }
  },
  getHighRiskAreas: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.HIGH_RISK_AREAS);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockHighRiskPredictions; }
      throw error;
    }
  },
  getForecast: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.FORECAST);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockCrimeForecast; }
      throw error;
    }
  },
  getEmergingTypologies: async () => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.EMERGING_TYPOLOGIES);
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockEmergingTypologies; }
      throw error;
    }
  },
  getSocioeconomicData: async (filters?: any) => {
    try {
      const res = await api.get(ENDPOINTS.PREDICTIONS.SOCIOECONOMIC, { params: filters });
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockSocioeconomicData; }
      throw error;
    }
  },
};

export const anomalyService = {
  getList: async () => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.LIST);
      return res.data?.data || res.data || [];
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockAnomalies; }
      throw error;
    }
  },
  getDetail: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.ANOMALIES.DETAIL(id));
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockAnomalies.find((a) => a.anomaly_id === id) || null; }
      throw error;
    }
  },
  updateStatus: async (id: string, status: string) => {
    try {
      const res = await api.patch(ENDPOINTS.ANOMALIES.UPDATE_STATUS(id), { status });
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return { success: true, anomaly_id: id, status }; }
      throw error;
    }
  },
};
