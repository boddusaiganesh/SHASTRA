import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

export const victimService = {
  search: (q?: string, districtId?: string) =>
    api.get(ENDPOINTS.VICTIMS.SEARCH, { params: { q, district_id: districtId } }).then((r) => r.data),
  getProfile: (victimId: string) =>
    api.get(ENDPOINTS.VICTIMS.PROFILE(victimId)).then((r) => r.data),
  register: (payload: any) =>
    api.post(ENDPOINTS.VICTIMS.REGISTER, payload).then((r) => r.data),
};
