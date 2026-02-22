"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Team, type Agent } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Users, Plus, Trash2, X, Bot } from "lucide-react";

function TeamDetailModal({
  teamId,
  agents,
  onClose,
}: {
  teamId: string;
  agents: Agent[];
  onClose: () => void;
}) {
  const { token } = useAuth();
  const [team, setTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.teams
      .get(token, teamId)
      .then(setTeam)
      .finally(() => setLoading(false));
  }, [token, teamId]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="mx-4 flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-gray-700 bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        {loading ? (
          <div className="flex justify-center p-16">
            <Spinner className="h-8 w-8" />
          </div>
        ) : team ? (
          <>
            <div className="flex items-start justify-between border-b border-gray-800 p-6">
              <div className="flex items-start gap-3">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg border border-purple-600/30 bg-purple-600/20">
                  <Users className="h-6 w-6 text-purple-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-100">
                    {team.name}
                  </h2>
                  <p className="font-mono text-sm text-gray-500">
                    @{team.slug}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1 text-gray-500 hover:text-gray-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-6">
              {team.description && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Description
                  </h3>
                  <p className="text-sm text-gray-300">{team.description}</p>
                </div>
              )}

              {team.goal && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Goal
                  </h3>
                  <p className="text-sm text-gray-300">{team.goal}</p>
                </div>
              )}

              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Member Agents — {team.agent_slugs.length} agent
                  {team.agent_slugs.length !== 1 ? "s" : ""}
                </h3>
                {team.agent_slugs.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                    {team.agent_slugs.map((slug) => {
                      const agent = agents.find((a) => a.slug === slug);
                      return (
                        <div
                          key={slug}
                          className="flex flex-col items-center gap-2 rounded-lg border border-angie-600/30 bg-angie-600/5 p-3"
                        >
                          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-angie-600/30 bg-angie-600/20">
                            <Bot className="h-5 w-5 text-angie-400" />
                          </div>
                          <div className="w-full min-w-0 text-center">
                            <p className="truncate text-sm font-medium text-gray-200">
                              {agent?.name ?? slug}
                            </p>
                            <p className="truncate font-mono text-xs text-gray-500">
                              {slug}
                            </p>
                            {agent?.description && (
                              <p className="mt-1 line-clamp-2 text-xs text-gray-400">
                                {agent.description}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm italic text-gray-500">
                    No agents assigned to this team.
                  </p>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="p-16 text-center text-gray-500">Team not found.</div>
        )}
      </div>
    </div>
  );
}

export default function TeamsPage() {
  const { token } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    slug: "",
    description: "",
    goal: "",
  });
  const [selectedSlugs, setSelectedSlugs] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [agentSearch, setAgentSearch] = useState("");
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setAgentDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchTeams = useCallback(() => {
    if (!token) return;
    api.teams
      .list(token)
      .then((t) => setTeams(t ?? []))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    fetchTeams();
    api.agents.list(token).then((a) => setAgents(a ?? []));
  }, [token, fetchTeams]);

  const toggleAgent = (slug: string) => {
    setSelectedSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const handleCreate = async () => {
    if (!token || !form.name || !form.slug) return;
    setCreating(true);
    try {
      await api.teams.create(token, { ...form, agent_slugs: selectedSlugs });
      setForm({ name: "", slug: "", description: "", goal: "" });
      setSelectedSlugs([]);
      setShowCreate(false);
      fetchTeams();
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this team?")) return;
    try {
      await api.teams.delete(token, id);
      setTeams((prev) => prev.filter((t) => t.id !== id));
    } catch {
      fetchTeams();
    }
  };

  const handleToggleEnabled = async (team: Team, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;
    try {
      const updated = await api.teams.update(token, team.id, {
        is_enabled: !team.is_enabled,
      });
      setTeams((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch {
      fetchTeams();
    }
  };

  const filtered = teams.filter(
    (t) =>
      !search ||
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase())
  );

  const filteredAgents = agents.filter(
    (a) =>
      !agentSearch ||
      a.name.toLowerCase().includes(agentSearch.toLowerCase()) ||
      a.slug.toLowerCase().includes(agentSearch.toLowerCase())
  );

  if (loading)
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Teams</h1>
          <p className="mt-1 text-sm text-gray-400">
            Groups of agents that collaborate on workflows
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setShowCreate(!showCreate);
            if (showCreate) {
              setSelectedSlugs([]);
              setAgentSearch("");
              setAgentDropdownOpen(false);
            }
          }}
        >
          {showCreate ? (
            <X className="h-4 w-4" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {showCreate ? "Cancel" : "New Team"}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-angie-600/40">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Name"
                placeholder="Email Team"
                value={form.name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    name: e.target.value,
                    slug:
                      form.slug ||
                      e.target.value.toLowerCase().replace(/\s+/g, "-"),
                  })
                }
              />
              <Input
                label="Slug"
                placeholder="email-team"
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })}
              />
            </div>
            <Input
              label="Description"
              placeholder="Agents that handle email operations"
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
            <Input
              label="Goal"
              placeholder="Manage all email-related tasks"
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
            />

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Add Agents
              </label>
              <div className="relative" ref={dropdownRef}>
                <Input
                  placeholder="Click to browse or type to search agents…"
                  value={agentSearch}
                  onFocus={() => setAgentDropdownOpen(true)}
                  onChange={(e) => {
                    setAgentSearch(e.target.value);
                    setAgentDropdownOpen(true);
                  }}
                />
                {agentDropdownOpen && (
                  <div className="absolute z-10 mt-1 max-h-48 w-full divide-y divide-gray-800 overflow-y-auto rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
                    {filteredAgents
                      .filter((a) => !selectedSlugs.includes(a.slug))
                      .map((agent) => (
                        <button
                          key={agent.slug}
                          type="button"
                          onClick={() => {
                            toggleAgent(agent.slug);
                            setAgentSearch("");
                            setAgentDropdownOpen(false);
                          }}
                          className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-gray-800/50"
                        >
                          <Plus className="h-4 w-4 flex-shrink-0 text-angie-400" />
                          <Bot className="h-4 w-4 flex-shrink-0 text-gray-500" />
                          <div className="min-w-0">
                            <span className="text-sm text-gray-200">
                              {agent.name}
                            </span>
                            <span className="ml-2 font-mono text-xs text-gray-500">
                              {agent.slug}
                            </span>
                          </div>
                        </button>
                      ))}
                    {filteredAgents.filter(
                      (a) => !selectedSlugs.includes(a.slug)
                    ).length === 0 && (
                      <div className="px-3 py-4 text-center text-sm text-gray-500">
                        No agents match
                      </div>
                    )}
                  </div>
                )}
              </div>

              {selectedSlugs.length > 0 && (
                <div className="mt-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Team Roster — {selectedSlugs.length} agent
                    {selectedSlugs.length !== 1 ? "s" : ""}
                  </p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                    {selectedSlugs.map((slug) => {
                      const agent = agents.find((a) => a.slug === slug);
                      if (!agent) return null;
                      return (
                        <div
                          key={slug}
                          className="group/card relative flex flex-col items-center gap-2 rounded-lg border border-angie-600/30 bg-angie-600/5 p-3 transition-colors hover:border-angie-500/50"
                        >
                          <button
                            type="button"
                            onClick={() => toggleAgent(slug)}
                            className="absolute right-1.5 top-1.5 rounded p-1 text-gray-500 opacity-0 transition-all hover:bg-red-600/20 hover:text-red-400 group-hover/card:opacity-100"
                            title="Remove from team"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-angie-600/30 bg-angie-600/20">
                            <Bot className="h-5 w-5 text-angie-400" />
                          </div>
                          <div className="w-full min-w-0 text-center">
                            <p className="truncate text-sm font-medium text-gray-200">
                              {agent.name}
                            </p>
                            <p className="truncate font-mono text-xs text-gray-500">
                              {agent.slug}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <Button
              size="sm"
              onClick={handleCreate}
              disabled={creating || !form.name || !form.slug}
            >
              {creating ? "Creating…" : "Create Team"}
            </Button>
          </div>
        </Card>
      )}

      <Input
        placeholder="Search teams…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="grid grid-cols-3 gap-4">
        {filtered.map((team) => (
          <Card
            key={team.id}
            className={cn(
              "group cursor-pointer transition-colors hover:border-angie-600/40",
              !team.is_enabled && "opacity-50"
            )}
            onClick={() => setSelectedTeamId(team.id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-purple-600/30 bg-purple-600/20">
                  <Users className="h-5 w-5 text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-100">{team.name}</h3>
                  <p className="font-mono text-xs text-gray-500">{team.slug}</p>
                  {team.description && (
                    <p className="mt-1 text-sm text-gray-400">
                      {team.description}
                    </p>
                  )}
                  {team.agent_slugs?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {team.agent_slugs.map((slug) => (
                        <span
                          key={slug}
                          className="flex items-center gap-1 rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400"
                        >
                          <Bot className="h-3 w-3" />
                          {slug}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => handleToggleEnabled(team, e)}
                  className={cn(
                    "relative h-5 w-9 flex-shrink-0 rounded-full transition-colors",
                    team.is_enabled ? "bg-green-500" : "bg-gray-600"
                  )}
                  title={team.is_enabled ? "Disable team" : "Enable team"}
                >
                  <span
                    className={cn(
                      "absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
                      team.is_enabled && "translate-x-4"
                    )}
                  />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(team.id);
                  }}
                  className="rounded-lg p-1.5 text-gray-500 opacity-0 transition-all hover:bg-red-600/20 hover:text-red-400 group-hover:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-3 py-16 text-center text-gray-500">
            <Users className="mx-auto mb-3 h-12 w-12 opacity-30" />
            <p>
              {search ? "No teams match your search." : "No teams created yet."}
            </p>
          </div>
        )}
      </div>

      {selectedTeamId && (
        <TeamDetailModal
          teamId={selectedTeamId}
          agents={agents}
          onClose={() => setSelectedTeamId(null)}
        />
      )}
    </div>
  );
}
