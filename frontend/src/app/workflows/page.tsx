"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Workflow } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { GitBranch } from "lucide-react";

export default function WorkflowsPage() {
  const { token } = useAuth();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.workflows.list(token).then((w) => setWorkflows(w ?? [])).finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Workflows</h1>
        <p className="text-sm text-gray-400 mt-1">Ordered sequences of steps across agents and teams</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {workflows.map((wf) => (
          <Card key={wf.id} className="hover:border-angie-600/40 transition-colors">
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
              <Badge label={wf.is_enabled ? "enabled" : "disabled"} status={wf.is_enabled ? "success" : "cancelled"} />
            </div>
          </Card>
        ))}
        {workflows.length === 0 && (
          <div className="col-span-2 text-center py-16 text-gray-500">
            <GitBranch className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No workflows defined yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
