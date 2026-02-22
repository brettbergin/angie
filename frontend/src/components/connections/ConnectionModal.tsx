"use client";

import { useEffect, useState } from "react";
import {
  api,
  type Connection,
  type ServiceDefinition,
  type TestResult,
} from "@/lib/api";
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

export function ConnectionModal({
  service,
  connection,
  onClose,
  onSaved,
}: Props) {
  const { token } = useAuth();
  const [fields, setFields] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    service.fields.forEach((f) => (init[f.key] = ""));
    return init;
  });
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>(
    {}
  );
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
        const hasValues = Object.values(fields).some(
          (value) => value.trim() !== ""
        );
        const payload = hasValues ? { credentials: fields } : {};
        await api.connections.update(token, connection.id, payload);
      } else {
        await api.connections.create(token, {
          service_type: service.key,
          credentials: fields,
        });
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
      setTestResult({
        success: false,
        message: "Test request failed",
        status: "error",
      });
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    if (
      !token ||
      !connection ||
      !confirm(
        "Disconnect this service? All credentials will be permanently deleted."
      )
    )
      return;
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="mx-4 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-gray-700 bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with brand color */}
        <div
          className="border-b border-gray-800 px-6 py-4"
          style={{ borderTopColor: service.color, borderTopWidth: 3 }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-lg text-lg font-bold text-white"
                style={{ backgroundColor: service.color }}
              >
                {service.name[0]}
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-100">
                  {service.name}
                </h2>
                <p className="text-xs text-gray-400">{service.description}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 text-gray-500 hover:text-gray-300"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <form
          autoComplete="off"
          onSubmit={(e) => e.preventDefault()}
          className="flex-1 space-y-5 overflow-y-auto p-6"
        >
          {/* Current status */}
          {connection && (
            <div className="flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-800/50 p-3">
              <span
                className={cn(
                  "h-2.5 w-2.5 flex-shrink-0 rounded-full",
                  connection.status === "connected" && "bg-green-400",
                  connection.status === "expired" && "bg-amber-400",
                  connection.status === "error" && "bg-red-400",
                  connection.status === "disconnected" && "bg-gray-500"
                )}
              />
              <span className="text-sm capitalize text-gray-300">
                {connection.status}
              </span>
              {connection.last_tested_at && (
                <span className="ml-auto text-xs text-gray-500">
                  Last tested:{" "}
                  {new Date(connection.last_tested_at).toLocaleString()}
                </span>
              )}
            </div>
          )}

          {/* Masked credentials preview */}
          {connection &&
            Object.keys(connection.masked_credentials).length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Current Credentials
                </h3>
                <div className="space-y-1">
                  {Object.entries(connection.masked_credentials).map(
                    ([key, val]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-gray-400">{key}</span>
                        <span className="font-mono text-xs text-gray-500">
                          {val}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

          {/* Credential form */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              {connection ? "Update Credentials" : "Enter Credentials"}
            </h3>
            {service.fields.map((field) => (
              <div key={field.key} className="relative">
                <Input
                  label={field.label}
                  type={
                    field.type === "password" && !showPasswords[field.key]
                      ? "password"
                      : "text"
                  }
                  placeholder={
                    connection
                      ? "(unchanged)"
                      : `Enter ${field.label.toLowerCase()}`
                  }
                  value={fields[field.key]}
                  autoComplete="off"
                  onChange={(e) =>
                    setFields((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                />
                {field.type === "password" && (
                  <button
                    type="button"
                    onClick={() =>
                      setShowPasswords((prev) => ({
                        ...prev,
                        [field.key]: !prev[field.key],
                      }))
                    }
                    className="absolute right-3 top-8 text-gray-500 hover:text-gray-300"
                  >
                    {showPasswords[field.key] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={cn(
                "flex items-center gap-2 rounded-lg border p-3 text-sm",
                testResult.success
                  ? "border-green-600/30 bg-green-600/10 text-green-400"
                  : "border-red-600/30 bg-red-600/10 text-red-400"
              )}
            >
              {testResult.success ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              {testResult.message}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-600/30 bg-red-600/10 p-3 text-sm text-red-400">
              <XCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </form>
        <div className="flex items-center gap-3 border-t border-gray-800 px-6 py-4">
          {connection && (
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={handleTest}
                disabled={testing}
              >
                {testing ? <Spinner className="mr-1 h-4 w-4" /> : null}
                Test Connection
              </Button>
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:text-red-300 disabled:opacity-50"
              >
                <Unplug className="h-4 w-4" />
                {disconnecting ? "Disconnecting…" : "Disconnect"}
              </button>
            </>
          )}
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || (!hasValues && !connection)}
            >
              {saving ? "Saving…" : connection ? "Update" : "Connect"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
