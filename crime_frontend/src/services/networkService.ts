import api from "./api";

export const networkService = {
  getGraphData: async (searchQuery?: string, crimeType?: string, districtId?: string) => {
    try {
      const response = await api.get("/network/graph", {
        params: { search_query: searchQuery, crime_type: crimeType, district_id: districtId },
      });
      const data = response.data;
      if (!data || !data.nodes || data.nodes.length === 0) {
        return { status: "no_data" };
      }
      return {
        status: "ok",
        nodes: data.nodes,
        edges: data.edges || [],
        network_density: data.network_density || 0,
        key_players: data.key_players || []
      };
    } catch (error) {
      console.error("Error fetching network graph:", error);
      return { status: "offline", error: "Failed to connect to the backend API." };
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
