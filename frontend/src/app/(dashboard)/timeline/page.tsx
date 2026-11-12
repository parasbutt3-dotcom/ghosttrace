"use client";
import { useCallback, useEffect, useState } from "react";
import { eventsApi } from "@/lib/api";
import type { EventItem } from "@/lib/types";

const PAGE = 200;

export default function TimelinePage() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback((append = false, offset = 0) => {
    setLoading(true);
    eventsApi.list({ q: q || undefined, source: source || undefined, limit: PAGE, offset })
      .then((r) => {
        setTotal(r.data.total);
        setItems((prev) => (append ? [...prev, ...r.data.items] : r.data.items));
        setNextOffset(r.data.next_offset);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [q, source]);
  useEffect(() => {
    const id = setTimeout(() => load(), 0);
    return () => clearTimeout(id);
  }, [load]);
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Activity Timeline</h2>
      <div className="flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 flex-1 min-w-40" />
        <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 w-40" />
        <button onClick={() => load()} disabled={loading} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 disabled:opacity-50">Filter</button>
      </div>
      <div className="text-sm text-slate-500">{total} events</div>
      <div className="space-y-2">
        {items.map((e) => (
          <div key={e.id} className="bg-[#0d1224] border border-slate-800 rounded-lg p-3 flex gap-3 flex-wrap sm:flex-nowrap">
            <div className="text-xs text-slate-500 w-40 shrink-0">{new Date(e.timestamp).toLocaleString()}</div>
            <div className="w-28 shrink-0 text-cyan-300 text-sm">{e.source}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{e.event_type}</div>
              <div className="text-xs text-slate-400 truncate">{e.description}</div>
              <div className="text-xs text-slate-600 mt-1">{e.application} · {e.collection_method} · conf {e.confidence}</div>
            </div>
            <span className={`text-xs px-2 py-0.5 rounded h-fit ${e.permission_status === "authorized" ? "bg-green-500/10 text-green-400" : e.permission_status === "unavailable" ? "bg-red-500/10 text-red-400" : "bg-yellow-500/10 text-yellow-400"}`}>{e.permission_status}</span>
          </div>
        ))}
        {loading && <div className="text-slate-500 text-sm">Loading…</div>}
        {!loading && items.length === 0 && <div className="text-slate-500 text-sm">No events.</div>}
        {nextOffset !== null && (
          <button onClick={() => load(true, nextOffset)} disabled={loading} className="text-sm text-cyan-400 hover:text-cyan-300 disabled:opacity-50">
            Load more…
          </button>
        )}
      </div>
    </div>
  );
}