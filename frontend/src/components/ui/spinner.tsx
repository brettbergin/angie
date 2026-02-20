import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("animate-spin rounded-full border-2 border-gray-600 border-t-angie-500 h-5 w-5", className)} />
  );
}
