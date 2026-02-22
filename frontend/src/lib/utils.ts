import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Parse a date string as UTC even if the server omits the trailing Z. */
export function parseUTC(dateStr: string): Date {
  if (
    !dateStr.endsWith("Z") &&
    !dateStr.includes("+") &&
    !dateStr.includes("-", 10)
  ) {
    return new Date(dateStr + "Z");
  }
  return new Date(dateStr);
}

export function formatDate(iso: string): string {
  return parseUTC(iso).toLocaleString();
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    success: "text-green-400",
    pending: "text-yellow-400",
    running: "text-blue-400",
    queued: "text-blue-300",
    failure: "text-red-400",
    cancelled: "text-gray-400",
    retrying: "text-orange-400",
  };
  return map[status] ?? "text-gray-400";
}
