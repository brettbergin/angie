"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Workflow } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { GitBranch, Plus, Trash2, X } from "lucide-react";

export default function WorkflowsPage() {
  const { token } = useAuth();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "", trigger_event: "" });
  const [search, setSearch] = useState("");

  const fetchWorkflows = useCallback(() => {
    if (!token) return;
    api.workflows.list(token).then((w) => setWorkflows(w ?? [])).finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchWorkflows(); }, [fetchWorkflows]);

  const handleCreate = async () => {
    if (!token || !form.name || !form.slug) return;
    setCreating(true);
    try {
      await api.workflows.create(token, form);
      setForm({ name: "", slug: "", description: "", trigger_event: "" });
      setShowCreate(false);
      fetchWorkflows();
    } finally { setCreating(false); }
  };

  const handleToggle = async (wf: Workflow) => {
    if (!token) return;
    await api.workflows.update(token, wf.id, { is_enabled: !wf.is_enabled });
    fetchWorkflows();
  };

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this workflow?")) return;
    await api.workflows.delete(token, id);
    fetchWorkflows();
  };

  const filtered = workflows.filter((w) =>
    !search || w.name.toLowerCase().includes(search.toLowerCase()) || w.slug.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Workflows</h1>
          <p className="text-sm text-gray-400 mt-1">Ordered sequences of steps across agents and teams</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showCreate ? "Cancel" : "New Workflow"}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-angie-600/40">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="Name" placeholder="Email Triage" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value, slug: form.slug || e.target.value.toLowerCase().replace(/\s+/g, "-") })} />
              <Input label="Slug" placeholder="email-triage" value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })} />
            </div>
            <Input label="Description" placeholder="Triage incoming emails and route to appropriate agent" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Input label="Trigger Event" placeholder="user_message" value={form.trigger_event}
              onChange={(e) => setForm({ ...form, trigger_event: e.target.value })} />
            <Button size="sm" onClick={handleCreate} disabled={creating || !form.name || !form.slug}>
              {creating ? "Creating…" : "Create Workflow"}
            </Button>
          </div>
        </Card>
      )}

      <Input placeholder="Search workflows…" value={search} onChange={(e) => setSearch(e.target.value)} />

      <div className="grid grid-cols-2 gap-4">
        {filtered.map((wf) => (
          <Card key={wf.id} className="hover:border-angie-600/40 transition-colors group">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-600/30 flex items-center justify-center flex-shrink-0">
                  <GitBranch className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-100">{wf.name}</h3>
                  <p className="text-xs text-gray-500 font-mono">{wf.slug}</p>
                  {wf.description && <p className="text-sm text-gray-400 mt-1">{wf.description}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => handleToggle(wf)} className="cursor-pointer">
                  <Badge label={wf.is_enabled ? "enabled" : "disabled"} status={wf.is_enabled ? "success" : "cancelled"} />
                </button>
                <button onClick={() => handleDelete(wf.id)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-2 text-center py-16 text-gray-500">
            <GitBranch className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No workflows match your search." : "No workflows defined yet."}</p>
          </div>
        )}
      </div>
    </div>
  );
}
