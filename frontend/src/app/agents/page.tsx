"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Agent, type AgentDetail } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Bot, X, Copy, Check } from "lucide-react";

function AgentDetailModal({ slug, onClose }: { slug: string; onClose: () => void }) {
  const { token } = useAuth();
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.agents.get(token, slug).then(setAgent).finally(() => setLoading(false));
  }, [token, slug]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const copyPrompt = () => {
    if (!agent) return;
    navigator.clipboard.writeText(agent.system_prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        {loading ? (
          <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>
        ) : agent ? (
          <>
            <div className="flex items-start justify-between p-6 border-b border-gray-800">
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-lg bg-angie-600/20 border border-angie-600/30 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-6 h-6 text-angie-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-100">{agent.name}</h2>
                  <p className="text-sm text-gray-500 font-mono">{agent.slug}</p>
                </div>
              </div>
              <button onClick={onClose} className="text-gray-500 hover:text-gray-300 p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto p-6 space-y-5 flex-1">
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Description</h3>
                <p className="text-sm text-gray-300">{agent.description}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Capabilities</h3>
                <div className="flex flex-wrap gap-1.5">
                  {agent.capabilities.map((cap) => (
                    <span key={cap} className="text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded border border-gray-700">{cap}</span>
                  ))}
                  {agent.capabilities.length === 0 && <p className="text-sm text-gray-500 italic">No capabilities declared.</p>}
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Module Path</h3>
                <p className="text-sm text-gray-400 font-mono">{agent.module_path}</p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Instructions</h3>
                  <button onClick={copyPrompt} className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors">
                    {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="text-sm text-gray-300 bg-gray-950 border border-gray-800 rounded-lg p-4 whitespace-pre-wrap font-mono leading-relaxed max-h-64 overflow-y-auto">
                  {agent.system_prompt || "No instructions configured."}
                </pre>
              </div>
            </div>
          </>
        ) : (
          <div className="p-16 text-center text-gray-500">Agent not found.</div>
        )}
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { token } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

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
          <Card key={agent.slug} className="hover:border-angie-600/40 transition-colors cursor-pointer" onClick={() => setSelectedSlug(agent.slug)}>
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

      {selectedSlug && <AgentDetailModal slug={selectedSlug} onClose={() => setSelectedSlug(null)} />}
    </div>
  );
}
