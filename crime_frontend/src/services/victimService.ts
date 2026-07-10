import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const victimService = {
  search: (q?: string, districtId?: string, page: number = 1, page_size: number = 20) =>
    api.get(ENDPOINTS.VICTIMS.SEARCH, { params: { q, district_id: districtId, page, page_size } }).then((r) => r.data?.data || {}),
  getProfile: (victimId: string) =>
    api.get(ENDPOINTS.VICTIMS.PROFILE(victimId)).then((r) => r.data?.data || null),
  register: (payload: any) =>
    api.post(ENDPOINTS.VICTIMS.REGISTER, payload).then((r) => r.data?.data || r.data),
};
