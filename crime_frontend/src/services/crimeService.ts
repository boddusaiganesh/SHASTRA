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

const normalizeHotspot = (h: any) => {
  if (!h) return null;
  const rawRisk = h.risk_level || "Medium";
  const risk_level = rawRisk.charAt(0).toUpperCase() + rawRisk.slice(1).toLowerCase();
  
  const rawTrend = h.trend || "Stable";
  const trend = rawTrend.charAt(0).toUpperCase() + rawTrend.slice(1).toLowerCase();

  return {
    ...h,
    hotspot_id: h.hotspot_id,
    location: h.hotspot_name || h.location || "Unknown Area",
    district: h.district || h.district_id || "Unknown District",
    crime_count: h.crime_count || 0,
    most_common_crime: h.dominant_crime_type || h.most_common_crime || "Unknown",
    risk_level: risk_level,
    trend: trend,
    intensity: Math.round(h.risk_score || h.intensity || 50),
  };
};

export const crimeService = {
  getDashboardSummary: async () => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.SUMMARY);
      return res.data;
    } catch (error) {
      return mockDashboardSummary;
    }
  },
  getRecentCrimes: async (limit = 10) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_CRIMES, { params: { limit } });
      return res.data;
    } catch {
      return mockRecentCrimes;
    }
  },
  getRecentAlerts: async (limit = 8) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_ALERTS, { params: { limit } });
      return res.data;
    } catch {
      return mockRecentAlerts;
    }
  },
  getCrimeTrends: async () => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.CRIME_TRENDS);
      return res.data;
    } catch (error) {
      return { trends: mockCrimeTrends, byType: mockCrimeTypeBreakdown, byDistrict: mockDistrictCrimeCounts };
    }
  },
  getMapData: async (filters?: Record<string, string>) => { 
    try {
      const response = await api.get(ENDPOINTS.CRIMES.MAP_DATA, { params: filters });
      return response.data;
    } catch (error) {
      return mockMapCrimes;
    }
  },
  getCrimeDetail: async (id: string) => {
    try {
      const response = await api.get(ENDPOINTS.CRIMES.DETAIL(id));
      return response.data;
    } catch (error) {
      return mockMapCrimes.find((c) => c.crime_id === id) || null;
    }
  },
  getHotspotClusters: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.CLUSTERS, { params: filters });
      const data = response.data;
      const list = data?.hotspots || (Array.isArray(data) ? data : []);
      return {
        ...data,
        hotspots: list.map(normalizeHotspot)
      };
    } catch {
      return {
        hotspots: mockHotspotClusters.map(normalizeHotspot)
      };
    }
  },
  getTimePatterns: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TIME_PATTERNS, { params: filters });
      return response.data;
    } catch {
      return { byHour: mockTimePatternData, byDay: mockDayPatternData, byMonth: mockMonthPatternData };
    }
  },
  getTopHotspots: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TOP_LIST, { params: filters });
      const data = response.data;
      const list = data?.hotspots || (Array.isArray(data) ? data : []);
      return list.map(normalizeHotspot);
    } catch {
      return mockHotspotClusters.map(normalizeHotspot);
    }
  },
  getDeploymentSuggestions: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.DEPLOYMENT_SUGGESTIONS, { params: filters });
      const data = response.data;
      
      const suggestions = (data?.suggestions || []).map((s: any) => {
        const rawPriority = s.priority_level || s.priority || "Medium";
        const priority = rawPriority.charAt(0).toUpperCase() + rawPriority.slice(1).toLowerCase();
        
        return {
          area: s.area_name || s.area || "Unknown Area",
          priority: priority,
          patrol_timing: Array.isArray(s.suggested_patrol_times) ? s.suggested_patrol_times[0] : (s.suggested_patrol_times || s.patrol_timing || "20:00 - 02:00"),
          officers_needed: s.recommended_officers || s.officers_needed || 2,
          reason: s.specific_instructions || s.reason || "Maintain visible patrol presence",
        };
      });
      
      return {
        ai_summary: data?.ai_overall_strategy || data?.ai_summary || "Maintain standard patrol schedules.",
        suggestions: suggestions,
      };
    } catch {
      return mockDeploymentSuggestions;
    }
  },
};
