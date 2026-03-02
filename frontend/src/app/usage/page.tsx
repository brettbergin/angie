"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/lib/auth";
import {
  api,
  type UsageSummary,
  type DailyUsage,
  type UsageTotals,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { BarChart3 } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

type RangeOption = {
  label: string;
  granularity: "15min" | "30min" | "1h" | "1d";
  getRange: () => { start_date: string; end_date: string };
};

const RANGE_OPTIONS: RangeOption[] = [
  {
    label: "15m",
    granularity: "15min",
    getRange: () => {
      const end = new Date();
      const start = new Date(end.getTime() - 15 * 60 * 1000);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
  {
    label: "30m",
    granularity: "30min",
    getRange: () => {
      const end = new Date();
      const start = new Date(end.getTime() - 30 * 60 * 1000);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
  {
    label: "1h",
    granularity: "1h",
    getRange: () => {
      const end = new Date();
      const start = new Date(end.getTime() - 60 * 60 * 1000);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
  {
    label: "7d",
    granularity: "1d",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 7);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
  {
    label: "30d",
    granularity: "1d",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 30);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
  {
    label: "90d",
    granularity: "1d",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 90);
      return { start_date: start.toISOString(), end_date: end.toISOString() };
    },
  },
];

const DEFAULT_RANGE_INDEX = 4; // 30d

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

type GroupBy = "agent" | "model";

type AggregatedRow = {
  key: string;
  sublabel: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  request_count: number;
};

export default function UsagePage() {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [selectedRange, setSelectedRange] = useState(DEFAULT_RANGE_INDEX);
  const [groupBy, setGroupBy] = useState<GroupBy>("agent");
  const [totals, setTotals] = useState<UsageTotals | null>(null);
  const [daily, setDaily] = useState<DailyUsage[]>([]);
  const [summary, setSummary] = useState<UsageSummary[]>([]);

  const rangeOpt = RANGE_OPTIONS[selectedRange];
  const isSubDay = rangeOpt.granularity !== "1d";

  const fetchData = useCallback(async (t: string, idx: number) => {
    const opt = RANGE_OPTIONS[idx];
    const params = opt.getRange();
    const [totalsData, dailyData, summaryData] = await Promise.all([
      api.usage.totals(t, params),
      api.usage.daily(t, { ...params, granularity: opt.granularity }),
      api.usage.summary(t, params),
    ]);
    setTotals(totalsData);
    setDaily(dailyData ?? []);
    setSummary(summaryData ?? []);
  }, []);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchData(token, selectedRange).finally(() => setLoading(false));
  }, [token, selectedRange, fetchData]);

  const aggregatedRows = useMemo((): AggregatedRow[] => {
    const map = new Map<string, AggregatedRow>();
    for (const row of summary) {
      let key: string;
      let sublabel: string;
      if (groupBy === "agent") {
        key = row.agent_slug || "chat";
        sublabel = [row.provider, row.model].filter(Boolean).join(" / ");
      } else {
        key = row.model || "unknown";
        sublabel = row.provider || "—";
      }
      const existing = map.get(key);
      if (existing) {
        existing.total_input_tokens += row.total_input_tokens;
        existing.total_output_tokens += row.total_output_tokens;
        existing.total_cost_usd += row.total_cost_usd;
        existing.request_count += row.request_count;
        if (sublabel && !existing.sublabel.includes(sublabel)) {
          existing.sublabel += `, ${sublabel}`;
        }
      } else {
        map.set(key, {
          key,
          sublabel,
          total_input_tokens: row.total_input_tokens,
          total_output_tokens: row.total_output_tokens,
          total_cost_usd: row.total_cost_usd,
          request_count: row.request_count,
        });
      }
    }
    return Array.from(map.values()).sort(
      (a, b) => b.total_cost_usd - a.total_cost_usd
    );
  }, [summary, groupBy]);

  if (loading) {
    return (
      <div className="flex justify-center p-16">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  const avgCostPerRequest =
    totals && totals.total_requests > 0
      ? totals.total_cost_usd / totals.total_requests
      : 0;

  const totalCostForPercent = aggregatedRows.reduce(
    (acc, r) => acc + r.total_cost_usd,
    0
  );

  const chartTitle = isSubDay ? "Token Usage" : "Daily Token Usage";
  const chartSubtitle = isSubDay
    ? `Input vs output tokens (${rangeOpt.label} window)`
    : "Input vs output tokens over time";

  return (
    <div className="space-y-6 p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Token Usage</h1>
          <p className="mt-1 text-sm text-gray-400">
            LLM token consumption and cost estimates
          </p>
        </div>
        <div className="flex gap-2">
          {RANGE_OPTIONS.map((opt, idx) => (
            <button
              key={opt.label}
              onClick={() => setSelectedRange(idx)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                selectedRange === idx
                  ? "bg-angie-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-100"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-wide text-gray-500">
            Total Tokens
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-100">
            {formatTokens(totals?.total_tokens ?? 0)}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">
            {formatTokens(totals?.total_input_tokens ?? 0)} in /{" "}
            {formatTokens(totals?.total_output_tokens ?? 0)} out
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-gray-500">
            Total Cost
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-100">
            {formatCost(totals?.total_cost_usd ?? 0)}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">estimated USD</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-gray-500">
            Total Requests
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-100">
            {totals?.total_requests ?? 0}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">LLM API calls</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-gray-500">
            Avg Cost / Request
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-100">
            {formatCost(avgCostPerRequest)}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">per LLM call</p>
        </Card>
      </div>

      {/* Chart */}
      <Card>
        <CardHeader title={chartTitle} subtitle={chartSubtitle} />
        {daily.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <BarChart3 className="mx-auto mb-2 h-10 w-10 opacity-30" />
            <p>No usage data for this period.</p>
          </div>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12, fill: "#9CA3AF" }}
                  tickFormatter={(v: string) => {
                    if (v.includes(" ")) {
                      // Sub-day: "2026-03-01 14:15:00" → "14:15"
                      return v.split(" ")[1].slice(0, 5);
                    }
                    // Daily: "2026-03-01" → "3/1"
                    const d = new Date(v);
                    return `${d.getMonth() + 1}/${d.getDate()}`;
                  }}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "#9CA3AF" }}
                  tickFormatter={formatTokens}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1F2937",
                    border: "1px solid #374151",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#F3F4F6" }}
                  itemStyle={{ color: "#D1D5DB" }}
                  formatter={(value: number | undefined) =>
                    formatTokens(value ?? 0)
                  }
                />
                <Area
                  type="monotone"
                  dataKey="input_tokens"
                  stackId="1"
                  stroke="#7C3AED"
                  fill="#7C3AED"
                  fillOpacity={0.3}
                  name="Input Tokens"
                />
                <Area
                  type="monotone"
                  dataKey="output_tokens"
                  stackId="1"
                  stroke="#06B6D4"
                  fill="#06B6D4"
                  fillOpacity={0.3}
                  name="Output Tokens"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Breakdown Table */}
      <Card>
        <div className="flex items-center justify-between">
          <CardHeader
            title={groupBy === "agent" ? "Agent Breakdown" : "Model Breakdown"}
            subtitle={
              groupBy === "agent"
                ? "Token usage and cost by agent"
                : "Token usage and cost by model"
            }
          />
          <div className="flex gap-1 pr-4">
            {(["agent", "model"] as const).map((g) => (
              <button
                key={g}
                onClick={() => setGroupBy(g)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                  groupBy === g
                    ? "bg-angie-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-gray-100"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>
        {aggregatedRows.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <p>No usage data for this period.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="pb-2 pr-4">
                    {groupBy === "agent" ? "Agent" : "Model"}
                  </th>
                  <th className="pb-2 pr-4">
                    {groupBy === "agent" ? "Provider / Model" : "Provider"}
                  </th>
                  <th className="pb-2 pr-4 text-right">Input Tokens</th>
                  <th className="pb-2 pr-4 text-right">Output Tokens</th>
                  <th className="pb-2 pr-4 text-right">Cost</th>
                  <th className="pb-2 text-right">% of Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {aggregatedRows.map((row) => (
                  <tr key={row.key} className="text-gray-300">
                    <td className="py-2 pr-4 font-medium">{row.key}</td>
                    <td className="py-2 pr-4 text-xs text-gray-400">
                      {row.sublabel || "—"}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-xs">
                      {formatTokens(row.total_input_tokens)}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-xs">
                      {formatTokens(row.total_output_tokens)}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-xs">
                      {formatCost(row.total_cost_usd)}
                    </td>
                    <td className="py-2 text-right font-mono text-xs">
                      {totalCostForPercent > 0
                        ? `${((row.total_cost_usd / totalCostForPercent) * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
