import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockAuthResponse } from "./mockData";

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  auth_token: string;
  user_role: string;
  user_name: string;
  user_district: string;
  permissions_list: string[];
}

export const authService = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    try {
      const res = await api.post(ENDPOINTS.AUTH.LOGIN, credentials);
      return res.data;
    } catch (error) {
      console.warn("Backend DB offline, falling back to mock authentication.");
      return {
        ...mockAuthResponse,
        user_name: credentials.username === "admin" ? "System Administrator" : credentials.username || mockAuthResponse.user_name,
      };
    }
  },

  logout: async (): Promise<void> => {
    try {
      await api.post(ENDPOINTS.AUTH.LOGOUT);
    } catch (e) {
      // Token already expired or backend down — clear locally anyway
    }
  },

  verifyToken: async (): Promise<boolean> => {
    try {
      await api.get(ENDPOINTS.AUTH.VERIFY_TOKEN);
      return true;
    } catch {
      return false;
    }
  },

  isAuthenticated: (): boolean => {
    return !!localStorage.getItem("auth_token");
  },
};
