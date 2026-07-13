import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const investigationService = {
  save: async (payload: { title: string; notes?: string; filters: Record<string, any>; board_state: Record<string, any>; district_id?: string }) => {
    const res = await api.post(ENDPOINTS.INVESTIGATIONS.CREATE, payload);
    return res.data?.data;
  },
  list: async (page = 1, pageSize = 20) => {
    const res = await api.get(ENDPOINTS.INVESTIGATIONS.LIST, { params: { page, page_size: pageSize } });
    return res.data?.data;
  },
  get: async (id: string) => {
    const res = await api.get(ENDPOINTS.INVESTIGATIONS.DETAIL(id));
    return res.data?.data;
  },
  update: async (id: string, payload: Record<string, any>) => {
    const res = await api.put(ENDPOINTS.INVESTIGATIONS.UPDATE(id), payload);
    return res.data?.data;
  },
  remove: async (id: string) => {
    await api.delete(ENDPOINTS.INVESTIGATIONS.DELETE(id));
  },
};
