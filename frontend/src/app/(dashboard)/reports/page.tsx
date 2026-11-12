"use client";
import { useEffect, useState } from "react";
import { reportsApi } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";

export default function ReportsPage() {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState("");
  useEffect(() => {
    const id = setTimeout(() => {
      reportsApi.summary(days).then((r) => setSummary(r.data)).catch(() => setError("Failed to load report."));
    }, 250);
    return () => clearTimeout(id);
  }, [days]);
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Reports</h2>
      <div className="flex flex-wrap gap-2 items-center">
        <label className="text-sm text-slate-400" htmlFor="range-days">Range (days)</label>
        <input id="range-days" type="number" min={1} max={365} value={days} onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))} className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 w-24" />
        <a href={reportsApi.exportUrl("json", days)} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2 text-sm">Export JSON</a>
        <a href={reportsApi.exportUrl("csv", days)} className="bg-slate-700 hover:bg-slate-600 rounded-lg px-4 py-2 text-sm">Export CSV</a>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      {summary && (
        <>
          <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
            <div className="text-slate-400 text-sm">Total events in range</div>
            <div className="text-3xl font-bold text-cyan-300">{summary.total}</div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
              <h3 className="font-semibold mb-3">By Source</h3>
              {summary.by_source.map((s) => <div key={s.source} className="flex justify-between text-sm py-1 border-b border-slate-800/50"><span>{s.source}</span><span>{s.count}</span></div>)}
            </div>
            <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
              <h3 className="font-semibold mb-3">Top Applications</h3>
              {summary.top_applications.map((a) => <div key={a.application} className="flex justify-between text-sm py-1 border-b border-slate-800/50"><span className="truncate">{a.application}</span><span>{a.count}</span></div>)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}