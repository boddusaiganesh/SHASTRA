import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';
import {
  mockMapCrimes,
  mockDashboardSummary,
  mockCrimeTrends,
  mockCrimeTypeBreakdown,
  mockDistrictCrimeCounts,
  mockRecentCrimes,
  mockRecentAlerts,
  mockHotspotClusters,
  mockTimePatternData,
  mockDayPatternData,
  mockMonthPatternData,
  mockDeploymentSuggestions,
} from "./mockData";

export const crimeService = {
  getDashboardSummary: async () => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.SUMMARY);
      return res.data.data || res.data;
    } catch (error) {
      return mockDashboardSummary;
    }
  },
  getRecentCrimes: async (limit = 10) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_CRIMES, { params: { limit } });
      return res.data.data || res.data;
    } catch {
      return mockRecentCrimes;
    }
  },
  getRecentAlerts: async (limit = 8) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_ALERTS, { params: { limit } });
      return res.data.data || res.data;
    } catch {
      return mockRecentAlerts;
    }
  },
  getCrimeTrends: async () => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.CRIME_TRENDS);
      return res.data.data || res.data;
    } catch (error) {
      return { trends: mockCrimeTrends, byType: mockCrimeTypeBreakdown, byDistrict: mockDistrictCrimeCounts };
    }
  },
  getMapData: async (filters?: Record<string, string>) => { 
    try {
      const response = await api.get(ENDPOINTS.CRIMES.MAP_DATA, { params: filters });
      return response.data.data || response.data;
    } catch (error) {
      return mockMapCrimes;
    }
  },
  getCrimeDetail: async (id: string) => {
    try {
      const response = await api.get(ENDPOINTS.CRIMES.DETAIL(id));
      return response.data.data || response.data;
    } catch (error) {
      return mockMapCrimes.find((c) => c.crime_id === id) || null;
    }
  },
  getHotspotClusters: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.CLUSTERS, { params: filters });
      return response.data.data || response.data;
    } catch {
      return mockHotspotClusters;
    }
  },
  getTimePatterns: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TIME_PATTERNS, { params: filters });
      return response.data.data || response.data;
    } catch {
      return { byHour: mockTimePatternData, byDay: mockDayPatternData, byMonth: mockMonthPatternData };
    }
  },
  getTopHotspots: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TOP_LIST, { params: filters });
      return response.data.data || response.data;
    } catch {
      return mockHotspotClusters;
    }
  },
  getDeploymentSuggestions: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.DEPLOYMENT_SUGGESTIONS, { params: filters });
      return response.data.data || response.data;
    } catch {
      return mockDeploymentSuggestions;
    }
  },
};
