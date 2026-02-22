"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Agent, type AgentDetail } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Bot, X, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_ORDER = [
  "System Agents",
  "Communication Agents",
  "Smart Home Agents",
  "Social Agents",
  "Planning Agents",
  "Media Agents",
];

function AgentDetailModal({
  slug,
  onClose,
}: {
  slug: string;
  onClose: () => void;
}) {
  const { token } = useAuth();
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.agents
      .get(token, slug)
      .then(setAgent)
      .finally(() => setLoading(false));
  }, [token, slug]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const copyPrompt = () => {
    if (!agent) return;
    navigator.clipboard.writeText(agent.instructions);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
        ) : agent ? (
          <>
            <div className="flex items-start justify-between border-b border-gray-800 p-6">
              <div className="flex items-start gap-3">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg border border-angie-600/30 bg-angie-600/20">
                  <Bot className="h-6 w-6 text-angie-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-100">
                    {agent.name}
                  </h2>
                  <p className="font-mono text-sm text-gray-500">
                    {agent.slug}
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
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Description
                </h3>
                <p className="text-sm text-gray-300">{agent.description}</p>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Capabilities
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {agent.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-300"
                    >
                      {cap}
                    </span>
                  ))}
                  {agent.capabilities.length === 0 && (
                    <p className="text-sm italic text-gray-500">
                      No capabilities declared.
                    </p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Module Path
                </h3>
                <p className="font-mono text-sm text-gray-400">
                  {agent.module_path}
                </p>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Instructions
                  </h3>
                  <button
                    onClick={copyPrompt}
                    className="flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-gray-300"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-lg border border-gray-800 bg-gray-950 p-4 font-mono text-sm leading-relaxed text-gray-300">
                  {agent.instructions}
                </pre>
              </div>

              <div>
                <button
                  onClick={() => setShowSystemPrompt(!showSystemPrompt)}
                  className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-gray-500 transition-colors hover:text-gray-300"
                >
                  <span
                    className={cn(
                      "transition-transform",
                      showSystemPrompt ? "rotate-90" : ""
                    )}
                  >
                    ▶
                  </span>
                  Full System Prompt
                </button>
                {showSystemPrompt && (
                  <pre className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg border border-gray-800 bg-gray-950 p-4 font-mono text-sm leading-relaxed text-gray-400">
                    {agent.system_prompt}
                  </pre>
                )}
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
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set()
  );

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  const selectAll = () => setSelectedCategories(new Set());

  useEffect(() => {
    if (!token) return;
    api.agents
      .list(token)
      .then((a) => setAgents(a ?? []))
      .finally(() => setLoading(false));
  }, [token]);

  const filtered = agents.filter(
    (a) =>
      !search ||
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.slug.toLowerCase().includes(search.toLowerCase()) ||
      a.capabilities.some((c) => c.toLowerCase().includes(search.toLowerCase()))
  );

  const grouped = useMemo(() => {
    const groups: Record<string, Agent[]> = {};
    for (const agent of filtered) {
      const cat = agent.category || "General";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(agent);
    }
    const ordered = CATEGORY_ORDER.filter((c) => groups[c]);
    const remaining = Object.keys(groups)
      .filter((c) => !CATEGORY_ORDER.includes(c))
      .sort();
    return [...ordered, ...remaining].map((cat) => ({
      category: cat,
      agents: groups[cat],
    }));
  }, [filtered]);

  const visibleGroups =
    selectedCategories.size > 0
      ? grouped.filter(({ category }) => selectedCategories.has(category))
      : grouped;

  const categoryLabel = (cat: string) => cat.replace(/ Agents$/i, "");

  const categoryId = (cat: string) =>
    cat
      .toLowerCase()
      .trim()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");

  if (loading)
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Agent Fleet</h1>
        <p className="mt-1 text-sm text-gray-400">
          {agents.length} agents registered
        </p>
      </div>

      <Input
        placeholder="Search agents by name, slug, or capability…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {grouped.length > 1 && (
        <nav className="sticky top-0 z-10 -mx-8 flex gap-2 overflow-x-auto bg-gray-950/80 px-8 py-2 pb-1 backdrop-blur-sm">
          <button
            type="button"
            onClick={selectAll}
            aria-pressed={selectedCategories.size === 0}
            className={cn(
              "whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              selectedCategories.size === 0
                ? "border-angie-500 bg-angie-500/10 text-angie-300"
                : "border-gray-700 text-gray-400 hover:border-angie-600/40 hover:text-angie-400"
            )}
          >
            All
          </button>
          {grouped.map(({ category }) => (
            <button
              type="button"
              key={category}
              onClick={() => toggleCategory(category)}
              aria-pressed={selectedCategories.has(category)}
              className={cn(
                "whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                selectedCategories.has(category)
                  ? "border-angie-500 bg-angie-500/10 text-angie-300"
                  : "border-gray-700 text-gray-400 hover:border-angie-600/40 hover:text-angie-400"
              )}
            >
              {categoryLabel(category)}
            </button>
          ))}
        </nav>
      )}

      {visibleGroups.map(({ category, agents: catAgents }) => (
        <section
          key={category}
          id={categoryId(category)}
          className="scroll-mt-20"
        >
          <h2 className="mb-3 border-b border-gray-800 pb-2 text-lg font-semibold text-gray-200">
            {category}
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {catAgents.map((agent) => (
              <Card
                key={agent.slug}
                className="cursor-pointer transition-colors hover:border-angie-600/40"
                onClick={() => setSelectedSlug(agent.slug)}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-angie-600/30 bg-angie-600/20">
                    <Bot className="h-5 w-5 text-angie-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate font-semibold text-gray-100">
                      {agent.name}
                    </h3>
                    <p className="font-mono text-xs text-gray-500">
                      {agent.slug}
                    </p>
                    <p className="mt-1 line-clamp-2 text-sm text-gray-400">
                      {agent.description}
                    </p>
                    {agent.capabilities.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {agent.capabilities.slice(0, 3).map((cap) => (
                          <span
                            key={cap}
                            className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400"
                          >
                            {cap}
                          </span>
                        ))}
                        {agent.capabilities.length > 3 && (
                          <span className="text-xs text-gray-500">
                            +{agent.capabilities.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}

      {visibleGroups.length === 0 && (
        <div className="py-16 text-center text-gray-500">
          <Bot className="mx-auto mb-3 h-12 w-12 opacity-30" />
          <p>
            {search
              ? "No agents match your search."
              : "No agents registered yet."}
          </p>
        </div>
      )}

      {selectedSlug && (
        <AgentDetailModal
          slug={selectedSlug}
          onClose={() => setSelectedSlug(null)}
        />
      )}
    </div>
  );
}
