"use client";
import { useEffect, useState } from "react";
import { insightsApi } from "@/lib/api";
import type { Insights } from "@/lib/types";
import { Activity, Flame, Calendar, FileText, GitBranch, Shield, Layers, MapPin, MapPinned } from "lucide-react";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function InsightsPage() {
  const [data, setData] = useState<Insights | null>(null);
  const [days, setDays] = useState(14);
  const [error, setError] = useState("");
  useEffect(() => {
    const id = setTimeout(() => insightsApi.get(days).then((r) => setData(r.data)).catch(() => setError("Failed to load insights.")), 200);
    return () => clearTimeout(id);
  }, [days]);
  const maxHour = Math.max(1, ...(data?.hourly || [{ count: 1 }]).map((h) => h.count));
  const maxWeekday = Math.max(1, ...(data?.weekdays || [{ count: 1 }]).map((w) => w.count));
  const corr = [
    { label: "Meetings", value: data?.correlations.meetings ?? 0, icon: Calendar },
    { label: "File edits", value: data?.correlations.file_edits ?? 0, icon: FileText },
    { label: "Git pushes", value: data?.correlations.git_pushes ?? 0, icon: GitBranch },
    { label: "Security alerts", value: data?.correlations.security_alerts ?? 0, icon: Shield },
    { label: "Location points", value: data?.correlations.location_points ?? 0, icon: MapPin },
    { label: "Place visits", value: data?.correlations.place_visits ?? 0, icon: MapPinned },
  ];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-bold">Insights</h2>
        <div className="flex items-center gap-2">
          {[7, 14, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={`text-sm px-3 py-1 rounded-lg border ${days === d ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/30" : "text-slate-400 border-slate-700"}`}>{d}d</button>
          ))}
        </div>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <div className="text-slate-400 text-sm flex items-center gap-2"><Activity size={14} /> Total events</div>
          <div className="text-3xl font-bold mt-2 text-cyan-300">{data?.total_events ?? 0}</div>
        </div>
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <div className="text-slate-400 text-sm flex items-center gap-2"><Layers size={14} /> Active days</div>
          <div className="text-3xl font-bold mt-2 text-violet-300">{data?.active_days ?? 0}</div>
        </div>
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <div className="text-slate-400 text-sm flex items-center gap-2"><Flame size={14} /> Current streak</div>
          <div className="text-3xl font-bold mt-2 text-orange-300">{data?.current_streak ?? 0}</div>
        </div>
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <div className="text-slate-400 text-sm flex items-center gap-2"><Shield size={14} /> MFA / integrations</div>
          <div className="text-3xl font-bold mt-2 text-green-300">{data?.coverage.mfa_enabled ? "On" : "Off"}</div>
          <div className="text-xs text-slate-500 mt-1">{data?.coverage.integrations_enabled ?? 0} enabled{data && data.coverage.integrations_error > 0 ? ` · ${data.coverage.integrations_error} erroring` : ""}</div>
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-4">Activity by hour of day</h3>
        <div className="flex items-end gap-1 h-28">
          {(data?.hourly || []).map((h) => (
            <div key={h.hour} className="flex-1 flex flex-col items-center gap-1" title={`${h.hour}:00 — ${h.count} events`}>
              <div className="w-full bg-cyan-500/70 rounded-t" style={{ height: `${(h.count / maxHour) * 100}%`, minHeight: h.count ? 2 : 0 }} />
              {h.hour % 4 === 0 && <span className="text-[10px] text-slate-600">{h.hour}</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold mb-4">Activity by weekday</h3>
          <div className="space-y-2">
            {(data?.weekdays || []).map((w) => (
              <div key={w.weekday} className="flex items-center gap-2 text-sm">
                <span className="w-8 text-slate-500 text-xs">{DAY_NAMES[w.weekday]}</span>
                <div className="flex-1 bg-slate-800/50 rounded-full h-2 overflow-hidden">
                  <div className="h-full bg-violet-400/70" style={{ width: `${(w.count / maxWeekday) * 100}%` }} />
                </div>
                <span className="w-12 text-right text-slate-400 text-xs">{w.count}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold mb-4">Cross-account signals</h3>
          <div className="grid grid-cols-2 gap-3">
            {corr.map((c) => {
              const Icon = c.icon;
              return (
                <div key={c.label} className="border border-slate-800 rounded-lg p-3 flex items-center gap-3">
                  <Icon size={16} className="text-cyan-300" />
                  <div>
                    <div className="text-lg font-bold text-slate-200">{c.value}</div>
                    <div className="text-xs text-slate-500">{c.label} ({days}d)</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-4">Top applications</h3>
        <div className="space-y-1">
          {(data?.top_applications || []).map((a) => (
            <div key={a.application} className="flex justify-between text-sm py-1 border-b border-slate-800/50">
              <span className="truncate">{a.application}</span>
              <span className="text-slate-500 ml-3 shrink-0">{a.count}</span>
            </div>
          ))}
          {!data?.top_applications?.length && <div className="text-slate-500 text-sm">No application data yet. Connect ActivityWatch, GitHub, or Google Drive and sync.</div>}
        </div>
      </div>
    </div>
  );
}