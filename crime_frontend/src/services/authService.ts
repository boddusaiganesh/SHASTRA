import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";

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
    // Let errors propagate — the Login page should show a real error message.
    const res = await api.post(ENDPOINTS.AUTH.LOGIN, credentials);
    return res.data;
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
