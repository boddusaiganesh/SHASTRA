import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface AlertsState {
  alerts: unknown[];
  unreadCount: number;
  totalCount: number;
  loading: boolean;
}

const initialState: AlertsState = {
  alerts: [],
  unreadCount: 0,
  totalCount: 0,
  loading: false,
};

const alertsSlice = createSlice({
  name: "alerts",
  initialState,
  reducers: {
    setAlerts: (state, action: PayloadAction<any>) => {
      const payload = action.payload;
      if (payload && payload.alerts) {
        state.alerts = payload.alerts;
        state.unreadCount = payload.unread_count !== undefined ? payload.unread_count : state.unreadCount;
        state.totalCount = payload.total_count !== undefined ? payload.total_count : state.totalCount;
      } else {
        const list = Array.isArray(payload) ? payload : [];
        state.alerts = list;
        state.unreadCount = list.filter((a: any) => !a?.is_read).length;
        state.totalCount = list.length;
      }
    },
    addAlert: (state, action: PayloadAction<any>) => {
      state.alerts = [action.payload, ...state.alerts];
      state.unreadCount += 1;
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

export const { setAlerts, addAlert, markAlertRead, clearUnreadCount, setLoading } = alertsSlice.actions;
export default alertsSlice.reducer;
