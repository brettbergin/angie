"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  api,
  type Connection,
  type ServiceDefinition,
  type TestResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ConnectionModal } from "@/components/connections/ConnectionModal";
import { Plug, RefreshCw } from "lucide-react";

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "h-2.5 w-2.5 flex-shrink-0 rounded-full",
        status === "connected" &&
          "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]",
        status === "expired" &&
          "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]",
        status === "error" &&
          "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.5)]",
        (!status || status === "disconnected") && "bg-gray-600"
      )}
    />
  );
}

function statusLabel(status: string | undefined): string {
  if (!status || status === "disconnected") return "Not Connected";
  if (status === "connected") return "Connected";
  if (status === "expired") return "Expired";
  return "Error";
}

type MergedService = ServiceDefinition & { connection: Connection | null };

export default function ConnectionsPage() {
  const { token } = useAuth();
  const [services, setServices] = useState<ServiceDefinition[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<MergedService | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>(
    {}
  );

  const fetchAll = useCallback(async () => {
    if (!token) return;
    try {
      const [svc, conn] = await Promise.all([
        api.connections.services(token),
        api.connections.list(token),
      ]);
      setServices(svc ?? []);
      setConnections(conn ?? []);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const merged: MergedService[] = services.map((svc) => ({
    ...svc,
    connection: connections.find((c) => c.service_type === svc.key) ?? null,
  }));

  const filtered = merged.filter(
    (s) =>
      !search ||
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.key.toLowerCase().includes(search.toLowerCase())
  );

  const handleQuickTest = async (e: React.MouseEvent, conn: Connection) => {
    e.stopPropagation();
    if (!token) return;
    setTestingId(conn.id);
    try {
      const result = await api.connections.test(token, conn.id);
      setTestResults((prev) => ({ ...prev, [conn.id]: result }));
      await fetchAll();
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [conn.id]: { success: false, message: "Test failed", status: "error" },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const connectedCount = connections.filter(
    (c) => c.status === "connected"
  ).length;
  const errorCount = connections.filter(
    (c) => c.status === "error" || c.status === "expired"
  ).length;

  if (loading)
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Connections</h1>
        <p className="mt-1 text-sm text-gray-400">
          Connect your services to Angie
        </p>
        <div className="mt-3 flex gap-4">
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="h-2 w-2 rounded-full bg-green-400" />
            {connectedCount} connected
          </span>
          {errorCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="h-2 w-2 rounded-full bg-red-400" />
              {errorCount} need attention
            </span>
          )}
          <span className="text-xs text-gray-500">
            {services.length - connections.length} available
          </span>
        </div>
      </div>

      <Input
        placeholder="Search services…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        autoComplete="off"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((svc) => {
          const conn = svc.connection;
          const isConnected = conn?.status === "connected";
          const isTesting = testingId === conn?.id;
          const quickResult = conn ? testResults[conn.id] : undefined;

          return (
            <Card
              key={svc.key}
              className={cn(
                "group cursor-pointer transition-all hover:border-gray-600",
                isConnected && "border-green-600/20"
              )}
              onClick={() => setSelected(svc)}
            >
              <div className="flex items-start gap-3">
                {/* Brand icon */}
                <div
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-lg font-bold text-white"
                  style={{ backgroundColor: svc.color }}
                >
                  {svc.name[0]}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-semibold text-gray-100">
                      {svc.name}
                    </h3>
                    <StatusDot status={conn?.status ?? ""} />
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-gray-400">
                    {svc.description}
                  </p>

                  <div className="mt-2 flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs",
                        isConnected
                          ? "border border-green-600/20 bg-green-600/10 text-green-400"
                          : conn?.status === "expired"
                            ? "border border-amber-600/20 bg-amber-600/10 text-amber-400"
                            : conn?.status === "error"
                              ? "border border-red-600/20 bg-red-600/10 text-red-400"
                              : "border border-gray-700 bg-gray-800 text-gray-500"
                      )}
                    >
                      {statusLabel(conn?.status)}
                    </span>

                    {conn && (
                      <button
                        onClick={(e) => handleQuickTest(e, conn)}
                        disabled={isTesting}
                        className="p-1 text-gray-500 opacity-0 transition-all hover:text-gray-300 group-hover:opacity-100"
                        title="Test connection"
                      >
                        {isTesting ? (
                          <Spinner className="h-3.5 w-3.5" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                      </button>
                    )}
                  </div>

                  {quickResult && (
                    <p
                      className={cn(
                        "mt-1.5 text-xs",
                        quickResult.success ? "text-green-400" : "text-red-400"
                      )}
                    >
                      {quickResult.message}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          );
        })}

        {filtered.length === 0 && (
          <div className="col-span-3 py-16 text-center text-gray-500">
            <Plug className="mx-auto mb-3 h-12 w-12 opacity-30" />
            <p>
              {search
                ? "No services match your search."
                : "No services available."}
            </p>
          </div>
        )}
      </div>

      {selected && (
        <ConnectionModal
          service={selected}
          connection={selected.connection}
          onClose={() => setSelected(null)}
          onSaved={() => {
            setSelected(null);
            fetchAll();
          }}
        />
      )}
    </div>
  );
}
