export const CRIME_TYPES = [
  "All",
  "Theft",
  "Murder",
  "Robbery",
  "Assault",
  "Kidnapping",
  "Fraud",
  "Drug Offense",
  "Sexual Offense",
  "Vehicle Theft",
  "Burglary",
  "Arson",
  "Cybercrime",
  "Extortion",
  "Human Trafficking",
];

export const CRIME_TYPE_COLORS: Record<string, string> = {
  Theft: "#F59E0B",
  Murder: "#EF4444",
  Robbery: "#DC2626",
  Assault: "#F97316",
  Kidnapping: "#7C3AED",
  Fraud: "#3B82F6",
  "Drug Offense": "#10B981",
  "Sexual Offense": "#EC4899",
  "Vehicle Theft": "#6366F1",
  Burglary: "#8B5CF6",
  Arson: "#FF6B35",
  Cybercrime: "#06B6D4",
  Extortion: "#84CC16",
  "Human Trafficking": "#F43F5E",
};

export const RISK_LEVELS = ["High", "Medium", "Low"] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

export const SEVERITY_LEVELS = ["Critical", "High", "Medium", "Low"] as const;
export type SeverityLevel = (typeof SEVERITY_LEVELS)[number];

export const STATUS_OPTIONS = [
  "Active",
  "Imprisoned",
  "Absconding",
  "Deceased",
] as const;
export type StatusOption = (typeof STATUS_OPTIONS)[number];

export const NODE_TYPES = [
  "criminal",
  "victim",
  "location",
  "organization",
] as const;
export type NodeType = (typeof NODE_TYPES)[number];

export const TIME_OF_DAY = [
  "All",
  "Morning (6AM-12PM)",
  "Afternoon (12PM-6PM)",
  "Evening (6PM-10PM)",
  "Night (10PM-6AM)",
];

export const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export const USER_ROLES = [
  "SCRB Officer",
  "District Officer",
  "Investigator",
] as const;
export type UserRole = (typeof USER_ROLES)[number];
