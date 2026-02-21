import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
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
