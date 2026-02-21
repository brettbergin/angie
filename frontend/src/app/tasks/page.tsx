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
    <div className="px-4 py-3 bg-gray-950 border-t border-gray-800 space-y-3 text-sm">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Task ID</span>
          <p className="text-gray-300 font-mono text-xs mt-0.5">{task.id}</p>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Source</span>
          <p className="text-gray-300 mt-0.5">{task.source_channel ?? "internal"}</p>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Created</span>
          <p className="text-gray-300 mt-0.5">{task.created_at ? formatDate(task.created_at) : "—"}</p>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Updated</span>
          <p className="text-gray-300 mt-0.5">{task.updated_at ? formatDate(task.updated_at) : "—"}</p>
        </div>
      </div>
      {task.input_data && Object.keys(task.input_data).length > 0 && (
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Input</span>
          <pre className="text-gray-300 bg-gray-900 rounded-lg p-2 mt-1 text-xs overflow-x-auto">{JSON.stringify(task.input_data, null, 2)}</pre>
        </div>
      )}
      {task.output_data && Object.keys(task.output_data).length > 0 && (
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wide">Output</span>
          <pre className="text-gray-300 bg-gray-900 rounded-lg p-2 mt-1 text-xs overflow-x-auto">{JSON.stringify(task.output_data, null, 2)}</pre>
        </div>
      )}
      {task.error && (
        <div>
          <span className="text-red-400 text-xs uppercase tracking-wide">Error</span>
          <pre className="text-red-300 bg-red-950/30 border border-red-900/30 rounded-lg p-2 mt-1 text-xs overflow-x-auto">{task.error}</pre>
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
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [token]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  };

  const filtered = (filter === "all" ? tasks : tasks.filter((t) => t.status === filter))
    .filter((t) => !search || t.title.toLowerCase().includes(search.toLowerCase()));
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

      <div className="flex gap-4 items-end">
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
        <div className="flex-1">
          <Input placeholder="Search tasks…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <Card>
        <CardHeader title="Task History" subtitle="Click a task to view details" />
        {sorted.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Activity className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p>No tasks match this filter.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {sorted.map((t) => (
              <div key={t.id}>
                <div className="flex items-center justify-between py-3 cursor-pointer hover:bg-gray-800/30 -mx-6 px-6 transition-colors" onClick={() => toggleExpand(t.id)}>
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    {expanded.has(t.id) ? <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-gray-200 truncate">{t.title}</p>
                      <p className="text-xs text-gray-500 font-mono">
                        {t.source_channel ?? "internal"} · {t.created_at ? formatDate(t.created_at) : "—"}
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
