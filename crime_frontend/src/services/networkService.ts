import api from "./api";

export const networkService = {
  getNodeDetail: async (nodeId: string) => {
    try {
      const response = await api.get(`/network/node-detail/${nodeId}`);
      return response.data || null;
    } catch (error) {
      console.error("Error fetching node detail:", error);
      return null;
    }
  },

  getGraphData: async (searchQuery?: string, crimeType?: string, districtId?: string) => {
    try {
      const response = await api.get("/network/graph", {
        params: { search_query: searchQuery, crime_type: crimeType, district_id: districtId },
      });
      return response.data?.data || response.data || null;
    } catch (error: any) {
      console.error("Error fetching network graph:", error);
      return { status: "offline", error: error.response?.data?.detail || "Failed to connect to the backend API." };
    }
  },

  getShortestPath: async (nodeA: string, nodeB: string) => {
    try {
      const response = await api.get("/network/shortest-path", {
        params: { node_a: nodeA, node_b: nodeB },
      });
      return response.data?.data || null;
    } catch (error) {
      console.error("Error fetching shortest path:", error);
      return null;
    }
  },

  expandNode: async (nodeId: string) => {
    try {
      const response = await api.get(`/network/expand/${nodeId}`);
      return response.data?.data || null;
    } catch (error) {
      console.error("Error expanding node:", error);
      return null;
    }
  },

  getAiSummary: async () => {
    try {
      const response = await api.get("/network/ai-summary");
      return response.data || null;
    } catch (error) {
      console.error("Error fetching AI summary:", error);
      return null;
    }
  },
};
