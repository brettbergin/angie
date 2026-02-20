"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Agent } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Bot } from "lucide-react";

export default function AgentsPage() {
  const { token } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.agents.list(token).then((a) => setAgents(a ?? [])).finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Agent Fleet</h1>
        <p className="text-sm text-gray-400 mt-1">{agents.length} agents registered</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {agents.map((agent) => (
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
        {agents.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-500">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No agents registered yet.</p>
            <p className="text-sm mt-1">Run <code className="bg-gray-800 px-1 rounded">angie setup</code> to onboard Angie.</p>
          </div>
        )}
      </div>
    </div>
  );
}
