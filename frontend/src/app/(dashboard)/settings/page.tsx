"use client";
import { useCallback, useEffect, useState } from "react";
import { apiKeysApi, authApi, errDetail, securityApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiKeyCreated, ApiKeyRow, MfaSetupResponse } from "@/lib/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [setup, setSetup] = useState<MfaSetupResponse | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [pwCur, setPwCur] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [delPw, setDelPw] = useState("");
  const [delMsg, setDelMsg] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [keyName, setKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [retention, setRetention] = useState<{ days: number; default_days: number } | null>(null);
  const loadKeys = useCallback(() => { apiKeysApi.list().then((r) => setKeys(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    const id = setTimeout(loadKeys, 0);
    return () => clearTimeout(id);
  }, [loadKeys]);
  useEffect(() => {
    const id = setTimeout(() => { securityApi.retention().then((r) => setRetention(r.data)).catch(() => {}); }, 0);
    return () => clearTimeout(id);
  }, []);
  const createKey = async () => {
    if (!keyName) return;
    try {
      const r = await apiKeysApi.create(keyName);
      setCreatedKey(r.data);
      setKeyName("");
      loadKeys();
    } catch (e) { setMsg(errDetail(e, "Key creation failed")); }
  };
  const revokeKey = async (id: string) => {
    await apiKeysApi.revoke(id).catch(() => {});
    loadKeys();
  };
  const startSetup = async () => {
    setMsg("");
    try {
      const r = await authApi.mfaSetup();
      setSetup(r.data);
      setMsg("Scan the URI or add the secret in your authenticator, then verify below. Save the recovery codes!");
    } catch (e) { setMsg(errDetail(e, "Setup failed")); }
  };
  const enableMfa = async () => {
    setMsg("");
    try {
      await authApi.mfaVerify(code);
      setMsg(`MFA enabled. ${setup?.recovery_codes.length ?? 0} recovery codes were generated — store them offline.`);
      if (setup?.recovery_codes) setCodes(setup.recovery_codes);
      setSetup(null); setCode("");
    } catch (e) { setMsg(errDetail(e, "Verify failed")); }
  };
  const disableMfa = async () => {
    setMsg("");
    try {
      await authApi.mfaDisable(code);
      setMsg("MFA disabled.");
      setCodes([]);
      setCode("");
    } catch (e) { setMsg(errDetail(e, "Disable failed")); }
  };
  const regenerateCodes = async () => {
    setMsg("");
    try {
      const r = await authApi.mfaRecoveryCodes();
      setCodes(r.data.recovery_codes);
      setMsg("New recovery codes generated — old ones are invalid.");
    } catch (e) { setMsg(errDetail(e, "Regenerate failed")); }
  };
  const changePassword = async () => {
    setPwMsg("");
    if (pwNew.length < 8) { setPwMsg("New password must be at least 8 characters."); return; }
    try {
      await authApi.changePassword(pwCur, pwNew);
      setPwMsg("Password changed. Signing out…");
      setTimeout(() => logout(), 1500);
    } catch (e) { setPwMsg(errDetail(e, "Change failed")); }
  };
  const deleteAccount = async () => {
    setDelMsg("");
    if (!confirmDelete) { setDelMsg("Tick the confirmation box first."); return; }
    try {
      await authApi.deleteAccount(delPw);
      setDelMsg("Account and all activity data deleted.");
      setTimeout(() => logout(), 1500);
    } catch (e) { setDelMsg(errDetail(e, "Delete failed")); }
  };
  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-2xl font-bold">Settings</h2>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold">Account</h3>
        <div className="text-sm text-slate-400">
          Signed in as <span className="text-cyan-300">{user?.email}</span>
          {user?.is_admin && <span className="ml-2 text-xs bg-cyan-500/10 text-cyan-300 px-2 py-0.5 rounded">admin</span>}
          {user?.mfa_enabled && <span className="ml-2 text-xs bg-green-500/10 text-green-300 px-2 py-0.5 rounded">MFA on</span>}
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold">Data retention</h3>
        <p className="text-xs text-slate-500">
          Collected events are purged automatically after{" "}
          <span className="text-cyan-300">{retention ? `${retention.days} days` : "…"}</span>
          {retention && retention.days !== retention.default_days && <> (default is {retention.default_days})</>}.
          The operator can change this window via <code>EVENT_RETENTION_DAYS</code> on this instance.
        </p>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold">Two-factor authentication (TOTP)</h3>
        <button onClick={startSetup} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2 text-sm">Set up MFA</button>
        {setup && (
          <div className="text-sm space-y-2">
            <div>Secret: <code className="break-all">{setup.secret}</code></div>
            <div className="text-xs text-slate-500 break-all">{setup.otpauth_uri}</div>
          </div>
        )}
        <div className="flex gap-2">
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code or recovery code" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          <button onClick={enableMfa} className="bg-green-600 hover:bg-green-500 rounded-lg px-4 py-2 text-sm">Enable</button>
          <button onClick={disableMfa} className="bg-red-600/80 hover:bg-red-600 rounded-lg px-4 py-2 text-sm">Disable</button>
        </div>
        {codes.length > 0 && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
            <div className="text-sm font-semibold text-yellow-300 mb-2">Recovery codes (each works once)</div>
            <div className="grid grid-cols-2 gap-1 text-xs font-mono text-yellow-200">
              {codes.map((c) => <span key={c}>{c}</span>)}
            </div>
          </div>
        )}
        <div className="flex gap-2">
          <button onClick={regenerateCodes} className="text-xs text-slate-400 hover:text-slate-200">Regenerate recovery codes</button>
        </div>
        {msg && <div className="text-sm text-slate-300">{msg}</div>}
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold">API keys</h3>
        <p className="text-xs text-slate-500">Programmatic access to the events API: <code>Authorization: Bearer gt_…</code> on <code>GET/POST /api/v1/events</code>. Keys are stored hashed.</p>
        {createdKey && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 text-sm">
            <div className="font-semibold text-yellow-300">New key (shown once):</div>
            <code className="break-all text-xs">{createdKey.key}</code>
          </div>
        )}
        <div className="flex gap-2">
          <input value={keyName} onChange={(e) => setKeyName(e.target.value)} placeholder="Key name (e.g. backup-script)" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          <button onClick={createKey} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2 text-sm">Create</button>
        </div>
        <div className="space-y-2">
          {keys.map((k) => (
            <div key={k.id} className="flex items-center gap-3 text-sm border-b border-slate-800/50 pb-2">
              <code className="text-cyan-300">{k.prefix}…</code>
              <span className="flex-1">{k.name}</span>
              <span className="text-xs text-slate-500">used {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "never"}</span>
              <button onClick={() => revokeKey(k.id)} className="text-xs text-red-400 hover:text-red-300">Revoke</button>
            </div>
          ))}
          {keys.length === 0 && <div className="text-slate-500 text-sm">No API keys.</div>}
        </div>
      </div>

      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold">Change password</h3>
        <p className="text-xs text-slate-500">Changing your password signs you out of every session.</p>
        <div className="flex flex-col md:flex-row gap-2">
          <input type="password" value={pwCur} onChange={(e) => setPwCur(e.target.value)} placeholder="Current password" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          <input type="password" value={pwNew} onChange={(e) => setPwNew(e.target.value)} placeholder="New password (min 8 chars)" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          <button onClick={changePassword} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2 text-sm">Update</button>
        </div>
        {pwMsg && <div className="text-sm text-slate-300">{pwMsg}</div>}
      </div>

      <div className="bg-[#0d1224] border border-red-500/30 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold text-red-300">Delete account</h3>
        <p className="text-xs text-slate-500">Permanently removes your account and every collected event. Connected Google tokens are revoked first. This cannot be undone.</p>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input type="checkbox" checked={confirmDelete} onChange={(e) => setConfirmDelete(e.target.checked)} />
          I understand all data will be permanently deleted
        </label>
        <div className="flex gap-2">
          <input type="password" value={delPw} onChange={(e) => setDelPw(e.target.value)} placeholder="Password" className="bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2 flex-1" />
          <button onClick={deleteAccount} className="bg-red-600 hover:bg-red-500 rounded-lg px-4 py-2 text-sm">Delete my account</button>
        </div>
        {delMsg && <div className="text-sm text-slate-300">{delMsg}</div>}
      </div>
    </div>
  );
}