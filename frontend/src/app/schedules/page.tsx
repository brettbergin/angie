"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Schedule } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Clock, Plus, Trash2, X, Pencil, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function SchedulesPage() {
  const { token } = useAuth();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", cron_expression: "", agent_slug: "" });
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Edit modal state
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "", cron_expression: "", agent_slug: "" });
  const [saving, setSaving] = useState(false);

  const fetchSchedules = useCallback(() => {
    if (!token) return;
    api.schedules.list(token).then((s) => setSchedules(s ?? [])).finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async () => {
    if (!token || !form.name || !form.cron_expression) return;
    setCreating(true);
    try {
      await api.schedules.create(token, {
        name: form.name,
        description: form.description || undefined,
        cron_expression: form.cron_expression,
        agent_slug: form.agent_slug || undefined,
      });
      setForm({ name: "", description: "", cron_expression: "", agent_slug: "" });
      setShowCreate(false);
      fetchSchedules();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create schedule");
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (e: React.MouseEvent, s: Schedule) => {
    e.stopPropagation();
    if (!token) return;
    try {
      await api.schedules.toggle(token, s.id);
      fetchSchedules();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to toggle schedule");
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!token || !confirm("Delete this schedule?")) return;
    try {
      await api.schedules.delete(token, id);
      fetchSchedules();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete schedule");
    }
  };

  const openEdit = (e: React.MouseEvent, s: Schedule) => {
    e.stopPropagation();
    setEditing(s);
    setEditForm({
      name: s.name,
      description: s.description || "",
      cron_expression: s.cron_expression,
      agent_slug: s.agent_slug || "",
    });
  };

  const handleSaveEdit = async () => {
    if (!token || !editing) return;
    setSaving(true);
    try {
      await api.schedules.update(token, editing.id, {
        name: editForm.name,
        description: editForm.description || null,
        cron_expression: editForm.cron_expression,
        agent_slug: editForm.agent_slug || null,
      });
      setEditing(null);
      fetchSchedules();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update schedule");
    } finally {
      setSaving(false);
    }
  };

  const filtered = schedules.filter((s) =>
    !search ||
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.cron_human.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Schedules</h1>
          <p className="text-sm text-gray-400 mt-1">Recurring cron tasks managed by Angie</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showCreate ? "Cancel" : "New Schedule"}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-angie-600/40">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="Name" placeholder="Nightly Backup" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Cron Expression" placeholder="0 0 * * *" value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} />
            </div>
            <Input label="Description" placeholder="Run a backup of all databases every night" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Input label="Agent Slug (optional)" placeholder="e.g. github" value={form.agent_slug}
              onChange={(e) => setForm({ ...form, agent_slug: e.target.value })} />
            <Button size="sm" onClick={handleCreate} disabled={creating || !form.name || !form.cron_expression}>
              {creating ? "Creating…" : "Create Schedule"}
            </Button>
          </div>
        </Card>
      )}

      <Input placeholder="Search schedules…" value={search} onChange={(e) => setSearch(e.target.value)} />

      <Card>
        {/* Table header */}
        <div className="flex items-center gap-4 px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-800">
          <div className="w-5" />
          <div className="flex-1">Name</div>
          <div className="w-44 text-center">Schedule</div>
          <div className="w-20 text-center">Status</div>
          <div className="w-20" />
        </div>

        <div className="divide-y divide-gray-800">
          {filtered.map((s) => (
            <div key={s.id}>
              {/* Row */}
              <div
                className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-gray-800/30 transition-colors group"
                onClick={() => toggleExpand(s.id)}
              >
                <div className="w-5 flex items-center text-gray-500">
                  {expanded.has(s.id) ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn("text-sm font-medium", s.is_enabled ? "text-gray-100" : "text-gray-500")}>{s.name}</p>
                  <p className="text-xs text-gray-500 truncate">{s.cron_human}</p>
                </div>
                <div className="w-44 text-center">
                  <span className="text-xs font-mono text-purple-400">{s.cron_expression}</span>
                </div>
                <div className="w-20 flex justify-center">
                  <button
                    onClick={(e) => handleToggle(e, s)}
                    className={cn(
                      "relative w-9 h-5 rounded-full transition-colors flex-shrink-0",
                      s.is_enabled ? "bg-green-500" : "bg-gray-600"
                    )}
                    title={s.is_enabled ? "Disable schedule" : "Enable schedule"}
                    aria-label={s.is_enabled ? `Disable ${s.name}` : `Enable ${s.name}`}
                  >
                    <span className={cn(
                      "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform",
                      s.is_enabled && "translate-x-4"
                    )} />
                  </button>
                </div>
                <div className="w-20 flex justify-end gap-1">
                  <button onClick={(e) => openEdit(e, s)}
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1.5 rounded-lg hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-all"
                    title="Edit schedule" aria-label={`Edit ${s.name}`}>
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={(e) => handleDelete(e, s.id)}
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1.5 rounded-lg hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-all"
                    title="Delete schedule" aria-label={`Delete ${s.name}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Expanded detail panel */}
              {expanded.has(s.id) && (
                <div className="px-4 pb-4 pt-1 ml-9 border-l-2 border-purple-600/30 space-y-3">
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    {s.description && (
                      <div className="col-span-2">
                        <span className="text-gray-500 text-xs uppercase tracking-wider">Description</span>
                        <p className="text-gray-300 mt-0.5">{s.description}</p>
                      </div>
                    )}
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Cron Expression</span>
                      <p className="text-purple-400 font-mono mt-0.5">{s.cron_expression}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Runs</span>
                      <p className="text-gray-300 mt-0.5">{s.cron_human}</p>
                    </div>
                    {s.agent_slug && (
                      <div>
                        <span className="text-gray-500 text-xs uppercase tracking-wider">Agent</span>
                        <p className="text-gray-300 mt-0.5">
                          <span className="inline-block text-xs font-medium bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">
                            @{s.agent_slug}
                          </span>
                        </p>
                      </div>
                    )}
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Status</span>
                      <p className={cn("mt-0.5", s.is_enabled ? "text-green-400" : "text-gray-500")}>
                        {s.is_enabled ? "Enabled" : "Disabled"}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Next Run</span>
                      <p className="text-gray-300 mt-0.5">{formatDate(s.next_run_at)}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Last Run</span>
                      <p className="text-gray-300 mt-0.5">{formatDate(s.last_run_at)}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Created</span>
                      <p className="text-gray-300 mt-0.5">{formatDate(s.created_at)}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 text-xs uppercase tracking-wider">Updated</span>
                      <p className="text-gray-300 mt-0.5">{formatDate(s.updated_at)}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16 text-gray-500">
            <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No schedules match your search." : "No schedules yet. Create one or ask @cron in chat."}</p>
          </div>
        )}
      </Card>

      {/* Edit modal with focus trap */}
      {editing && (
        <EditModal
          editForm={editForm}
          setEditForm={setEditForm}
          saving={saving}
          onSave={handleSaveEdit}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function EditModal({
  editForm,
  setEditForm,
  saving,
  onSave,
  onClose,
}: {
  editForm: { name: string; description: string; cron_expression: string; agent_slug: string };
  setEditForm: (f: typeof editForm) => void;
  saving: boolean;
  onSave: () => void;
  onClose: () => void;
}) {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = modalRef.current;
    if (!el) return;
    el.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key !== "Tab") return;

      const focusable = el.querySelectorAll<HTMLElement>(
        'input, button, textarea, select, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };

    el.addEventListener("keydown", handleKeyDown);
    return () => el.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      role="dialog"
      aria-label="Edit schedule"
      aria-modal="true"
      tabIndex={-1}
      ref={modalRef}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4">
        <h2 className="text-lg font-semibold text-gray-100">Edit Schedule</h2>
        <Input label="Name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
        <Input label="Cron Expression" value={editForm.cron_expression}
          onChange={(e) => setEditForm({ ...editForm, cron_expression: e.target.value })} />
        <Input label="Description" value={editForm.description}
          onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
        <Input label="Agent Slug" value={editForm.agent_slug}
          onChange={(e) => setEditForm({ ...editForm, agent_slug: e.target.value })} />
        <div className="flex justify-end gap-3 pt-2">
          <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={onSave} disabled={saving || !editForm.name || !editForm.cron_expression}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
