import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const networkService = {
  getNodeDetail: async (nodeId: string) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.NODE_DETAIL(nodeId));
      return response.data?.data || null;
    } catch (error) {
      console.error("Error fetching node detail:", error);
      return null;
    }
  },

  getGraphData: async (
    searchQuery?: string, 
    crimeType?: string, 
    districtId?: string, 
    nodeType?: string,
    opts?: { signal?: AbortSignal }
  ) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.GRAPH_DATA, {
        params: { search_query: searchQuery, crime_type: crimeType, district_id: districtId, node_type: nodeType },
        signal: opts?.signal,
      });
      return response.data?.data || null;
    } catch (error: any) {
      if (error.name === "CanceledError") throw error;
      console.error("Error fetching network graph:", error);
      return { status: "offline", error: error.response?.data?.detail || "Failed to connect to the backend API." };
    }
  },

  getShortestPath: async (nodeA: string, nodeB: string) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.SHORTEST_PATH, {
        params: { node_a: nodeA, node_b: nodeB },
      });
      return response.data?.data || null;
    } catch (error) {
      console.error("Error fetching shortest path:", error);
      return null;
    }
  },

  expandNode: async (nodeId: string, nodeType?: string) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.EXPAND(nodeId), { params: { node_type: nodeType } });
      return response.data?.data || response.data || null;
    } catch (error: any) {
      console.error("Error expanding node:", error);
      throw error;
    }
  },

  getAiSummary: async (
    districtId?: string, 
    crimeType?: string, 
    searchQuery?: string, 
    nodeType?: string,
    opts?: { signal?: AbortSignal }
  ) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.AI_SUMMARY, { 
        params: { district_id: districtId, crime_type: crimeType, search_query: searchQuery, node_type: nodeType },
        signal: opts?.signal
      });
      return response.data?.data || null;
    } catch (error: any) {
      if (error.name === "CanceledError") throw error;
      console.error("Error fetching AI summary:", error);
      throw error;
    }
  },

  getEdgeInsight: async (nodeA: any, nodeB: any, edge: any) => {
    try {
      const response = await api.post(ENDPOINTS.NETWORK.EDGE_INSIGHT, { node_a: nodeA, node_b: nodeB, edge });
      return response.data?.data?.insight ?? null;
    } catch (error) {
      console.error("Error fetching edge insight:", error);
      return null;
    }
  },

  getNodeAiAnalysis: async (nodeId: string) => {
    try {
      const response = await api.get(ENDPOINTS.NETWORK.NODE_AI_ANALYSIS(nodeId));
      return response.data?.data?.ai_analysis || null;
    } catch (error) {
      console.error("Error fetching node AI analysis:", error);
      return null;
    }
  },
};
