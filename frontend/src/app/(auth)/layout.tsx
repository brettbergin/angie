"use client";

import { AuthProvider } from "@/lib/auth";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        {children}
      </div>
    </AuthProvider>
  );
}
