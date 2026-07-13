import { useEffect, useState } from "react";
import { settingsService } from "../services/settingsService";

export interface DistrictItem {
  district_id: string;
  district_name: string;
}

export function useDistricts() {
  const [districts, setDistricts] = useState<DistrictItem[]>([]);

  useEffect(() => {
    let mounted = true;
    let timeoutId: ReturnType<typeof setTimeout>;

    const fetchDistricts = async (retries = 3, delay = 1000) => {
      try {
        const d = await settingsService.getDistricts();
        if (!mounted) return;
        if (Array.isArray(d)) {
          setDistricts(d);
        } else if (d?.districts && Array.isArray(d.districts)) {
          setDistricts(d.districts);
        } else if (d?.data && Array.isArray(d.data)) {
          setDistricts(d.data);
        } else {
          setDistricts([]);
        }
      } catch (err) {
        if (!mounted) return;
        if (retries > 0) {
          console.warn(`Failed to fetch districts, retrying in ${delay}ms...`);
          timeoutId = setTimeout(() => fetchDistricts(retries - 1, delay * 2), delay);
        } else {
          console.error("Exhausted retries fetching districts", err);
          setDistricts([]);
        }
      }
    };

    fetchDistricts();

    return () => {
      mounted = false;
      clearTimeout(timeoutId);
    };
  }, []);

  return districts;
}
