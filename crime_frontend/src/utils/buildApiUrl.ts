import { API_BASE_URL } from "../constants/apiEndpoints";

export const buildApiUrl = (path: string, params?: Record<string, string>) => {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  return url.toString();
};

export const downloadAuthenticated = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });
  
  const disposition: string = response.headers["content-disposition"] || "";
  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : path.split("/").pop() || "download";

  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(blobUrl);
};

export const getAuthenticatedBlobUrl = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });
  
  const contentType = response.headers["content-type"] || "application/octet-stream";
  return window.URL.createObjectURL(new Blob([response.data], { type: contentType }));
};
