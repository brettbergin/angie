"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Task } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatDate } from "@/lib/utils";
import { Activity } from "lucide-react";

const FILTERS = ["all", "success", "pending", "running", "failure"] as const;
const POLL_MS = 5000;

export default function TasksPage() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = (t: string) =>
    api.tasks.list(t).then((data) => setTasks(data ?? []));

  useEffect(() => {
    if (!token) return;
    fetchTasks(token).finally(() => setLoading(false));
    timerRef.current = setInterval(() => fetchTasks(token), POLL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [token]);

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);
  const sorted = [...filtered].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Tasks</h1>
          <p className="text-sm text-gray-400 mt-1">{tasks.length} total · refreshing every {POLL_MS / 1000}s</p>
        </div>
      </div>

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f ? "bg-angie-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-100"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader title="Task History" />
        {sorted.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Activity className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p>No tasks match this filter.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {sorted.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-200 truncate">{t.title}</p>
                  <p className="text-xs text-gray-500 font-mono">
                    {t.source_channel ?? "internal"} · {t.created_at ? formatDate(t.created_at) : "—"}
                  </p>
                </div>
                <Badge label={t.status} status={t.status} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
