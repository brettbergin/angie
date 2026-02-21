"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type ChannelConfig } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";

const TIMEZONES = Intl.supportedValuesOf("timeZone");

const CHANNELS = [
  { key: "slack", label: "Slack", field: "token", placeholder: "xoxb-..." },
  { key: "discord", label: "Discord", field: "token", placeholder: "Bot token" },
  { key: "imessage", label: "iMessage (BlueBubbles)", field: "url", placeholder: "http://localhost:1234" },
  { key: "email", label: "Email (SMTP host)", field: "smtp_host", placeholder: "smtp.gmail.com" },
];

export default function SettingsPage() {
  const { user, token, refreshUser } = useAuth();
  const [channelValues, setChannelValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [profileForm, setProfileForm] = useState({ full_name: "", timezone: "" });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [tzOpen, setTzOpen] = useState(false);
  const [tzSearch, setTzSearch] = useState("");

  useEffect(() => {
    if (user) {
      setProfileForm({ full_name: user.full_name ?? "", timezone: user.timezone ?? "UTC" });
    }
  }, [user]);

  useEffect(() => {
    if (!token) return;
    api.channels.list(token).then((configs: ChannelConfig[]) => {
      const vals: Record<string, string> = {};
      configs.forEach((c) => {
        const ch = CHANNELS.find((ch) => ch.key === c.type);
        if (ch) vals[c.type] = (c.config as Record<string, string>)[ch.field] ?? "";
      });
      setChannelValues(vals);
    });
  }, [token]);

  const handleSaveProfile = async () => {
    if (!token) return;
    setProfileSaving(true);
    try {
      await api.users.updateMe(token, profileForm);
      if (refreshUser) refreshUser();
      setProfileSaved(true);
      setTimeout(() => setProfileSaved(false), 2000);
    } finally { setProfileSaving(false); }
  };

  const handleSaveChannels = async () => {
    if (!token) return;
    setSaving(true);
    try {
      await Promise.all(
        CHANNELS.map((ch) =>
          api.channels.upsert(token, ch.key, {
            is_enabled: !!channelValues[ch.key],
            config: { [ch.field]: channelValues[ch.key] ?? "" },
          }),
        ),
      );
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

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
          <Input label="Full name" value={profileForm.full_name} placeholder="Your full name"
            onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })} />
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Timezone</label>
            <div className="relative" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setTzOpen(false); }}>
              <button type="button" onClick={() => { setTzOpen(!tzOpen); setTzSearch(""); }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-gray-700 bg-gray-800/50 text-sm text-gray-200 hover:border-gray-600 transition-colors text-left">
                <span>{profileForm.timezone || "Select timezone…"}</span>
                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${tzOpen ? "rotate-180" : ""}`} />
              </button>
              {tzOpen && (
                <div className="absolute z-20 w-full mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
                  <div className="p-2 border-b border-gray-800">
                    <input autoFocus type="text" placeholder="Search timezones…" value={tzSearch}
                      onChange={(e) => setTzSearch(e.target.value)}
                      className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-angie-500" />
                  </div>
                  <div className="max-h-56 overflow-y-auto">
                    {TIMEZONES.filter((tz) => !tzSearch || tz.toLowerCase().includes(tzSearch.toLowerCase())).map((tz) => (
                      <button key={tz} type="button"
                        onClick={() => { setProfileForm({ ...profileForm, timezone: tz }); setTzOpen(false); setTzSearch(""); }}
                        className={`w-full text-left px-3 py-1.5 text-sm transition-colors ${tz === profileForm.timezone ? "bg-angie-600/20 text-angie-300" : "text-gray-300 hover:bg-gray-800"}`}>
                        {tz}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
          <Button variant="secondary" onClick={handleSaveProfile} disabled={profileSaving}>
            {profileSaved ? "Saved ✓" : profileSaving ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Communication Channels" subtitle="Configure where Angie can reach you" />
        <div className="space-y-4">
          {CHANNELS.map(({ key, label, placeholder }) => (
            <div key={key} className="space-y-1">
              <Input
                label={label}
                placeholder={placeholder}
                type="password"
                value={channelValues[key] ?? ""}
                onChange={(e) => setChannelValues((v) => ({ ...v, [key]: e.target.value }))}
              />
            </div>
          ))}
          <Button variant="secondary" onClick={handleSaveChannels} disabled={saving}>
            {saved ? "Saved ✓" : saving ? "Saving…" : "Save channels"}
          </Button>
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
