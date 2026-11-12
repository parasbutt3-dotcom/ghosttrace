"use client";
import { useState } from "react";
import { authApi, errDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function MfaPage() {
  const router = useRouter();
  const { completeLogin } = useAuth();
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      const mt = sessionStorage.getItem("mfa_token") || "";
      const r = await authApi.mfaLogin(mt, code);
      sessionStorage.removeItem("mfa_token");
      await completeLogin(r.data.access_token, r.data.refresh_token);
      router.push("/overview");
    } catch (x) {
      setErr(errDetail(x, "MFA verification failed"));
    } finally { setLoading(false); }
  };
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-md bg-[#0d1224] border border-slate-800 rounded-xl p-8 space-y-4">
        <h1 className="text-2xl font-bold text-cyan-400">Two-factor authentication</h1>
        <p className="text-slate-500 text-sm">Enter the code from your authenticator app, or a recovery code.</p>
        <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="6-digit code or recovery code" className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" />
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button disabled={loading} className="w-full bg-cyan-600 hover:bg-cyan-500 rounded-lg py-2 font-medium disabled:opacity-50">{loading ? "Verifying…" : "Verify"}</button>
      </form>
    </div>
  );
}