"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Clock,
  GitBranch,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Plug,
  Settings,
  Users,
  Zap,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const navSections = [
  {
    label: "Main",
    items: [
      { href: "/chat",      label: "Chat",      icon: MessageSquare },
      { href: "/agents",    label: "Agents",    icon: Bot },
      { href: "/teams",     label: "Teams",     icon: Users },
    ],
  },
  {
    label: "Work",
    items: [
      { href: "/events",    label: "Events",    icon: Zap },
      { href: "/tasks",     label: "Tasks",     icon: Activity },
      { href: "/workflows", label: "Workflows", icon: GitBranch },
      { href: "/schedules", label: "Schedules", icon: Clock },
    ],
  },
  {
    label: "Configure",
    items: [
      { href: "/connections", label: "Connections", icon: Plug },
      { href: "/dashboard",  label: "History",     icon: LayoutDashboard },
      { href: "/settings",   label: "Settings",    icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-angie-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">A</span>
          </div>
          <span className="font-semibold text-gray-100">Angie</span>
          <span className="ml-auto w-2 h-2 rounded-full bg-green-400" title="Online" />
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    pathname.startsWith(href)
                      ? "bg-angie-600/20 text-angie-400 border border-angie-600/30"
                      : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
                  )}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-800">
        {user && (
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-angie-700 flex items-center justify-center text-sm font-medium text-white flex-shrink-0">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-100 truncate">{user.username}</p>
              <p className="text-xs text-gray-500 truncate">{user.email}</p>
            </div>
            <button
              onClick={logout}
              className="p-1 text-gray-500 hover:text-red-400 transition-colors"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
