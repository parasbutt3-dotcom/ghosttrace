"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { eventsApi } from "@/lib/api";
import type { EventItem } from "@/lib/types";

const LocationMap = dynamic(() => import("@/components/LocationMap"), {
  ssr: false,
  loading: () => <div className="text-slate-500 text-sm">Loading map…</div>,
});

const PAGE = 200;
const SAVED_KEY = "ghosttrace.savedQueries";

interface SavedQuery {
  name: string;
  q: string;
  source: string;
  category: string;
  start: string;
  end: string;
}

export default function TimelinePage() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [category, setCategory] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedQuery[]>([]);
  const [saveName, setSaveName] = useState("");

  useEffect(() => {
    const id = setTimeout(() => {
      try {
        const raw = localStorage.getItem(SAVED_KEY);
        if (raw) setSaved(JSON.parse(raw));
      } catch {}
    }, 0);
    return () => clearTimeout(id);
  }, []);

  const persistSaved = (next: SavedQuery[]) => {
    setSaved(next);
    try { localStorage.setItem(SAVED_KEY, JSON.stringify(next)); } catch {}
  };

  const load = useCallback((append = false, offset = 0) => {
    setLoading(true);
    eventsApi.list({ q: q || undefined, source: source || undefined, category: category || undefined,
      start: start || undefined, end: end || undefined, limit: PAGE, offset })
      .then((r) => {
        setTotal(r.data.total);
        setItems((prev) => (append ? [...prev, ...r.data.items] : r.data.items));
        setNextOffset(r.data.next_offset);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [q, source, category, start, end]);
  useEffect(() => {
    const id = setTimeout(() => load(), 0);
    return () => clearTimeout(id);
  }, [load]);

  const applySaved = (sq: SavedQuery) => {
    setQ(sq.q); setSource(sq.source); setCategory(sq.category); setStart(sq.start); setEnd(sq.end);
  };
  const saveCurrent = () => {
    if (!saveName.trim()) return;
    const next = [...saved.filter((s) => s.name !== saveName.trim()),
      { name: saveName.trim(), q, source, category, start, end }];
    persistSaved(next);
    setSaveName("");
  };
  const removeSaved = (name: string) => persistSaved(saved.filter((s) => s.name !== name));

  const chips: { label: string; clear: () => void }[] = [];
  if (q) chips.push({ label: `search: ${q}`, clear: () => setQ("") });
  if (source) chips.push({ label: `source: ${source}`, clear: () => setSource("") });
  if (category) chips.push({ label: `category: ${category}`, clear: () => setCategory("") });
  if (start) chips.push({ label: `from: ${start}`, clear: () => setStart("") });
  if (end) chips.push({ label: `to: ${end}`, clear: () => setEnd("") });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Activity Timeline</h2>
      <div className="flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 flex-1 min-w-40" />
        <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 w-40" />
        <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 w-40" />
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2" />
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2" />
        <button onClick={() => load()} disabled={loading} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 disabled:opacity-50">Filter</button>
      </div>
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {chips.map((c, i) => (
            <button key={i} onClick={c.clear} className="text-xs bg-slate-700 hover:bg-slate-600 rounded-full px-3 py-1">{c.label} ✕</button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-center">
        <input value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="Saved query name" className="bg-[#0d1224] border border-slate-700 rounded-lg px-3 py-2 text-sm" />
        <button onClick={saveCurrent} className="text-xs bg-slate-700 hover:bg-slate-600 rounded-lg px-3 py-2">Save filters</button>
        {saved.map((sq) => (
          <span key={sq.name} className="flex items-center gap-1 text-xs bg-cyan-600/20 text-cyan-300 rounded-full px-3 py-1">
            <button onClick={() => applySaved(sq)}>{sq.name}</button>
            <button onClick={() => removeSaved(sq.name)} className="text-slate-400 hover:text-red-400">✕</button>
          </span>
        ))}
      </div>
      <div className="text-sm text-slate-500">{total} events</div>
      <LocationMap />
      <div className="space-y-2">
        {items.map((e) => (
          <div key={e.id} className="bg-[#0d1224] border border-slate-800 rounded-lg">
            <div onClick={() => setExpanded(expanded === e.id ? null : e.id)} className="p-3 flex gap-3 flex-wrap sm:flex-nowrap cursor-pointer">
              <div className="text-xs text-slate-500 w-40 shrink-0">{new Date(e.timestamp).toLocaleString()}</div>
              <div className="w-28 shrink-0 text-cyan-300 text-sm">{e.source}</div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{e.event_type}</div>
                <div className="text-xs text-slate-400 truncate">{e.description}</div>
                <div className="text-xs text-slate-600 mt-1">{e.application} · {e.collection_method} · conf {e.confidence}</div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded h-fit ${e.permission_status === "authorized" ? "bg-green-500/10 text-green-400" : e.permission_status === "unavailable" ? "bg-red-500/10 text-red-400" : "bg-yellow-500/10 text-yellow-400"}`}>{e.permission_status}</span>
            </div>
            {expanded === e.id && (
              <div className="border-t border-slate-800 p-3 text-xs space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div><span className="text-slate-500">id:</span> <span className="text-slate-300">{e.id}</span></div>
                  <div><span className="text-slate-500">timestamp:</span> <span className="text-slate-300">{e.timestamp}</span></div>
                  <div><span className="text-slate-500">source:</span> <span className="text-slate-300">{e.source}</span></div>
                  <div><span className="text-slate-500">application:</span> <span className="text-slate-300">{e.application ?? "—"}</span></div>
                  <div><span className="text-slate-500">event_type:</span> <span className="text-slate-300">{e.event_type}</span></div>
                  <div><span className="text-slate-500">category:</span> <span className="text-slate-300">{e.category ?? "—"}</span></div>
                  <div><span className="text-slate-500">collection_method:</span> <span className="text-slate-300">{e.collection_method}</span></div>
                  <div><span className="text-slate-500">permission_status:</span> <span className="text-slate-300">{e.permission_status}</span></div>
                  <div><span className="text-slate-500">confidence:</span> <span className="text-slate-300">{e.confidence}</span></div>
                </div>
                {e.description && <div><span className="text-slate-500">description:</span> <span className="text-slate-300">{e.description}</span></div>}
                <div>
                  <div className="text-slate-500 mb-1">metadata:</div>
                  <pre className="bg-[#0a0e1a] border border-slate-800 rounded-lg p-2 overflow-auto text-[11px] text-slate-300">{JSON.stringify(e.metadata ?? null, null, 2)}</pre>
                </div>
              </div>
            )}
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