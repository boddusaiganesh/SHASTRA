import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockOffenders } from "./mockData";

export const offenderService = {
  searchOffenders: async (query: string = "") => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.SEARCH, { params: { query } });
      return res.data.data;
    } catch {
      return mockOffenders.filter((o: any) => 
        !query || o.offender_name?.toLowerCase().includes(query.toLowerCase())
      );
    }
  },
  getProfile: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.PROFILE(id));
      return res.data.data;
    } catch {
      return mockOffenders.find((o: any) => o.id === id);
    }
  },
  getModusOperandi: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.MODUS_OPERANDI(id));
      return res.data.data;
    } catch {
      return null;
    }
  },
};
