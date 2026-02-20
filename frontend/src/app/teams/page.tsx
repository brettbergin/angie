"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Team } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Users } from "lucide-react";

export default function TeamsPage() {
  const { token } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.teams.list(token).then((t) => setTeams(t ?? [])).finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="flex justify-center p-16"><Spinner className="w-8 h-8" /></div>;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Teams</h1>
        <p className="text-sm text-gray-400 mt-1">Groups of agents that collaborate on workflows</p>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {teams.map((team) => (
          <Card key={team.id} className="hover:border-angie-600/40 transition-colors">
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
          </Card>
        ))}
        {teams.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No teams created yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
