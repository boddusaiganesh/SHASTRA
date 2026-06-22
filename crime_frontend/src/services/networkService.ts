import api from './api';
import { mockNetworkData } from './mockData';

export const networkService = {
  getNetworkData: async (filters?: any) => {
    try {
      const res = await api.get('/network/graph', { params: filters });
      return res.data;
    } catch (error) {
      console.warn("Using mock network data");
      return mockNetworkData;
    }
  },

  getAiSummary: async (networkId?: string) => {
    try {
      const res = await api.get('/network/ai-summary', { params: { id: networkId } });
      return res.data;
    } catch (error) {
      console.warn("Using mock AI network summary");
      return {
        summary: "Gemini Analysis: The network shows a highly centralized structure built around two primary actors (ON-001 and ON-002). The Modus Operandi suggests coordinated vehicle theft followed by interstate trafficking. 40% of the nodes represent repeat offenders.",
        key_actors: ["ON-001", "ON-002"],
        recommended_actions: ["Target the bridge node ON-003 to disrupt communication.", "Increase surveillance at locations L-01 and L-04."]
      };
    }
  }
};
