"use client";
import { useCallback, useEffect, useState } from "react";
import { securityApi, sessionsApi, rulesApi, errDetail } from "@/lib/api";
import type { Alert, AuditEntry, DetectionRule, Session } from "@/lib/types";
import { Laptop, LogOut } from "lucide-react";

const DAY = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

export default function SecurityPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [rules, setRules] = useState<DetectionRule[]>([]);
  const [error, setError] = useState("");
  // rule form
  const [rName, setRName] = useState("");
  const [rCat, setRCat] = useState("security");
  const [rType, setRType] = useState("");
  const [rSrc, setRSrc] = useState("");
  const [rMin, setRMin] = useState("1");
  const [rWin, setRWin] = useState("24");
  const [rSev, setRSev] = useState("medium");
  const [rMsg, setRMsg] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  const load = useCallback(() => {
    securityApi.alerts().then((r) => setAlerts(r.data.alerts)).catch(() => setError("Failed to load alerts."));
    securityApi.audit().then((r) => setAudit(r.data)).catch(() => {});
    sessionsApi.list().then((r) => setSessions(r.data.sessions)).catch(() => {});
    rulesApi.list().then((r) => setRules(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
  }, [load]);

  const revoke = async (id: string) => {
    await sessionsApi.revoke(id).catch(() => {});
    load();
  };
  const addRule = async () => {
    setRMsg("");
    if (!rName) { setRMsg("Rule needs a name."); return; }
    if (!rCat && !rType && !rSrc) { setRMsg("Set at least one filter."); return; }
    const payload = {
      name: rName,
      category: rCat || undefined,
      event_type: rType || undefined,
      source: rSrc || undefined,
      window_hours: Math.max(1, Number(rWin) || 24),
      min_count: Math.max(1, Number(rMin) || 1),
      severity: rSev,
    };
    try {
      if (editingId) {
        await rulesApi.update(editingId, payload);
        setRMsg("Rule updated.");
      } else {
        await rulesApi.create(payload);
        setRMsg("Rule created.");
      }
      setRName(""); setRCat("security"); setRType(""); setRSrc(""); setRMin("1"); setRWin("24"); setRSev("medium"); setEditingId(null);
      load();
    } catch (e) { setRMsg(errDetail(e, editingId ? "Update failed" : "Create failed")); }
  };
  const editRule = (r: DetectionRule) => {
    setEditingId(r.id);
    setRName(r.name);
    setRCat(r.category || "");
    setRType(r.event_type || "");
    setRSrc(r.source || "");
    setRMin(String(r.min_count));
    setRWin(String(r.window_hours));
    setRSev(r.severity);
    setRMsg("");
  };
  const cancelEdit = () => {
    setEditingId(null);
    setRName(""); setRCat("security"); setRType(""); setRSrc(""); setRMin("1"); setRWin("24"); setRSev("medium"); setRMsg("");
  };
  const toggleRule = async (r: DetectionRule) => {
    try { await rulesApi.toggle(r.id, !r.enabled); load(); }
    catch (e) { setRMsg(errDetail(e, "Toggle failed")); }
  };
  const delRule = async (id: string) => { await rulesApi.delete(id).catch(() => {}); load(); };

  const sevColor = (s: string) => s === "high" ? "text-red-400 border-red-500/30" : s === "medium" ? "text-yellow-400 border-yellow-500/30" : "text-blue-400 border-blue-500/30";
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Security Center</h2>
      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="space-y-3">
        {alerts.map((a, i) => (
          <div key={i} className={`bg-[#0d1224] border rounded-xl p-4 ${sevColor(a.severity)}`}>
            <div className="font-semibold">{a.title}</div>
            <div className="text-sm text-slate-400 mt-1">{a.detail}</div>
            <div className="text-xs text-slate-600 mt-2">{a.type} · {a.severity}</div>
          </div>
        ))}
        {alerts.length === 0 && !error && <div className="text-slate-500 text-sm">No active alerts.</div>}
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Detection rules</h3>
        <div className="space-y-2 mb-4">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center gap-3 text-sm border-b border-slate-800/50 pb-2">
              <span className={`text-xs px-2 py-0.5 rounded ${r.severity === "high" ? "bg-red-500/10 text-red-400" : r.severity === "medium" ? "bg-yellow-500/10 text-yellow-400" : "bg-blue-500/10 text-blue-400"}`}>{r.severity}</span>
              <span className="font-medium flex-1">{r.name}</span>
              <span className="text-xs text-slate-500">{[r.source && `source=${r.source}`, r.category && `cat=${r.category}`, r.event_type && `type=${r.event_type}`].filter(Boolean).join(" · ") || "any event"}</span>
              <span className="text-xs text-slate-500">≥{r.min_count}/{r.window_hours}h</span>
              <span className={`text-xs ${r.enabled ? "text-green-400" : "text-slate-500"}`}>{r.enabled ? "on" : "off"}</span>
              <button onClick={() => toggleRule(r)} className="text-xs text-cyan-400 hover:text-cyan-300">{r.enabled ? "Disable" : "Enable"}</button>
              <button onClick={() => editRule(r)} className="text-xs text-slate-300 hover:text-white">Edit</button>
              <button onClick={() => delRule(r.id)} className="text-xs text-red-400 hover:text-red-300">Delete</button>
            </div>
          ))}
          {rules.length === 0 && <div className="text-slate-500 text-sm">No rules. Create one to turn activity patterns into alerts.</div>}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-7 gap-2 items-end">
          <div className="col-span-2"><label className="text-xs text-slate-500" htmlFor="rule-name">Name</label><input id="rule-name" value={rName} onChange={(e) => setRName(e.target.value)} className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" /></div>
          <div><label className="text-xs text-slate-500" htmlFor="rule-cat">Category</label><input id="rule-cat" value={rCat} onChange={(e) => setRCat(e.target.value)} placeholder="security" className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" /></div>
          <div><label className="text-xs text-slate-500" htmlFor="rule-type">Event type</label><input id="rule-type" value={rType} onChange={(e) => setRType(e.target.value)} placeholder="security.login_alert" className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" /></div>
          <div><label className="text-xs text-slate-500" htmlFor="rule-src">Source</label><input id="rule-src" value={rSrc} onChange={(e) => setRSrc(e.target.value)} placeholder="google" className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" /></div>
          <div><label className="text-xs text-slate-500">Min / hours</label><div className="flex gap-1"><input id="rule-min" aria-label="Minimum event count" value={rMin} onChange={(e) => setRMin(e.target.value)} className="w-12 bg-[#0a0e1a] border border-slate-700 rounded-lg px-2 py-2" /><input id="rule-win" aria-label="Window in hours" value={rWin} onChange={(e) => setRWin(e.target.value)} className="w-14 bg-[#0a0e1a] border border-slate-700 rounded-lg px-2 py-2" /></div></div>
          <div><label className="text-xs text-slate-500" htmlFor="rule-sev">Severity</label><select id="rule-sev" value={rSev} onChange={(e) => setRSev(e.target.value)} className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-2 py-2">{["info", "low", "medium", "high"].map((s) => <option key={s}>{s}</option>)}</select></div>
          <button onClick={addRule} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-3 py-2 text-sm">{editingId ? "Save" : "Add"}</button>
          {editingId && <button onClick={cancelEdit} className="bg-slate-700 hover:bg-slate-600 rounded-lg px-3 py-2 text-sm">Cancel</button>}
        </div>
        {rMsg && <div className="text-xs text-slate-400 mt-2">{rMsg}</div>}
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Active sessions</h3>
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-center gap-3 text-sm border-b border-slate-800/50 pb-2">
              <Laptop size={15} className="text-slate-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="truncate">{s.user_agent || "unknown client"}</div>
                <div className="text-xs text-slate-500">{s.ip_address || "no ip"} · seen {DAY(s.last_seen_at)}</div>
              </div>
              {s.current && <span className="text-xs bg-cyan-500/10 text-cyan-300 px-2 py-0.5 rounded">this device</span>}
              {s.revoked && <span className="text-xs bg-red-500/10 text-red-400 px-2 py-0.5 rounded">revoked</span>}
              {!s.revoked && !s.current && <button onClick={() => revoke(s.id)} className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300"><LogOut size={12} /> Revoke</button>}
            </div>
          ))}
          {sessions.length === 0 && <div className="text-slate-500 text-sm">No recorded sessions.</div>}
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-4">Audit Log</h3>
        <div className="space-y-1 max-h-96 overflow-auto">
          {audit.map((a) => (
            <div key={a.id} className="text-xs flex gap-3 border-b border-slate-800/50 py-1">
              <span className="text-slate-500 w-40">{DAY(a.created_at)}</span>
              <span className="text-cyan-300 w-40">{a.action}</span>
              <span className="text-slate-400 flex-1 truncate">{JSON.stringify(a.details)}</span>
              <span className={a.status === "success" ? "text-green-400" : "text-red-400"}>{a.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}