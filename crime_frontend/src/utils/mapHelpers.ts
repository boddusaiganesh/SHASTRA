import { RISK_COLORS } from "../constants/colorCodes";

export const getRiskColor = (score: number): string => {
  if (score >= 75) return RISK_COLORS.High;
  if (score >= 40) return RISK_COLORS.Medium;
  return RISK_COLORS.Low;
};

export const getRiskLevel = (score: number): string => {
  if (score >= 75) return "High";
  if (score >= 40) return "Medium";
  return "Low";
};

export const getIntensityColor = (intensity: number): string => {
  if (intensity >= 80) return "#991B1B";
  if (intensity >= 60) return "#EF4444";
  if (intensity >= 40) return "#F97316";
  if (intensity >= 20) return "#F59E0B";
  return "#22C55E";
};

export const karnatakaBounds: [[number, number], [number, number]] = [
  [11.5, 74.0],
  [18.5, 78.5],
];

export const karnatakaCenter: [number, number] = [15.3173, 75.7139];
