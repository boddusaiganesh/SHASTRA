import api from './api';
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

const delay = (ms = 600) => new Promise((r) => setTimeout(r, ms));

export const crimeService = {
  getDashboardSummary: async () => {
    try {
      const res = await api.get('/dashboard/summary');
      return res.data;
    } catch (error) {
      console.warn("Using mock dashboard summary");
      return mockDashboardSummary;
    }
  },
  getRecentCrimes: async (limit = 10) => {
    try {
      const res = await api.get('/dashboard/recent-crimes', { params: { limit } });
      return res.data;
    } catch {
      console.warn("Using mock recent crimes");
      return mockRecentCrimes;
    }
  },
  getRecentAlerts: async (limit = 8) => {
    try {
      const res = await api.get('/dashboard/recent-alerts', { params: { limit } });
      return res.data;
    } catch {
      console.warn("Using mock recent alerts");
      return mockRecentAlerts;
    }
  },
  getCrimeTrends: async () => {
    try {
      const res = await api.get('/dashboard/crime-trends');
      return res.data;
    } catch (error) {
      console.warn("Using mock crime trends");
      return { trends: mockCrimeTrends, byType: mockCrimeTypeBreakdown, byDistrict: mockDistrictCrimeCounts };
    }
  },
  getMapData: async (filters?: Record<string, string>) => { 
    try {
      const response = await api.get('/crimes/map-data', { params: filters });
      return response.data;
    } catch (error) {
      console.error('Error fetching map data from backend, falling back to mock data:', error);
      return mockMapCrimes;
    }
  },
  getCrimeDetail: async (id: string) => { await delay(); return mockMapCrimes.find((c) => c.crime_id === id) || null; },
  getHotspotClusters: async (_filters?: any) => { await delay(); return mockHotspotClusters; },
  getTimePatterns: async (_filters?: any) => { await delay(); return { byHour: mockTimePatternData, byDay: mockDayPatternData, byMonth: mockMonthPatternData }; },
  getTopHotspots: async (_filters?: any) => { await delay(); return mockHotspotClusters; },
  getDeploymentSuggestions: async (_filters?: any) => { await delay(); return mockDeploymentSuggestions; },
};
