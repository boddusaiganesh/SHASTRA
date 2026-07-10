import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface AuthState {
  isAuthenticated: boolean;
  auth_token: string | null;
  user_role: string;
  user_name: string;
  user_district: string;
  permissions_list: string[];
  isLoading: boolean;
  error: string | null;
}

const stored = localStorage.getItem("user_data");
let parsedUser = null;
try {
  parsedUser = stored ? JSON.parse(stored) : null;
} catch (e) {
  localStorage.removeItem("user_data");
}

const initialState: AuthState = {
  isAuthenticated: !!localStorage.getItem("is_logged_in"),
  auth_token: null, // No longer stored client-side
  user_role: parsedUser?.user_role || "",
  user_name: parsedUser?.user_name || "",
  user_district: parsedUser?.user_district || "",
  permissions_list: parsedUser?.permissions_list || [],
  isLoading: false,
  error: null,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    loginStart: (state) => {
      state.isLoading = true;
      state.error = null;
    },
    loginSuccess: (state, action: PayloadAction<AuthState>) => {
      state.isAuthenticated = true;
      state.auth_token = null; // No longer needed in state, handled by cookie
      state.user_role = action.payload.user_role;
      state.user_name = action.payload.user_name;
      state.user_district = action.payload.user_district;
      state.permissions_list = action.payload.permissions_list;
      state.isLoading = false;
      state.error = null;
      localStorage.setItem("is_logged_in", "true");
      localStorage.setItem("user_data", JSON.stringify(action.payload));
    },
    loginFailure: (state, action: PayloadAction<string>) => {
      state.isLoading = false;
      state.error = action.payload;
    },
    logout: (state) => {
      state.isAuthenticated = false;
      state.auth_token = null;
      state.user_role = "";
      state.user_name = "";
      state.user_district = "";
      state.permissions_list = [];
      state.isLoading = false;
      state.error = null;
      localStorage.removeItem("is_logged_in");
      localStorage.removeItem("user_data");
    },
  },
});

export const { loginStart, loginSuccess, loginFailure, logout } = authSlice.actions;
export default authSlice.reducer;
