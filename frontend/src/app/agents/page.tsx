"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Agent } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Bot } from "lucide-react";

export default function AgentsPage() {
  const { token } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!token) return;
    api.agents.list(token).then((a) => setAgents(a ?? [])).finally(() => setLoading(false));
  }, [token]);

  const filtered = agents.filter((a) =>
    !search || a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.slug.toLowerCase().includes(search.toLowerCase()) ||
    a.capabilities.some((c) => c.toLowerCase().includes(search.toLowerCase()))
  );

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Agent Fleet</h1>
        <p className="text-sm text-gray-400 mt-1">{agents.length} agents registered</p>
      </div>

      <Input placeholder="Search agents by name, slug, or capability…" value={search} onChange={(e) => setSearch(e.target.value)} />

      <div className="grid grid-cols-3 gap-4">
        {filtered.map((agent) => (
          <Card key={agent.slug} className="hover:border-angie-600/40 transition-colors">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-angie-600/20 border border-angie-600/30 flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-angie-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-gray-100 truncate">{agent.name}</h3>
                <p className="text-xs text-gray-500 font-mono">{agent.slug}</p>
                <p className="text-sm text-gray-400 mt-1 line-clamp-2">{agent.description}</p>
                {agent.capabilities.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {agent.capabilities.slice(0, 3).map((cap) => (
                      <span key={cap} className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                        {cap}
                      </span>
                    ))}
                    {agent.capabilities.length > 3 && (
                      <span className="text-xs text-gray-500">+{agent.capabilities.length - 3}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-500">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No agents match your search." : "No agents registered yet."}</p>
          </div>
        )}
      </div>
    </div>
  );
}
