import axios from 'axios';
import { mockNetworkNodes, mockNetworkEdges, mockAiNetworkSummary } from "./mockData";

const delay = (ms = 600) => new Promise((r) => setTimeout(r, ms));

export const networkService = {
  getGraphData: async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/network/graph');
      return { nodes: res.data.nodes, edges: res.data.edges };
    } catch (e) {
      console.error("Error fetching network graph, falling back to mock", e);
      return { nodes: mockNetworkNodes, edges: mockNetworkEdges };
    }
  },
  getNodeDetail: async (id: string) => { await delay(); return mockNetworkNodes.find((n) => n.node_id === id) || null; },
  getAiSummary: async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/network/ai-summary');
      return res.data;
    } catch (e) {
      console.error("Error fetching AI summary, falling back to mock", e);
      return mockAiNetworkSummary;
    }
  },
};
