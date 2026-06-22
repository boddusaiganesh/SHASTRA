import dayjs from "dayjs";

export const formatDate = (date: string | Date) => dayjs(date).format("DD-MM-YYYY");
export const formatDateTime = (date: string | Date) => dayjs(date).format("DD-MM-YYYY HH:mm");
export const formatTime = (date: string | Date) => dayjs(date).format("HH:mm");
export const formatRelative = (date: string | Date) => {
  const diff = dayjs().diff(dayjs(date), "minute");
  if (diff < 1) return "Just now";
  if (diff < 60) return `${diff}m ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
  return `${Math.floor(diff / 1440)}d ago`;
};
