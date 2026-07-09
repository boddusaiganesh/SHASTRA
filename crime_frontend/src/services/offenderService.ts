import { flagMockDataUsed } from '../utils/mockDataFlag';
import api from "./api";
import { ENDPOINTS } from "../constants/apiEndpoints";
import { mockOffenders } from "./mockData";

const normalizeOffender = (o: any) => {
  if (!o) return null;
  return {
    ...o,
    offender_id: o.offender_id,
    offender_name: o.offender_name || o.full_name || `${o.first_name || ""} ${o.last_name || ""}`.trim(),
    offender_age: o.offender_age || o.age,
    age: o.offender_age || o.age,
    offender_status: o.offender_status || o.status || "Active",
    status: o.offender_status || o.status || "Active",
    district: o.district || o.district_id || "Unknown",
    crime_count: o.crime_count || o.total_crimes || (o.crime_history ? o.crime_history.length : 0),
    primary_crime_type: o.primary_crime_type || o.preferred_crime_types?.[0] || "Unknown",
    risk_score: o.risk_score || 0,
    risk_level: o.risk_level || "MEDIUM",
    modus_operandi: o.modus_operandi || o.modus_operandi_summary || o.ai_mo_summary || "N/A"
  };
};

export const offenderService = {
  searchOffenders: async (
    query: string = "", 
    filters?: { 
      crime_type?: string, 
      district_id?: string, 
      risk_level?: string, 
      status?: string, 
      page?: number, 
      page_size?: number 
    }
  ) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.SEARCH, { 
        params: { query, ...filters } 
      });
      const list = res.data?.data || res.data || [];
      return (Array.isArray(list) ? list : []).map(normalizeOffender).filter(Boolean);
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
        flagMockDataUsed();
        return mockOffenders.filter((o: any) => 
          (!query || o.offender_name?.toLowerCase().includes(query.toLowerCase())) &&
          (!filters?.district_id || o.district === filters.district_id) &&
          (!filters?.crime_type || o.primary_crime_type === filters.crime_type)
        ).map(normalizeOffender).filter(Boolean);
      }
      throw error;
    }
  },
  getProfile: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.PROFILE(id));
      return normalizeOffender(res.data?.data || res.data);
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
      flagMockDataUsed();
        return normalizeOffender(mockOffenders.find((o: any) => o.offender_id === id));
      }
      throw error;
    }
  },
  getModusOperandi: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.MODUS_OPERANDI(id));
      const mo = res.data?.data || res.data;
      if (mo) {
        return {
          ai_mo_summary: mo.ai_mo_summary || "N/A",
          preferred_crime_types: Array.isArray(mo.preferred_crime_types)
            ? mo.preferred_crime_types.map((ct: any) => typeof ct === 'object' ? `${ct.crime_type} (${ct.frequency} times)` : ct)
            : [],
          preferred_locations: mo.preferred_locations || [],
          preferred_time: mo.preferred_time || "Unknown",
          preferred_days: Array.isArray(mo.preferred_days)
            ? mo.preferred_days.map((d: any) => typeof d === 'object' ? `${d.day} (${d.count} times)` : d)
            : [],
          typical_targets: mo.typical_targets || mo.typical_target || "Unknown",
          weapons_pattern: mo.weapons_pattern || mo.weapons_methods || [],
          geographic_range: mo.geographic_range || "Unknown",
          escalation_trend: mo.escalation_trend || "Unknown",
        };
      }
      return null;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
        return null;
      }
      throw error;
    }
  },
  getRisk: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.RISK(id));
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
        return null;
      }
      throw error;
    }
  },
  getNetwork: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.NETWORK(id));
      return res.data?.data || res.data;
    } catch (error) {
      if (import.meta.env.VITE_DEMO_MODE === 'true') {
        return null;
      }
      throw error;
    }
  },
  create: async (payload: Record<string, unknown>) => {
    const res = await api.post(ENDPOINTS.OFFENDERS.CREATE, payload);
    return res.data;
  },
  update: async (id: string, payload: Record<string, unknown>) => {
    const res = await api.put(ENDPOINTS.OFFENDERS.UPDATE(id), payload);
    return res.data;
  },
};
