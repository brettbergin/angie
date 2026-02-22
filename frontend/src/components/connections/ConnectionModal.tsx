"use client";

import { useEffect, useState } from "react";
import { api, type Connection, type ServiceDefinition, type TestResult } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { X, Eye, EyeOff, CheckCircle2, XCircle, Unplug } from "lucide-react";

type Props = {
  service: ServiceDefinition;
  connection: Connection | null;
  onClose: () => void;
  onSaved: () => void;
};

export function ConnectionModal({ service, connection, onClose, onSaved }: Props) {
  const { token } = useAuth();
  const [fields, setFields] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    service.fields.forEach((f) => (init[f.key] = ""));
    return init;
  });
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      if (connection) {
        // Only send non-empty fields on update so unchanged secrets aren't wiped
        const nonEmpty = Object.fromEntries(
          Object.entries(fields).filter(([, v]) => v.trim() !== "")
        );
        const payload = Object.keys(nonEmpty).length > 0 ? { credentials: nonEmpty } : {};
        await api.connections.update(token, connection.id, payload);
      } else {
        await api.connections.create(token, { service_type: service.key, credentials: fields });
      }
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!token || !connection) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.connections.test(token, connection.id);
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: "Test request failed", status: "error" });
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!token || !connection || !confirm("Disconnect this service? All credentials will be permanently deleted.")) return;
    setDisconnecting(true);
    try {
      await api.connections.delete(token, connection.id);
      onSaved();
    } catch {
      setError("Failed to disconnect");
      setDisconnecting(false);
    }
  };

  const hasValues = Object.values(fields).some((v) => v.trim().length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with brand color */}
        <div className="px-6 py-4 border-b border-gray-800" style={{ borderTopColor: service.color, borderTopWidth: 3 }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg"
                style={{ backgroundColor: service.color }}
              >
                {service.name[0]}
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-100">{service.name}</h2>
                <p className="text-xs text-gray-400">{service.description}</p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300 p-1">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form autoComplete="off" onSubmit={(e) => e.preventDefault()} className="overflow-y-auto p-6 space-y-5 flex-1">
          {/* Current status */}
          {connection && (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
              <span
                className={cn(
                  "w-2.5 h-2.5 rounded-full flex-shrink-0",
                  connection.status === "connected" && "bg-green-400",
                  connection.status === "expired" && "bg-amber-400",
                  connection.status === "error" && "bg-red-400",
                  connection.status === "disconnected" && "bg-gray-500"
                )}
              />
              <span className="text-sm text-gray-300 capitalize">{connection.status}</span>
              {connection.last_tested_at && (
                <span className="text-xs text-gray-500 ml-auto">Last tested: {new Date(connection.last_tested_at).toLocaleString()}</span>
              )}
            </div>
          )}

          {/* Masked credentials preview */}
          {connection && Object.keys(connection.masked_credentials).length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Current Credentials</h3>
              <div className="space-y-1">
                {Object.entries(connection.masked_credentials).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">{key}</span>
                    <span className="text-gray-500 font-mono text-xs">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Credential form */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {connection ? "Update Credentials" : "Enter Credentials"}
            </h3>
            {service.fields.map((field) => (
              <div key={field.key} className="relative">
                <Input
                  label={field.label}
                  type={field.type === "password" && !showPasswords[field.key] ? "password" : "text"}
                  placeholder={connection ? "(unchanged)" : `Enter ${field.label.toLowerCase()}`}
                  value={fields[field.key]}
                  autoComplete="off"
                  onChange={(e) => setFields((prev) => ({ ...prev, [field.key]: e.target.value }))}
                />
                {field.type === "password" && (
                  <button
                    type="button"
                    onClick={() => setShowPasswords((prev) => ({ ...prev, [field.key]: !prev[field.key] }))}
                    className="absolute right-3 top-8 text-gray-500 hover:text-gray-300"
                  >
                    {showPasswords[field.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={cn(
                "flex items-center gap-2 p-3 rounded-lg border text-sm",
                testResult.success ? "border-green-600/30 bg-green-600/10 text-green-400" : "border-red-600/30 bg-red-600/10 text-red-400"
              )}
            >
              {testResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {testResult.message}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg border border-red-600/30 bg-red-600/10 text-red-400 text-sm">
              <XCircle className="w-4 h-4" />
              {error}
            </div>
          )}
        </form>
        <div className="px-6 py-4 border-t border-gray-800 flex items-center gap-3">
          {connection && (
            <>
              <Button size="sm" variant="secondary" onClick={handleTest} disabled={testing}>
                {testing ? <Spinner className="w-4 h-4 mr-1" /> : null}
                Test Connection
              </Button>
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 disabled:opacity-50 px-3 py-1.5"
              >
                <Unplug className="w-4 h-4" />
                {disconnecting ? "Disconnecting…" : "Disconnect"}
              </button>
            </>
          )}
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving || (!hasValues && !connection)}>
              {saving ? "Saving…" : connection ? "Update" : "Connect"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
