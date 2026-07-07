import { KARNATAKA_DISTRICTS_WITH_CODES } from "../constants/districtsList";

const codeToNameMap: Record<string, string> = {};
KARNATAKA_DISTRICTS_WITH_CODES.forEach((d) => {
  codeToNameMap[d.district_id] = d.district_name;
  codeToNameMap[d.district_id.toLowerCase()] = d.district_name;
});

export function getDistrictName(districtIdOrName: string | undefined | null): string {
  if (!districtIdOrName) return "Unknown District";
  return codeToNameMap[districtIdOrName] || districtIdOrName;
}
