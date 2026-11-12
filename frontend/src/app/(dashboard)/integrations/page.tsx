"use client";
import { useEffect, useRef, useState } from "react";
import { integrationsApi, takeoutApi, errDetail } from "@/lib/api";
import type { ConnectedAccount, Integration, IntegrationDetails, TakeoutSummary } from "@/lib/types";

const OAUTH_MESSAGES: Record<string, string> = {
  access_denied: "Google sign-in was cancelled.",
  consent_required: "Google required consent that wasn't granted. Try connecting again.",
  login_required: "Google asked you to sign in first. Start the connection again.",
  google_error: "Google returned an error during sign-in. Try again.",
  invalid_or_expired_state: "That Google sign-in link expired. Click “Connect Google Account” to start again.",
  token_exchange_failed: "Google rejected the sign-in code. Start the connection again.",
  token_exchange_unreachable: "Could not reach Google. Check your connection and try again.",
  missing_code_or_state: "The Google callback was incomplete. Start the connection again.",
  no_user_for_state: "Your session expired during sign-in. Start again.",
  account_already_linked: "That Google account is already linked to another Ghosttrace user.",
};

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [oauthBanner, setOauthBanner] = useState<{ ok: boolean; text: string } | null>(() => {
    if (typeof window === "undefined") return null;
    const p = new URLSearchParams(window.location.search);
    const err = p.get("error");
    const ok = p.get("connected");
    if (err) return { ok: false, text: OAUTH_MESSAGES[err] || `Google connection failed (${err}).` };
    if (ok) return { ok: true, text: `${ok.charAt(0).toUpperCase() + ok.slice(1)} account connected.` };
    return null;
  });
  const [kinds, setKinds] = useState<string[]>([]);
  const [newKind, setNewKind] = useState("activitywatch");
  const [newName, setNewName] = useState("");
  const [ghUser, setGhUser] = useState("");
  const [ghToken, setGhToken] = useState("");
  const [scopes, setScopes] = useState({ gmail: false, calendar: false, drive: false });
  const [takeoutFile, setTakeoutFile] = useState<File | null>(null);
  const [takeoutBusy, setTakeoutBusy] = useState(false);
  const [takeoutResult, setTakeoutResult] = useState<TakeoutSummary | string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<Integration | null>(null);
  const [details, setDetails] = useState<IntegrationDetails | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const load = () => {
    integrationsApi.list().then((r) => setIntegrations(r.data)).catch(() => {});
    integrationsApi.accounts().then((r) => setAccounts(r.data)).catch(() => {});
    integrationsApi.kinds().then((r) => setKinds(r.data.kinds)).catch(() => {});
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    // Strip the OAuth callback params from the URL once the banner has been read.
    if (oauthBanner) window.history.replaceState({}, "", window.location.pathname);
  }, [oauthBanner]);
  const create = async () => {
    if (!newName) return;
    let config: Record<string, unknown> = {};
    if (newKind === "wazuh") config = { base_url: "https://localhost:55000", username: "wazuh", password: "" };
    else if (newKind === "activitywatch") config = { base_url: "http://localhost:5600" };
    else if (newKind === "github") config = { username: ghUser, access_token: ghToken || undefined };
    try {
      await integrationsApi.create(newKind, newName, config);
      setNewName(""); setGhUser(""); setGhToken("");
      load();
    } catch (e) {
      alert(errDetail(e, "Could not add integration"));
    }
  };
  const sync = async (id: string) => {
    setSyncing(id);
    try { await integrationsApi.sync(id); } catch {}
    setSyncing(null);
    load();
    if (selected?.id === id) openDetails(id);
  };
  const openDetails = async (id: string) => {
    const r = await integrationsApi.get(id);
    setDetails(r.data);
    setSelected(integrations.find((i) => i.id === id) ?? null);
  };
  const connectGoogle = async () => {
    try {
      const r = await integrationsApi.googleLogin(scopes);
      window.location.href = r.data.authorization_url;
    } catch (e) {
      alert(errDetail(e, "Google not configured"));
    }
  };
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Integrations</h2>

      {oauthBanner && (
        <div className={`flex justify-between items-center gap-3 rounded-xl border p-3 text-sm ${oauthBanner.ok ? "bg-green-500/10 border-green-500/30 text-green-300" : "bg-red-500/10 border-red-500/30 text-red-300"}`}>
          <span>{oauthBanner.text}</span>
          <button onClick={() => setOauthBanner(null)} className="text-xs opacity-70 hover:opacity-100 shrink-0">Dismiss</button>
        </div>
      )}

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Connected Accounts</h3>
        {accounts.map((a) => (
          <div key={a.id} className="flex justify-between items-center border-b border-slate-800/50 py-2 text-sm">
            <div>
              <span className="text-cyan-300">{a.provider}</span> · {a.email || a.display_name} · <span className="text-slate-500">{a.status}</span>
            </div>
            <button onClick={() => { integrationsApi.disconnectAccount(a.id).then(load); }} className="text-xs text-red-400">Disconnect</button>
          </div>
        ))}
        {accounts.length === 0 && <div className="text-slate-500 text-sm">No connected accounts.</div>}
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={scopes.gmail} onChange={(e) => setScopes({ ...scopes, gmail: e.target.checked })} />Gmail security alerts</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={scopes.calendar} onChange={(e) => setScopes({ ...scopes, calendar: e.target.checked })} />Calendar events</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={scopes.drive} onChange={(e) => setScopes({ ...scopes, drive: e.target.checked })} />Recent Drive files</label>
          </div>
          <button onClick={connectGoogle} title="Reconnect with additional scopes: Gmail alert emails (security events), Calendar (meetings), Drive (file activity). Gmail shows an 'unverified app' warning for dev OAuth clients — choose Advanced → Proceed."
            className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2 text-sm font-medium">
            Connect Google Account
          </button>
          <span className="text-xs text-slate-500">Tip: the third-party app list itself has no consumer API — check it at
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className="text-cyan-400 ml-1">myaccount.google.com/permissions</a>.
          </span>
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
        <h3 className="font-semibold mb-1">Google Takeout import</h3>
        <p className="text-xs text-slate-500 mb-3">
          The deepest account data is not an API — it&apos;s your export. Request a Takeout (takeout.google.com) with
          <em> Location History</em>, <em>My Activity</em> and <em>YouTube</em>, then upload the ZIP here.
          Location points, place visits, search activity and watch history become timeline events.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileRef} type="file" accept=".zip" className="text-sm text-slate-400 file:bg-slate-700 file:text-slate-200 file:border-0 file:rounded-lg file:px-3 file:py-2"
            onChange={(e) => { setTakeoutFile(e.target.files?.[0] ?? null); setTakeoutResult(null); }} />
          <button disabled={!takeoutFile || takeoutBusy}
            onClick={async () => {
              if (!takeoutFile) return;
              setTakeoutBusy(true); setTakeoutResult(null);
              try {
                const r = await takeoutApi.import(takeoutFile);
                setTakeoutResult(r.data);
              } catch (e) { setTakeoutResult(errDetail(e, "Import failed")); }
              finally { setTakeoutBusy(false); if (fileRef.current) fileRef.current.value = ""; }
            }}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 rounded-lg px-4 py-2 text-sm">
            {takeoutBusy ? "Importing… (can take a minute)" : "Import ZIP"}
          </button>
        </div>
        {typeof takeoutResult === "object" && takeoutResult && (
          <div className="mt-3 text-sm text-green-300">
            Imported {takeoutResult.total_ingested} events — {takeoutResult.locations} locations,
            {takeoutResult.place_visits} place visits, {takeoutResult.activities} activities, {takeoutResult.youtube} YouTube.
          </div>
        )}
        {typeof takeoutResult === "string" && <div className="mt-3 text-sm text-red-400">{takeoutResult}</div>}
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-2">
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="text-xs text-slate-500" htmlFor="integ-kind">Kind</label>
            <select id="integ-kind" value={newKind} onChange={(e) => setNewKind(e.target.value)} className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2">
              {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-40">
            <label className="text-xs text-slate-500" htmlFor="integ-name">Name</label>
            <input id="integ-name" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" />
          </div>
          <button onClick={create} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2">Add</button>
        </div>
        {newKind === "github" && (
          <div className="flex flex-wrap gap-2">
            <input value={ghUser} onChange={(e) => setGhUser(e.target.value)} placeholder="GitHub username" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 w-48" />
            <input type="password" value={ghToken} onChange={(e) => setGhToken(e.target.value)} placeholder="Optional PAT (adds private activity)" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {integrations.map((i) => (
          <div key={i.id} className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{i.name}</div>
                <div className="text-xs text-slate-500">{i.kind} · {i.status}</div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => sync(i.id)} disabled={syncing === i.id} className="text-xs bg-cyan-600/20 text-cyan-300 rounded px-3 py-1 disabled:opacity-50">{syncing === i.id ? "Syncing…" : "Sync"}</button>
                <button onClick={() => openDetails(i.id)} className="text-xs bg-slate-700 rounded px-3 py-1">Details</button>
                <button onClick={() => { integrationsApi.delete(i.id).then(load); }} className="text-xs text-red-400">Remove</button>
              </div>
            </div>
            {i.last_sync_at && <div className="text-xs text-slate-600 mt-2">Last sync: {new Date(i.last_sync_at).toLocaleString()}</div>}
            {i.last_error && <div className="text-xs text-red-400 mt-1">{i.last_error}</div>}
          </div>
        ))}
      </div>

      {details && (
        <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold mb-3">Capabilities — {details.name}</h3>
          <div className="space-y-2">
            {(details.capabilities || []).map((c, idx) => (
              <div key={idx} className="flex items-center gap-3 text-sm border-b border-slate-800/50 pb-2">
                <span className={`w-3 h-3 rounded-full ${c.available ? "bg-green-400" : "bg-red-400"}`} />
                <span className="font-medium w-48">{c.name}</span>
                <span className="text-slate-400 flex-1 text-xs">{c.reason}</span>
                {!c.available && c.requires?.length > 0 && <span className="text-xs text-slate-600">requires: {c.requires.join(", ")}</span>}
              </div>
            ))}
          </div>
          <button onClick={() => setDetails(null)} className="mt-3 text-xs text-slate-400">Close</button>
        </div>
      )}
    </div>
  );
}
