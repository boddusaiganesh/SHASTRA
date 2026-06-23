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
  searchOffenders: async (query: string = "") => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.SEARCH, { params: { query } });
      const list = res.data?.offenders || res.data || [];
      return list.map(normalizeOffender);
    } catch {
      return mockOffenders.filter((o: any) => 
        !query || o.offender_name?.toLowerCase().includes(query.toLowerCase())
      ).map(normalizeOffender);
    }
  },
  getProfile: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.PROFILE(id));
      return normalizeOffender(res.data);
    } catch {
      return normalizeOffender(mockOffenders.find((o: any) => o.offender_id === id));
    }
  },
  getModusOperandi: async (id: string) => {
    try {
      const res = await api.get(ENDPOINTS.OFFENDERS.MODUS_OPERANDI(id));
      const mo = res.data;
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
    } catch {
      return null;
    }
  },
};
