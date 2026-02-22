"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Connection, type ServiceDefinition, type TestResult } from "@/lib/api";
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
        "w-2.5 h-2.5 rounded-full flex-shrink-0",
        status === "connected" && "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]",
        status === "expired" && "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]",
        status === "error" && "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.5)]",
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
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});

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
      setTestResults((prev) => ({ ...prev, [conn.id]: { success: false, message: "Test failed", status: "error" } }));
    } finally {
      setTestingId(null);
    }
  };

  const connectedCount = connections.filter((c) => c.status === "connected").length;
  const errorCount = connections.filter((c) => c.status === "error" || c.status === "expired").length;

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Connections</h1>
        <p className="text-sm text-gray-400 mt-1">Connect your services to Angie</p>
        <div className="flex gap-4 mt-3">
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-2 h-2 rounded-full bg-green-400" />
            {connectedCount} connected
          </span>
          {errorCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2 h-2 rounded-full bg-red-400" />
              {errorCount} need attention
            </span>
          )}
          <span className="text-xs text-gray-500">
            {services.length - connections.length} available
          </span>
        </div>
      </div>

      <Input placeholder="Search services…" value={search} onChange={(e) => setSearch(e.target.value)} autoComplete="off" />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((svc) => {
          const conn = svc.connection;
          const isConnected = conn?.status === "connected";
          const isTesting = testingId === conn?.id;
          const quickResult = conn ? testResults[conn.id] : undefined;

          return (
            <Card
              key={svc.key}
              className={cn(
                "cursor-pointer hover:border-gray-600 transition-all group",
                isConnected && "border-green-600/20"
              )}
              onClick={() => setSelected(svc)}
            >
              <div className="flex items-start gap-3">
                {/* Brand icon */}
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
                  style={{ backgroundColor: svc.color }}
                >
                  {svc.name[0]}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-100 truncate">{svc.name}</h3>
                    <StatusDot status={conn?.status ?? ""} />
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{svc.description}</p>

                  <div className="flex items-center gap-2 mt-2">
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        isConnected
                          ? "bg-green-600/10 text-green-400 border border-green-600/20"
                          : conn?.status === "expired"
                            ? "bg-amber-600/10 text-amber-400 border border-amber-600/20"
                            : conn?.status === "error"
                              ? "bg-red-600/10 text-red-400 border border-red-600/20"
                              : "bg-gray-800 text-gray-500 border border-gray-700"
                      )}
                    >
                      {statusLabel(conn?.status)}
                    </span>

                    {conn && (
                      <button
                        onClick={(e) => handleQuickTest(e, conn)}
                        disabled={isTesting}
                        className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-gray-300 transition-all p-1"
                        title="Test connection"
                      >
                        {isTesting ? <Spinner className="w-3.5 h-3.5" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </div>

                  {quickResult && (
                    <p className={cn("text-xs mt-1.5", quickResult.success ? "text-green-400" : "text-red-400")}>
                      {quickResult.message}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          );
        })}

        {filtered.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-500">
            <Plug className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No services match your search." : "No services available."}</p>
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
