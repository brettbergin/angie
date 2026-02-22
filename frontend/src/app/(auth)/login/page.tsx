"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.username, form.password);
      router.replace("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="text-center mb-8">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/angie-logo.svg"
          alt="Angie logo"
          width={160}
          height={192}
          className="mx-auto mb-4"
        />
        <h1 className="text-2xl font-bold text-gray-100">Sign in to Angie</h1>
        <p className="text-sm text-gray-400 mt-1">Your personal AI assistant</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Username"
          placeholder="your-username"
          value={form.username}
          onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
          required
          autoFocus
        />
        <Input
          label="Password"
          type="password"
          placeholder="••••••••"
          value={form.password}
          onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
          required
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading && <Spinner className="w-4 h-4" />}
          Sign in
        </Button>
      </form>

      <p className="text-center text-sm text-gray-400 mt-6">
        No account?{" "}
        <Link href="/register" className="text-angie-400 hover:underline">
          Register
        </Link>
      </p>
    </div>
  );
}
