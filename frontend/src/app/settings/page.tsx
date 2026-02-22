"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ChevronDown, Pencil, X } from "lucide-react";

const TIMEZONES: string[] =
  typeof Intl !== "undefined" &&
  typeof (Intl as Record<string, unknown>).supportedValuesOf === "function"
    ? Intl.supportedValuesOf("timeZone")
    : [
        "UTC",
        "Europe/London",
        "Europe/Berlin",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Australia/Sydney",
      ];

type PreferenceDef = {
  name: string;
  label: string;
  description: string;
  placeholder: string;
};

export default function SettingsPage() {
  const { user, token } = useAuth();
  const [profileForm, setProfileForm] = useState({
    full_name: "",
    timezone: "",
  });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [tzOpen, setTzOpen] = useState(false);
  const [tzSearch, setTzSearch] = useState("");

  // Preferences state
  const [prefDefs, setPrefDefs] = useState<PreferenceDef[]>([]);
  const [prefValues, setPrefValues] = useState<Record<string, string>>({});
  const [prefResetting, setPrefResetting] = useState(false);

  // Modal state
  const [editingPref, setEditingPref] = useState<PreferenceDef | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [modalSaving, setModalSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileForm({
        full_name: user.full_name ?? "",
        timezone: user.timezone ?? "UTC",
      });
    }
  }, [user]);

  const loadPreferences = useCallback(async () => {
    if (!token) return;
    try {
      const [defs, prompts] = await Promise.all([
        api.prompts.definitions(token),
        api.prompts.list(token),
      ]);
      setPrefDefs(defs);
      const vals: Record<string, string> = {};
      prompts.forEach((p) => {
        vals[p.name] = p.content;
      });
      setPrefValues(vals);
    } catch (err) {
      console.error("Failed to load preferences:", err);
    }
  }, [token]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const handleSaveProfile = async () => {
    if (!token) return;
    setProfileSaving(true);
    try {
      const updated = await api.users.updateMe(token, profileForm);
      setProfileForm({
        full_name: updated.full_name ?? "",
        timezone: updated.timezone ?? "UTC",
      });
      setProfileSaved(true);
      setTimeout(() => setProfileSaved(false), 2000);
    } finally {
      setProfileSaving(false);
    }
  };

  const openEditor = (def: PreferenceDef) => {
    setEditingPref(def);
    setEditDraft(prefValues[def.name] ?? "");
  };

  const handleApply = async () => {
    if (!token || !editingPref) return;
    setModalSaving(true);
    try {
      const content = editDraft.trim();
      if (content) {
        await api.prompts.update(token, editingPref.name, content);
        setPrefValues((v) => ({ ...v, [editingPref.name]: content }));
      } else {
        await api.prompts.delete(token, editingPref.name).catch(() => {});
        setPrefValues((v) => {
          const next = { ...v };
          delete next[editingPref.name];
          return next;
        });
      }
      setEditingPref(null);
    } catch (err) {
      console.error("Failed to save preference:", err);
    } finally {
      setModalSaving(false);
    }
  };

  const handleResetPreferences = async () => {
    if (!token) return;
    setPrefResetting(true);
    try {
      await api.prompts.reset(token);
      await loadPreferences();
    } catch (err) {
      console.error("Failed to reset preferences:", err);
    } finally {
      setPrefResetting(false);
    }
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
        <p className="mt-1 text-sm text-gray-400">
          Configure your profile and preferences
        </p>
      </div>

      <div className="flex items-start gap-6">
        <div className="min-w-0 flex-1">
          <Card>
            <CardHeader
              title="Preferences"
              subtitle="Help Angie understand you — changes apply to new chats"
            />
            <div className="space-y-2">
              {prefDefs.map((def) => (
                <button
                  key={def.name}
                  type="button"
                  onClick={() => openEditor(def)}
                  className="group flex w-full items-center justify-between rounded-lg border border-gray-700/50 bg-gray-800/30 px-3 py-2.5 text-left transition-colors hover:border-gray-600 hover:bg-gray-800/60"
                >
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-gray-200">
                      {def.description}
                    </span>
                    {prefValues[def.name] ? (
                      <p className="mt-0.5 truncate text-xs text-gray-500">
                        {prefValues[def.name]
                          .replace(/^#\s.*\n+/, "")
                          .slice(0, 80)}
                      </p>
                    ) : (
                      <p className="mt-0.5 text-xs italic text-gray-600">
                        Not configured
                      </p>
                    )}
                  </div>
                  <Pencil className="ml-3 h-4 w-4 flex-shrink-0 text-gray-500 transition-colors group-hover:text-angie-400" />
                </button>
              ))}
              <div className="pt-2">
                <Button
                  variant="secondary"
                  onClick={handleResetPreferences}
                  disabled={prefResetting}
                >
                  {prefResetting ? "Resetting…" : "Reset to defaults"}
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="w-80 flex-shrink-0">
          <Card>
            <CardHeader title="Profile" subtitle="Your account information" />
            <div className="space-y-3">
              <Input
                label="Username"
                value={user?.username ?? ""}
                readOnly
                className="opacity-60"
              />
              <Input
                label="Email"
                value={user?.email ?? ""}
                readOnly
                className="opacity-60"
              />
              <Input
                label="Full name"
                value={profileForm.full_name}
                placeholder="Your full name"
                onChange={(e) =>
                  setProfileForm({ ...profileForm, full_name: e.target.value })
                }
              />
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-300">
                  Timezone
                </label>
                <div
                  className="relative"
                  onBlur={(e) => {
                    if (!e.currentTarget.contains(e.relatedTarget))
                      setTzOpen(false);
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setTzOpen(!tzOpen);
                      setTzSearch("");
                    }}
                    className="flex w-full items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2 text-left text-sm text-gray-200 transition-colors hover:border-gray-600"
                  >
                    <span>{profileForm.timezone || "Select timezone…"}</span>
                    <ChevronDown
                      className={`h-4 w-4 text-gray-500 transition-transform ${tzOpen ? "rotate-180" : ""}`}
                    />
                  </button>
                  {tzOpen && (
                    <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
                      <div className="border-b border-gray-800 p-2">
                        <input
                          autoFocus
                          type="text"
                          placeholder="Search timezones…"
                          value={tzSearch}
                          onChange={(e) => setTzSearch(e.target.value)}
                          className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:border-angie-500 focus:outline-none"
                        />
                      </div>
                      <div className="max-h-56 overflow-y-auto">
                        {TIMEZONES.filter(
                          (tz) =>
                            !tzSearch ||
                            tz.toLowerCase().includes(tzSearch.toLowerCase())
                        ).map((tz) => (
                          <button
                            key={tz}
                            type="button"
                            onClick={() => {
                              setProfileForm({ ...profileForm, timezone: tz });
                              setTzOpen(false);
                              setTzSearch("");
                            }}
                            className={`w-full px-3 py-1.5 text-left text-sm transition-colors ${tz === profileForm.timezone ? "bg-angie-600/20 text-angie-300" : "text-gray-300 hover:bg-gray-800"}`}
                          >
                            {tz}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <Button
                variant="secondary"
                onClick={handleSaveProfile}
                disabled={profileSaving}
              >
                {profileSaved
                  ? "Saved ✓"
                  : profileSaving
                    ? "Saving…"
                    : "Save profile"}
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Edit preference modal */}
      {editingPref && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditingPref(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setEditingPref(null);
          }}
          role="dialog"
          aria-modal="true"
          aria-label={`Edit ${editingPref.label} preference`}
        >
          <div className="mx-4 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-100">
                  {editingPref.label}
                </h2>
                <p className="mt-0.5 text-sm text-gray-400">
                  {editingPref.description}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingPref(null)}
                aria-label="Close preferences editor"
                className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <textarea
                autoFocus
                rows={12}
                placeholder={editingPref.placeholder}
                value={editDraft}
                onChange={(e) => setEditDraft(e.target.value)}
                className="h-full min-h-[200px] w-full resize-y rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:border-angie-500 focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-gray-800 px-5 py-4">
              <Button variant="secondary" onClick={() => setEditingPref(null)}>
                Cancel
              </Button>
              <Button onClick={handleApply} disabled={modalSaving}>
                {modalSaving ? "Applying…" : "Apply"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
