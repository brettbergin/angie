import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  success:   "bg-green-900/50 text-green-400 border-green-800",
  pending:   "bg-yellow-900/50 text-yellow-400 border-yellow-800",
  running:   "bg-blue-900/50 text-blue-400 border-blue-800",
  queued:    "bg-blue-900/40 text-blue-300 border-blue-700",
  failure:   "bg-red-900/50 text-red-400 border-red-800",
  cancelled: "bg-gray-800 text-gray-400 border-gray-700",
  retrying:  "bg-orange-900/50 text-orange-400 border-orange-800",
  default:   "bg-gray-800 text-gray-300 border-gray-700",
};

export function Badge({ label, status }: { label: string; status?: string }) {
  const color = colors[status ?? label.toLowerCase()] ?? colors.default;
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border", color)}>
      {label}
    </span>
  );
}
