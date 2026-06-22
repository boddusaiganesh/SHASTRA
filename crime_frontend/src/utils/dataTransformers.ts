export const transformCrimesForMap = (crimes: unknown[]) => {
  return (crimes as { crime_id: string; latitude: number; longitude: number; crime_type: string; date_time: string; location: string; district: string; status: string }[]).filter(
    (c) => c.latitude && c.longitude
  );
};

export const groupByField = <T extends Record<string, unknown>>(
  arr: T[],
  field: keyof T
): Record<string, T[]> => {
  return arr.reduce((acc, item) => {
    const key = String(item[field]);
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {} as Record<string, T[]>);
};

export const getSeverityWeight = (severity: string): number => {
  const weights: Record<string, number> = { Critical: 4, High: 3, Medium: 2, Low: 1 };
  return weights[severity] || 0;
};
