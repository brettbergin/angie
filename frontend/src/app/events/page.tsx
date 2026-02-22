"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Event } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { formatDate } from "@/lib/utils";
import { Zap } from "lucide-react";

const EVENT_FILTERS = [
  "all",
  "user_message",
  "cron",
  "webhook",
  "system",
  "task_complete",
  "task_failed",
] as const;

export default function EventsPage() {
  const { token } = useAuth();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!token) return;
    api.events
      .list(token)
      .then((e) => setEvents(e ?? []))
      .finally(() => setLoading(false));
  }, [token]);

  const filtered = events
    .filter((e) => filter === "all" || e.type === filter)
    .filter(
      (e) =>
        !search ||
        e.type.toLowerCase().includes(search.toLowerCase()) ||
        (e.source_channel ?? "").toLowerCase().includes(search.toLowerCase())
    );
  const sorted = [...filtered].sort((a, b) =>
    b.created_at.localeCompare(a.created_at)
  );

  if (loading)
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Event Log</h1>
        <p className="mt-1 text-sm text-gray-400">
          {events.length} events recorded
        </p>
      </div>

      <div className="flex items-end gap-4">
        <div className="flex flex-wrap gap-2">
          {EVENT_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === f
                  ? "bg-angie-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-100"
              }`}
            >
              {f === "all" ? "all" : f.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <div className="flex-1">
          <Input
            placeholder="Search events…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardHeader title="All Events" />
        {sorted.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <Zap className="mx-auto mb-2 h-10 w-10 opacity-30" />
            <p>
              {search || filter !== "all"
                ? "No events match this filter."
                : "No events yet."}
            </p>
          </div>
        ) : (
          <div className="space-y-0">
            {sorted.map((ev) => (
              <div
                key={ev.id}
                className="flex items-center justify-between border-b border-gray-800 py-3 last:border-0"
              >
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <Zap className="h-4 w-4 flex-shrink-0 text-angie-400" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-200">
                      {ev.type}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {ev.source_channel ?? "internal"} ·{" "}
                      {formatDate(ev.created_at)}
                    </p>
                  </div>
                </div>
                <Badge
                  label={ev.processed ? "processed" : "pending"}
                  status={ev.processed ? "success" : "pending"}
                />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
