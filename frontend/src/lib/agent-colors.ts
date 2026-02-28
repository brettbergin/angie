/**
 * Unique color identity for each agent in the chat UI.
 *
 * User messages stay purple (angie brand), orchestrator messages stay gray,
 * and each agent gets a distinct color so task results are instantly attributable.
 */

import type { ComponentType } from "react";
import { GitHubLogo } from "@/components/icons/GitHubLogo";

export type AgentColor = {
  /** Tailwind bg class for the avatar circle */
  avatarBg: string;
  /** Tailwind border class for the bubble */
  borderClass: string;
  /** Tailwind bg class for the bubble */
  bgClass: string;
  /** Tailwind text class for the label */
  labelClass: string;
  /** Single-char initial for the avatar */
  initial: string;
  /** Tailwind border + text classes for welcome-screen chips */
  chipBorder: string;
  chipText: string;
  /** Optional icon component to render instead of the text initial */
  icon?: ComponentType<{ className?: string }>;
};

const AGENT_COLORS: Record<string, AgentColor> = {
  cron: {
    avatarBg: "bg-amber-600",
    borderClass: "border-amber-700/40",
    bgClass: "bg-amber-900/30",
    labelClass: "text-amber-400",
    initial: "C",
    chipBorder: "border-amber-700/50",
    chipText: "text-amber-400",
  },
  "task-manager": {
    avatarBg: "bg-cyan-600",
    borderClass: "border-cyan-700/40",
    bgClass: "bg-cyan-900/30",
    labelClass: "text-cyan-400",
    initial: "T",
    chipBorder: "border-cyan-700/50",
    chipText: "text-cyan-400",
  },
  "workflow-manager": {
    avatarBg: "bg-indigo-600",
    borderClass: "border-indigo-700/40",
    bgClass: "bg-indigo-900/30",
    labelClass: "text-indigo-400",
    initial: "W",
    chipBorder: "border-indigo-700/50",
    chipText: "text-indigo-400",
  },
  "event-manager": {
    avatarBg: "bg-rose-600",
    borderClass: "border-rose-700/40",
    bgClass: "bg-rose-900/30",
    labelClass: "text-rose-400",
    initial: "E",
    chipBorder: "border-rose-700/50",
    chipText: "text-rose-400",
  },
  github: {
    avatarBg: "bg-green-600",
    borderClass: "border-green-700/40",
    bgClass: "bg-green-900/30",
    labelClass: "text-green-400",
    initial: "G",
    chipBorder: "border-green-700/50",
    chipText: "text-green-400",
    icon: GitHubLogo,
  },
  "software-dev": {
    avatarBg: "bg-orange-600",
    borderClass: "border-orange-700/40",
    bgClass: "bg-orange-900/30",
    labelClass: "text-orange-400",
    initial: "S",
    chipBorder: "border-orange-700/50",
    chipText: "text-orange-400",
  },
  web: {
    avatarBg: "bg-sky-600",
    borderClass: "border-sky-700/40",
    bgClass: "bg-sky-900/30",
    labelClass: "text-sky-400",
    initial: "W",
    chipBorder: "border-sky-700/50",
    chipText: "text-sky-400",
  },
  weather: {
    avatarBg: "bg-teal-600",
    borderClass: "border-teal-700/40",
    bgClass: "bg-teal-900/30",
    labelClass: "text-teal-400",
    initial: "W",
    chipBorder: "border-teal-700/50",
    chipText: "text-teal-400",
  },
};

/** Emerald fallback — preserves current behavior for unknown agents */
const FALLBACK: AgentColor = {
  avatarBg: "bg-emerald-600",
  borderClass: "border-emerald-700/40",
  bgClass: "bg-emerald-900/30",
  labelClass: "text-emerald-400",
  initial: "A",
  chipBorder: "border-emerald-700/50",
  chipText: "text-emerald-400",
};

/** Get agent color config by slug, with emerald fallback. */
export function getAgentColor(slug?: string | null): AgentColor {
  if (!slug) return FALLBACK;
  return AGENT_COLORS[slug] ?? FALLBACK;
}

export { AGENT_COLORS };
