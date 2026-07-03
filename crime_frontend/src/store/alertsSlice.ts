import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface AlertsState {
  alerts: unknown[];
  unreadCount: number;
  loading: boolean;
}

const initialState: AlertsState = {
  alerts: [],
  unreadCount: 0,
  loading: false,
};

const alertsSlice = createSlice({
  name: "alerts",
  initialState,
  reducers: {
    setAlerts: (state, action: PayloadAction<unknown[]>) => {
      const list = Array.isArray(action.payload) ? action.payload : ((action.payload as any)?.alerts || []);
      state.alerts = list;
      state.unreadCount = (list as { is_read: boolean }[]).filter((a) => !a?.is_read).length;
    },
    markAlertRead: (state, action: PayloadAction<string>) => {
      state.alerts = (state.alerts as { alert_id: string; is_read: boolean }[]).map((a) =>
        a.alert_id === action.payload ? { ...a, is_read: true } : a
      );
      state.unreadCount = Math.max(0, state.unreadCount - 1);
    },
    clearUnreadCount: (state) => {
      state.unreadCount = 0;
    },
    setLoading: (state, action: PayloadAction<boolean>) => { state.loading = action.payload; },
  },
});

export const { setAlerts, markAlertRead, clearUnreadCount, setLoading } = alertsSlice.actions;
export default alertsSlice.reducer;
