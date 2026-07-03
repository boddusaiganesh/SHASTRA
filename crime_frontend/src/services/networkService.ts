import api from './api';
import { mockNetworkNodes, mockNetworkEdges, mockAiNetworkSummary } from './mockData';

export const networkService = {
  getGraphData: async (filters?: Record<string, unknown>) => {
    try {
      const res = await api.get('/network/graph', { params: filters });
      const data = res.data;
      return {
        nodes: Array.isArray(data?.nodes) ? data.nodes : mockNetworkNodes,
        edges: Array.isArray(data?.edges) ? data.edges : mockNetworkEdges,
      };
    } catch (error) {
      console.warn("Using mock network data");
      return { nodes: mockNetworkNodes, edges: mockNetworkEdges };
    }
  },

  getAiSummary: async (networkId?: string) => {
    try {
      const res = await api.get('/network/ai-summary', { params: { id: networkId } });
      const data = res.data;
      if (data) {
        const summary = data.summary || data.summary_text || mockAiNetworkSummary.summary;
        
        const rawAssoc = data.suspicious_associations || data.suspicious_pairs || [];
        const suspicious_associations = (Array.isArray(rawAssoc) ? rawAssoc : []).map((s: any) => ({
          entities: Array.isArray(s.entities) ? s.entities : [s.offender_1 || "Node A", s.offender_2 || "Node B"],
          reason: s.reason || s.connection_type || "Identified co-conspirator link",
          severity: s.severity || (s.confidence === "SUSPECTED" ? "High" : "Medium"),
        }));

        const rawPriorities = data.investigation_priorities || data.recommended_actions || data.key_findings || [];
        const investigation_priorities = Array.isArray(rawPriorities) ? rawPriorities : [];

        return {
          summary,
          suspicious_associations: suspicious_associations.length > 0 ? suspicious_associations : mockAiNetworkSummary.suspicious_associations,
          investigation_priorities: investigation_priorities.length > 0 ? investigation_priorities : mockAiNetworkSummary.investigation_priorities,
        };
      }
      return mockAiNetworkSummary;
    } catch (error) {
      console.warn("Using mock AI network summary");
      return mockAiNetworkSummary;
    }
  },
};
