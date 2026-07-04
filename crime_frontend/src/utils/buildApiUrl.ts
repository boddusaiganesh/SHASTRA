import { API_BASE_URL } from "../constants/apiEndpoints";

export const buildApiUrl = (path: string, params?: Record<string, string>) => {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  return url.toString();
};

export const downloadAuthenticated = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = "";
  a.click();
  window.URL.revokeObjectURL(blobUrl);
};
