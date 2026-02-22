"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Task, type Event } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatDate } from "@/lib/utils";
import { Activity, CheckCircle, Clock, XCircle, Zap } from "lucide-react";

type Stats = {
  total: number;
  success: number;
  failed: number;
  pending: number;
};

function computeStats(tasks: Task[]): Stats {
  return tasks.reduce(
    (acc, t) => {
      acc.total++;
      if (t.status === "success") acc.success++;
      else if (t.status === "failure") acc.failed++;
      else acc.pending++;
      return acc;
    },
    { total: 0, success: 0, failed: 0, pending: 0 }
  );
}

export default function DashboardPage() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.tasks.list(token), api.events.list(token)])
      .then(([t, e]) => {
        setTasks(t ?? []);
        setEvents(e ?? []);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const stats = computeStats(tasks);
  const recent = [...tasks].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 8);
  const recentEvents = [...events].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 8);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">History</h1>
        <p className="text-sm text-gray-400 mt-1">Angie is running · monitoring your tasks and events</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Tasks", value: stats.total, icon: Activity, color: "text-angie-400" },
          { label: "Successful", value: stats.success, icon: CheckCircle, color: "text-green-400" },
          { label: "Pending", value: stats.pending, icon: Clock, color: "text-yellow-400" },
          { label: "Failed", value: stats.failed, icon: XCircle, color: "text-red-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="flex items-center gap-4">
            <div className={`${color} flex-shrink-0`}>
              <Icon className="w-8 h-8" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-100">{value}</p>
              <p className="text-xs text-gray-400">{label}</p>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Recent tasks */}
        <Card>
          <CardHeader title="Recent Tasks" subtitle="Latest task activity" />
          {recent.length === 0 ? (
            <p className="text-sm text-gray-500">No tasks yet.</p>
          ) : (
            <div className="space-y-2">
              {recent.map((t) => (
                <div key={t.id} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-gray-200 truncate">{t.title}</p>
                    <p className="text-xs text-gray-500">{formatDate(t.created_at)}</p>
                  </div>
                  <Badge label={t.status} status={t.status} />
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Recent events */}
        <Card>
          <CardHeader title="Event Log" subtitle="Incoming events" />
          {recentEvents.length === 0 ? (
            <p className="text-sm text-gray-500">No events yet.</p>
          ) : (
            <div className="space-y-2">
              {recentEvents.map((ev) => (
                <div key={ev.id} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <Zap className="w-3.5 h-3.5 text-angie-400 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm text-gray-200 truncate">{ev.type}</p>
                      <p className="text-xs text-gray-500">{ev.source_channel ?? "internal"} · {formatDate(ev.created_at)}</p>
                    </div>
                  </div>
                  <Badge label={ev.processed ? "processed" : "pending"} status={ev.processed ? "success" : "pending"} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
