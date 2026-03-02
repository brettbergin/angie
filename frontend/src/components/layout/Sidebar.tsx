"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Clock,
  GitBranch,
  History,
  LogOut,
  MessageSquare,
  Plug,
  Settings,
  Users,
  Zap,
  Activity,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const navSections = [
  {
    label: "Main",
    items: [
      { href: "/chat", label: "Chat", icon: MessageSquare },
      { href: "/agents", label: "Agents", icon: Bot },
      { href: "/teams", label: "Teams", icon: Users },
    ],
  },
  {
    label: "Work",
    items: [
      { href: "/events", label: "Events", icon: Zap },
      { href: "/tasks", label: "Tasks", icon: Activity },
      { href: "/workflows", label: "Workflows", icon: GitBranch },
      { href: "/schedules", label: "Schedules", icon: Clock },
    ],
  },
  {
    label: "Configure",
    items: [
      { href: "/connections", label: "Connections", icon: Plug },
      { href: "/usage", label: "Usage", icon: BarChart3 },
      { href: "/history", label: "History", icon: History },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-col border-r border-gray-800 bg-gray-900">
      {/* Logo */}
      <div className="border-b border-gray-800 px-6 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-angie-600">
            <span className="text-sm font-bold text-white">A</span>
          </div>
          <span className="font-semibold text-gray-100">Angie</span>
          <span
            className="ml-auto h-2 w-2 rounded-full bg-green-400"
            title="Online"
          />
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    pathname.startsWith(href)
                      ? "border border-angie-600/30 bg-angie-600/20 text-angie-400"
                      : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
                  )}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  {label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-gray-800 px-3 py-4">
        {user && (
          <div className="flex items-center gap-3 rounded-lg px-3 py-2">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-angie-700 text-sm font-medium text-white">
              {user.username[0].toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-100">
                {user.username}
              </p>
              <p className="truncate text-xs text-gray-500">{user.email}</p>
            </div>
            <button
              onClick={logout}
              className="p-1 text-gray-500 transition-colors hover:text-red-400"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
