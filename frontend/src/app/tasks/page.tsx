"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Task } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { formatDate } from "@/lib/utils";
import { Activity, ChevronDown, ChevronRight } from "lucide-react";

const FILTERS = ["all", "success", "pending", "running", "failure"] as const;
const POLL_MS = 5000;

function TaskDetail({ task }: { task: Task }) {
  return (
    <div className="space-y-3 border-t border-gray-800 bg-gray-950 px-4 py-3 text-sm">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Task ID
          </span>
          <p className="mt-0.5 font-mono text-xs text-gray-300">{task.id}</p>
        </div>
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Source
          </span>
          <p className="mt-0.5 text-gray-300">
            {task.source_channel ?? "internal"}
          </p>
        </div>
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Created
          </span>
          <p className="mt-0.5 text-gray-300">
            {task.created_at ? formatDate(task.created_at) : "—"}
          </p>
        </div>
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Updated
          </span>
          <p className="mt-0.5 text-gray-300">
            {task.updated_at ? formatDate(task.updated_at) : "—"}
          </p>
        </div>
      </div>
      {task.input_data && Object.keys(task.input_data).length > 0 && (
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Input
          </span>
          <pre className="mt-1 overflow-x-auto rounded-lg bg-gray-900 p-2 text-xs text-gray-300">
            {JSON.stringify(task.input_data, null, 2)}
          </pre>
        </div>
      )}
      {task.output_data && Object.keys(task.output_data).length > 0 && (
        <div>
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Output
          </span>
          <pre className="mt-1 overflow-x-auto rounded-lg bg-gray-900 p-2 text-xs text-gray-300">
            {JSON.stringify(task.output_data, null, 2)}
          </pre>
        </div>
      )}
      {task.error && (
        <div>
          <span className="text-xs uppercase tracking-wide text-red-400">
            Error
          </span>
          <pre className="mt-1 overflow-x-auto rounded-lg border border-red-900/30 bg-red-950/30 p-2 text-xs text-red-300">
            {task.error}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function TasksPage() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = (t: string) =>
    api.tasks.list(t).then((data) => setTasks(data ?? []));

  useEffect(() => {
    if (!token) return;
    fetchTasks(token).finally(() => setLoading(false));
    timerRef.current = setInterval(() => fetchTasks(token), POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [token]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const filtered = (
    filter === "all" ? tasks : tasks.filter((t) => t.status === filter)
  ).filter(
    (t) => !search || t.title.toLowerCase().includes(search.toLowerCase())
  );
  const sorted = [...filtered].sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? "")
  );

  if (loading)
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Tasks</h1>
          <p className="mt-1 text-sm text-gray-400">
            {tasks.length} total · refreshing every {POLL_MS / 1000}s
          </p>
        </div>
      </div>

      <div className="flex items-end gap-4">
        <div className="flex gap-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === f
                  ? "bg-angie-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-100"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="flex-1">
          <Input
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardHeader
          title="Task History"
          subtitle="Click a task to view details"
        />
        {sorted.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <Activity className="mx-auto mb-2 h-10 w-10 opacity-30" />
            <p>No tasks match this filter.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {sorted.map((t) => (
              <div key={t.id}>
                <div
                  className="-mx-6 flex cursor-pointer items-center justify-between px-6 py-3 transition-colors hover:bg-gray-800/30"
                  onClick={() => toggleExpand(t.id)}
                >
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    {expanded.has(t.id) ? (
                      <ChevronDown className="h-4 w-4 flex-shrink-0 text-gray-500" />
                    ) : (
                      <ChevronRight className="h-4 w-4 flex-shrink-0 text-gray-500" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-gray-200">
                        {t.title}
                      </p>
                      <p className="font-mono text-xs text-gray-500">
                        {t.source_channel ?? "internal"} ·{" "}
                        {t.created_at ? formatDate(t.created_at) : "—"}
                      </p>
                    </div>
                  </div>
                  <Badge label={t.status} status={t.status} />
                </div>
                {expanded.has(t.id) && <TaskDetail task={t} />}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
