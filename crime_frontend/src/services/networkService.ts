import api from './api';
import { mockNetworkNodes, mockNetworkEdges, mockAiNetworkSummary } from './mockData';

export const networkService = {
  getGraphData: async (filters?: Record<string, unknown>) => {
    try {
      const res = await api.get('/network/graph', { params: filters });
      return res.data;
    } catch (error) {
      console.warn("Using mock network data");
      return { nodes: mockNetworkNodes, edges: mockNetworkEdges };
    }
  },

  getAiSummary: async (networkId?: string) => {
    try {
      const res = await api.get('/network/ai-summary', { params: { id: networkId } });
      return res.data;
    } catch (error) {
      console.warn("Using mock AI network summary");
      return mockAiNetworkSummary;
    }
  },
};
