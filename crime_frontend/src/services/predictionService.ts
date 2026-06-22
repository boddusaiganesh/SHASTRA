import axios from 'axios';
import {
  mockDistrictRiskScores,
  mockHighRiskPredictions,
  mockCrimeForecast,
  mockEmergingTypologies,
  mockSocioeconomicData,
  mockOffenders,
  mockAnomalies,
} from "./mockData";

const delay = (ms = 600) => new Promise((r) => setTimeout(r, ms));

export const predictionService = {
  getRiskMap: async () => { await delay(); return mockDistrictRiskScores; },
  getHighRiskAreas: async () => { await delay(); return mockHighRiskPredictions; },
  getForecast: async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/predictions/forecast');
      return res.data;
    } catch (e) {
      console.error("Error fetching forecast, falling back to mock:", e);
      return mockCrimeForecast;
    }
  },
  getEmergingTypologies: async () => { await delay(); return mockEmergingTypologies; },
  getSocioeconomicData: async () => { await delay(); return mockSocioeconomicData; },
};

export const offenderService = {
  searchOffenders: async (query?: string) => {
    await delay();
    if (!query) return mockOffenders;
    return mockOffenders.filter((o) =>
      o.offender_name.toLowerCase().includes(query.toLowerCase()) ||
      o.district.toLowerCase().includes(query.toLowerCase())
    );
  },
  getProfile: async (id: string) => { await delay(); return mockOffenders.find((o) => o.offender_id === id) || null; },
  getModusOperandi: async (id: string) => { await delay(); return mockOffenders.find((o) => o.offender_id === id)?.modus_operandi || null; },
};

export const anomalyService = {
  getList: async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/anomalies/');
      return res.data;
    } catch (e) {
      console.error("Error fetching anomalies, falling back to mock:", e);
      return mockAnomalies;
    }
  },
  getDetail: async (id: string) => { await delay(); return mockAnomalies.find((a) => a.anomaly_id === id) || null; },
  updateStatus: async (id: string, status: string) => {
    await delay();
    return { success: true, anomaly_id: id, status };
  },
};
