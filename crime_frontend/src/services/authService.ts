import { mockAuthResponse } from "./mockData";

export const authService = {
  login: async (credentials: { username: string; password: string; role: string }) => {
    // Simulate API call
    await new Promise((r) => setTimeout(r, 1000));
    if (credentials.username && credentials.password) {
      return { ...mockAuthResponse, user_role: credentials.role };
    }
    throw new Error("Invalid credentials");
  },
  logout: async () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_data");
  },
  verifyToken: async () => {
    const token = localStorage.getItem("auth_token");
    return !!token;
  },
};
