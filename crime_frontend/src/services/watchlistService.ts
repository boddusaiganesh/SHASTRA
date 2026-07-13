import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const watchlistService = {
  add: async (entityId: string, entityType: string, entityLabel: string) => {
    const res = await api.post(ENDPOINTS.WATCHLIST.ADD, { entity_id: entityId, entity_type: entityType, entity_label: entityLabel });
    return res.data?.data;
  },
  remove: async (entityId: string) => api.delete(ENDPOINTS.WATCHLIST.REMOVE(entityId)),
  list: async () => {
    const res = await api.get(ENDPOINTS.WATCHLIST.LIST);
    return res.data?.data || [];
  },
  status: async (entityId: string) => {
    const res = await api.get(ENDPOINTS.WATCHLIST.STATUS(entityId));
    return !!res.data?.data?.is_watched;
  },
};
