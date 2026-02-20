"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Task } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatDate } from "@/lib/utils";
import { Activity } from "lucide-react";

const FILTERS = ["all", "success", "pending", "running", "failure"] as const;

export default function TasksPage() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<typeof FILTERS[number]>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.tasks.list(token).then((t) => setTasks(t ?? [])).finally(() => setLoading(false));
  }, [token]);

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);
  const sorted = [...filtered].sort((a, b) => b.created_at.localeCompare(a.created_at));

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Tasks</h1>
        <p className="text-sm text-gray-400 mt-1">{tasks.length} total tasks</p>
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
          <div className="space-y-0">
            {sorted.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-200 truncate">{t.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {t.source_channel ?? "internal"} · {formatDate(t.created_at)}
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
