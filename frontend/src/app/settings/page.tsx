"use client";

import { useAuth } from "@/lib/auth";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const CHANNELS = [
  { key: "slack", label: "Slack", placeholder: "xoxb-..." },
  { key: "discord", label: "Discord", placeholder: "Bot token" },
  { key: "imessage", label: "iMessage (BlueBubbles)", placeholder: "http://localhost:1234" },
  { key: "email", label: "Email (SMTP host)", placeholder: "smtp.gmail.com" },
];

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="p-8 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
        <p className="text-sm text-gray-400 mt-1">Configure Angie&apos;s channels, prompts, and profile</p>
      </div>

      <Card>
        <CardHeader title="Profile" subtitle="Your account information" />
        <div className="space-y-3">
          <Input label="Username" value={user?.username ?? ""} readOnly className="opacity-60" />
          <Input label="Email" value={user?.email ?? ""} readOnly className="opacity-60" />
          <Input label="Full name" defaultValue={user?.full_name ?? ""} placeholder="Your full name" />
          <Input label="Timezone" defaultValue={user?.timezone ?? "UTC"} placeholder="America/New_York" />
          <Button variant="secondary">Save profile</Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Communication Channels" subtitle="Configure where Angie can reach you" />
        <div className="space-y-4">
          {CHANNELS.map(({ key, label, placeholder }) => (
            <div key={key} className="space-y-1">
              <Input label={label} placeholder={placeholder} type="password" />
            </div>
          ))}
          <Button variant="secondary">Save channels</Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Prompt Management" subtitle="Manage how Angie understands you" />
        <div className="space-y-3">
          <p className="text-sm text-gray-400">
            User prompts are generated from the onboarding process and stored as markdown files.
            Use the CLI to reconfigure:
          </p>
          <div className="bg-gray-950 rounded-lg p-3 font-mono text-sm text-gray-300 space-y-1">
            <p><span className="text-angie-400">$</span> angie prompts list</p>
            <p><span className="text-angie-400">$</span> angie prompts edit</p>
            <p><span className="text-angie-400">$</span> angie prompts reset</p>
            <p><span className="text-angie-400">$</span> angie setup  <span className="text-gray-600"># re-run onboarding</span></p>
          </div>
        </div>
      </Card>
    </div>
  );
}
