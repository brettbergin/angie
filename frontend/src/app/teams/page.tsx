"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Team } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Users, Plus, Trash2, X } from "lucide-react";

export default function TeamsPage() {
  const { token } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "", goal: "" });
  const [search, setSearch] = useState("");

  const fetchTeams = () => {
    if (!token) return;
    api.teams.list(token).then((t) => setTeams(t ?? [])).finally(() => setLoading(false));
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchTeams(); }, [token]);

  const handleCreate = async () => {
    if (!token || !form.name || !form.slug) return;
    setCreating(true);
    try {
      await api.teams.create(token, form);
      setForm({ name: "", slug: "", description: "", goal: "" });
      setShowCreate(false);
      fetchTeams();
    } finally { setCreating(false); }
  };

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this team?")) return;
    await api.teams.delete(token, id);
    fetchTeams();
  };

  const filtered = teams.filter((t) =>
    !search || t.name.toLowerCase().includes(search.toLowerCase()) || t.slug.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Teams</h1>
          <p className="text-sm text-gray-400 mt-1">Groups of agents that collaborate on workflows</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showCreate ? "Cancel" : "New Team"}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-angie-600/40">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="Name" placeholder="Email Team" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value, slug: form.slug || e.target.value.toLowerCase().replace(/\s+/g, "-") })} />
              <Input label="Slug" placeholder="email-team" value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })} />
            </div>
            <Input label="Description" placeholder="Agents that handle email operations" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Input label="Goal" placeholder="Manage all email-related tasks" value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })} />
            <Button size="sm" onClick={handleCreate} disabled={creating || !form.name || !form.slug}>
              {creating ? "Creating…" : "Create Team"}
            </Button>
          </div>
        </Card>
      )}

      <Input placeholder="Search teams…" value={search} onChange={(e) => setSearch(e.target.value)} />

      <div className="grid grid-cols-3 gap-4">
        {filtered.map((team) => (
          <Card key={team.id} className="hover:border-angie-600/40 transition-colors group">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-600/20 border border-purple-600/30 flex items-center justify-center flex-shrink-0">
                  <Users className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-100">{team.name}</h3>
                  <p className="text-xs text-gray-500 font-mono">{team.slug}</p>
                  {team.description && <p className="text-sm text-gray-400 mt-1">{team.description}</p>}
                </div>
              </div>
              <button onClick={() => handleDelete(team.id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-all">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No teams match your search." : "No teams created yet."}</p>
          </div>
        )}
      </div>
    </div>
  );
}
