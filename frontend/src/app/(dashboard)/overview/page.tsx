"use client";
import { useEffect, useState } from "react";
import { overviewApi, eventsApi } from "@/lib/api";
import type { EventsStats, OverviewData } from "@/lib/types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [stats, setStats] = useState<EventsStats | null>(null);
  useEffect(() => {
    overviewApi.get().then((r) => setData(r.data)).catch(() => {});
    eventsApi.stats().then((r) => setStats(r.data)).catch(() => {});
  }, []);
  const cards = [
    { label: "Connected Accounts", value: data?.accounts ?? 0 },
    { label: "Integrations", value: data?.integrations ?? 0 },
    { label: "Devices", value: data?.devices ?? 0 },
    { label: "Total Events", value: data?.events ?? 0 },
  ];
  const COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399"];
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Overview</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
            <div className="text-slate-400 text-sm">{c.label}</div>
            <div className="text-3xl font-bold mt-2 text-cyan-300">{c.value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold mb-4">Events by Source</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stats?.by_source || []}>
              <XAxis dataKey="source" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip contentStyle={{ background: "#0d1224", border: "1px solid #1e293b" }} />
              <Bar dataKey="count" fill="#22d3ee" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold mb-4">Events by Category</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={stats?.by_category || []} dataKey="count" nameKey="category" outerRadius={90}>
                {(stats?.by_category || []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#0d1224", border: "1px solid #1e293b" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-4">Recent Events</h3>
        <div className="space-y-2">
          {(data?.recent_events || []).map((e) => (
            <div key={e.id} className="flex items-center gap-3 text-sm border-b border-slate-800/50 pb-2">
              <span className="text-slate-500 text-xs w-40">{new Date(e.timestamp).toLocaleString()}</span>
              <span className="text-cyan-300 w-24">{e.source}</span>
              <span className="text-slate-300 flex-1 truncate">{e.description || e.event_type}</span>
            </div>
          ))}
          {!data?.recent_events?.length && <div className="text-slate-500 text-sm">No events yet. Connect integrations and sync.</div>}
        </div>
      </div>
    </div>
  );
}