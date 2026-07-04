export const API_BASE_URL = "http://localhost:8000/api";

export const ENDPOINTS = {
  // Authentication
  AUTH: {
    LOGIN: "/auth/login",
    LOGOUT: "/auth/logout",
    VERIFY_TOKEN: "/auth/verify-token",
  },
  // Dashboard
  DASHBOARD: {
    SUMMARY: "/dashboard/summary",
    RECENT_CRIMES: "/dashboard/recent-crimes",
    RECENT_ALERTS: "/dashboard/recent-alerts",
    CRIME_TRENDS: "/dashboard/crime-trends",
  },
  // Crime Map
  CRIMES: {
    MAP_DATA: "/crimes/map-data",
    DETAIL: (id: string) => `/crimes/detail/${id}`,
    FILTER: "/crimes/filter",
  },
  // Hotspots
  HOTSPOTS: {
    CLUSTERS: "/hotspots/clusters",
    TIME_PATTERNS: "/hotspots/time-patterns",
    TOP_LIST: "/hotspots/top-list",
    DEPLOYMENT_SUGGESTIONS: "/hotspots/deployment-suggestions",
  },
  // Network
  NETWORK: {
    GRAPH_DATA: "/network/graph-data",
    NODE_DETAIL: (id: string) => `/network/node-detail/${id}`,
    AI_SUMMARY: "/network/ai-summary",
  },
  // Offenders
  OFFENDERS: {
    SEARCH: "/offenders/search",
    PROFILE: (id: string) => `/offenders/${id}/profile`,
    MODUS_OPERANDI: (id: string) => `/offenders/${id}/modus-operandi`,
    NETWORK: (id: string) => `/offenders/${id}/network`,
    RISK: (id: string) => `/offenders/${id}/risk`,
  },
  // Predictions
  PREDICTIONS: {
    RISK_MAP: "/predictions/risk-map",
    HIGH_RISK_AREAS: "/predictions/high-risk-areas",
    FORECAST: "/predictions/forecast",
    EMERGING_TYPOLOGIES: "/predictions/emerging-typologies",
    SOCIOECONOMIC: "/predictions/socioeconomic-correlation",
  },
  // Anomalies
  ANOMALIES: {
    LIST: "/anomalies/list",
    DETAIL: (id: string) => `/anomalies/detail/${id}`,
    UPDATE_STATUS: (id: string) => `/anomalies/update-status/${id}`,
  },
  // Alerts
  // Alerts
  ALERTS: {
    LIST: "/alerts/active",
    MARK_READ: (id: string) => `/alerts/${id}/read`,
  },
  // Reports
  REPORTS: {
    GENERATE: "/reports/generate",
    SAVED_LIST: "/reports/history",
    DOWNLOAD: (id: string) => `/reports/${id}/download`,
  },
  // Settings
  SETTINGS: {
    USERS: "/settings/users",
    USERS_ADD: "/settings/users/add",
    DISTRICTS: "/settings/districts",
    ALERT_THRESHOLDS: "/settings/alert-thresholds",
    AUDIT_LOGS: "/settings/audit-logs",
  },
};
