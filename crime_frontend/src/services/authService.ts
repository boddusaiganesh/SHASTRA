import api from "./api";

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
    const res = await api.post("/auth/login", credentials);
    return res.data;
  },

  logout: async (): Promise<void> => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      // Token already expired or backend down — clear locally anyway
    }
  },

  verifyToken: async (): Promise<boolean> => {
    try {
      await api.get("/auth/verify-token");
      return true;
    } catch {
      return false;
    }
  },

  isAuthenticated: (): boolean => {
    return !!localStorage.getItem("auth_token");
  },
};
