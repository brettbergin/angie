"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Schedule } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Clock, Plus, Trash2, X, Pencil } from "lucide-react";

export default function SchedulesPage() {
  const { token } = useAuth();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", cron_expression: "", agent_slug: "" });
  const [search, setSearch] = useState("");

  // Edit modal state
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "", cron_expression: "", agent_slug: "" });
  const [saving, setSaving] = useState(false);

  const fetchSchedules = useCallback(() => {
    if (!token) return;
    api.schedules.list(token).then((s) => setSchedules(s ?? [])).finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

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

  const handleToggle = async (s: Schedule) => {
    if (!token) return;
    await api.schedules.toggle(token, s.id);
    fetchSchedules();
  };

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this schedule?")) return;
    await api.schedules.delete(token, id);
    fetchSchedules();
  };

  const openEdit = (s: Schedule) => {
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

      <div className="grid grid-cols-2 gap-4">
        {filtered.map((s) => (
          <Card key={s.id} className="hover:border-angie-600/40 transition-colors group">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-600/20 border border-purple-600/30 flex items-center justify-center flex-shrink-0">
                  <Clock className="w-5 h-5 text-purple-400" />
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-gray-100">{s.name}</h3>
                  <p className="text-xs text-purple-400 font-mono">{s.cron_expression}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{s.cron_human}</p>
                  {s.description && <p className="text-sm text-gray-400 mt-1">{s.description}</p>}
                  {s.agent_slug && (
                    <span className="inline-block mt-1 text-[10px] font-medium bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">
                      @{s.agent_slug}
                    </span>
                  )}
                  {s.next_run_at && (
                    <p className="text-[10px] text-gray-500 mt-1">
                      Next: {new Date(s.next_run_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => handleToggle(s)} className="cursor-pointer">
                  <Badge label={s.is_enabled ? "enabled" : "disabled"} status={s.is_enabled ? "success" : "cancelled"} />
                </button>
                <button onClick={() => openEdit(s)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-all">
                  <Pencil className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(s.id)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-2 text-center py-16 text-gray-500">
            <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No schedules match your search." : "No schedules yet. Create one or ask @cron in chat."}</p>
          </div>
        )}
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" role="dialog" aria-label="Edit schedule"
          aria-modal="true" tabIndex={-1} ref={(el) => el?.focus()}
          onClick={(e) => { if (e.target === e.currentTarget) setEditing(null); }}
          onKeyDown={(e) => { if (e.key === "Escape") setEditing(null); }}>
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
              <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
              <Button size="sm" onClick={handleSaveEdit} disabled={saving || !editForm.name || !editForm.cron_expression}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
