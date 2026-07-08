import { useEffect, useState } from "react";
import { settingsService } from "../services/settingsService";

export interface DistrictItem {
  district_id: string;
  district_name: string;
}

export function useDistricts() {
  const [districts, setDistricts] = useState<DistrictItem[]>([]);

  useEffect(() => {
    settingsService.getDistricts().then((d: any) => {
      if (Array.isArray(d)) {
        setDistricts(d);
      } else if (d?.districts && Array.isArray(d.districts)) {
        setDistricts(d.districts);
      } else if (d?.data && Array.isArray(d.data)) {
        setDistricts(d.data);
      } else {
        setDistricts([]);
      }
    }).catch(() => {
      setDistricts([]);
    });
  }, []);

  return districts;
}
