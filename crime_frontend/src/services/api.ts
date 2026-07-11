import axios from "axios";
import { API_BASE_URL } from "../constants/apiEndpoints";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const isLoginRequest = error.config?.url?.includes("/auth/login");
    if (error.response?.status === 401 && !isLoginRequest) {
      localStorage.removeItem("user_data");
      localStorage.removeItem("is_logged_in");
      window.location.href = "/login";
    }
    // No mock-data fallback. Let the caller show a real error/toast.
    return Promise.reject(error);
  }
);

export default api;
