import api from "./api";

export const victimService = {
  search: (q?: string, districtId?: string) =>
    api.get("/victims/search", { params: { q, district_id: districtId } }).then((r) => r.data.data),
  getProfile: (victimId: string) =>
    api.get(`/victims/${victimId}/profile`).then((r) => r.data.data),
  register: (payload: any) =>
    api.post("/victims", payload).then((r) => r.data.data),
};
