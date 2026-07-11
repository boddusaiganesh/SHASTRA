import api from './api';

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
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getRecentCrimes: async (limit = 10) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_CRIMES, { params: { limit } });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getRecentAlerts: async (limit = 8) => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_ALERTS, { params: { limit } });
      return res.data?.data || res.data;
    } catch (error) {
      throw error;
    }
  },
  getCrimeTrends: async () => {
    try {
      const res = await api.get(ENDPOINTS.DASHBOARD.CRIME_TRENDS);
      return res.data?.data || res.data;
    } catch (error) {; }
      throw error;
    }
  },
  getMapData: async (
    filters?: { crime_type?: string; district_id?: string; date_from?: string; date_to?: string },
    opts?: { signal?: AbortSignal }
  ) => { 
    try {
      const response = await api.get(ENDPOINTS.CRIMES.MAP_DATA, { params: filters, signal: opts?.signal });
      const data = response.data;
      return Array.isArray(data) ? data : (data?.crimes || data?.data);
    } catch (error: any) {
      if (error.name === "CanceledError") throw error;
      throw error;
    }
  },
  getCrimeDetail: async (id: string) => {
    try {
      const response = await api.get(ENDPOINTS.CRIMES.DETAIL(id));
      return response.data?.data || response.data;
    } catch (error) {
      throw error;
    }
  },
  update: async (id: string, payload: any) => {
    const response = await api.put(ENDPOINTS.CRIMES.UPDATE(id), payload);
    return response.data;
  },
  updateStatus: async (id: string, status: string) => {
    const response = await api.patch(ENDPOINTS.CRIMES.UPDATE_STATUS(id), { status });
    return response.data;
  },
  remove: async (id: string) => {
    const response = await api.delete(ENDPOINTS.CRIMES.DELETE(id));
    return response.data;
  },
  getEvidence: evidenceService.getEvidenceList,
  uploadEvidence: evidenceService.uploadEvidence,
  getHotspotClusters: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.CLUSTERS, { params: filters });
      const data = response.data?.data || response.data;
      const list = data?.hotspots || (Array.isArray(data) ? data : []);
      return {
        ...data,
        hotspots: list.map(normalizeHotspot)
      };
    } catch (error) {; }
      throw error;
    }
  },
  getTimePatterns: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TIME_PATTERNS, { params: filters });
      const data = response.data?.data || response.data;
      if (data) {
        const rawHour = data.hourly_pattern || data.byHour || [];
        const byHour = (Array.isArray(rawHour) ? rawHour : []).map((h: any) => ({
          label: h.label || (h.hour !== undefined ? `${String(h.hour).padStart(2, "0")}:00` : "00:00"),
          crimes: h.crimes ?? h.crime_count ?? 0,
        }));
        const rawDay = data.daily_pattern || data.byDay || [];
        const byDay = (Array.isArray(rawDay) ? rawDay : []).map((d: any) => ({
          day: d.day ? (d.day.length > 3 ? d.day.slice(0, 3) : d.day) : "Mon",
          crimes: d.crimes ?? d.crime_count ?? 0,
        }));
        const rawMonth = data.monthly_pattern || data.byMonth || [];
        const byMonth = (Array.isArray(rawMonth) ? rawMonth : []).map((m: any) => ({
          month: m.month || "Jan",
          crimes: m.crimes ?? m.crime_count ?? 0,
        }));
        return { byHour, byDay, byMonth };
      }
      return { byHour: mockTimePatternData, byDay: mockDayPatternData, byMonth: mockMonthPatternData };
    } catch (error) {; }
      throw error;
    }
  },
  getTopHotspots: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.TOP_LIST, { params: filters });
      const data = response.data?.data || response.data;
      const list = data?.hotspots || (Array.isArray(data) ? data : []);
      return list.map(normalizeHotspot);
    } catch (error) {
      throw error;
    }
  },
  getDeploymentSuggestions: async (filters?: any) => {
    try {
      const response = await api.get(ENDPOINTS.HOTSPOTS.DEPLOYMENT_SUGGESTIONS, { params: filters });
      const data = response.data?.data || response.data;
      
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
    } catch (error) {
      throw error;
    }
  },
  filterCrimes: async (params: { q?: string, district_id?: string, crime_type?: string, status?: string, page?: number, page_size?: number }) => {
    try {
      const res = await api.get(ENDPOINTS.CRIMES.FILTER, { params });
      return res.data;
    } catch (error) {; }
      throw error;
    }
  },
};
