"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { errDetail } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try { await login(email, password); router.push("/overview"); }
    catch (x) { setErr(errDetail(x, "Login failed")); }
    finally { setLoading(false); }
  };
  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={submit} className="w-full max-w-md bg-[#0d1224] border border-slate-800 rounded-xl p-8 space-y-4">
        <h1 className="text-2xl font-bold text-cyan-400">GHOSTTRACE</h1>
        <p className="text-slate-500 text-sm">Sign in to your intelligence platform</p>
        <input className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input type="password" className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)} />
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button disabled={loading} className="w-full bg-cyan-600 hover:bg-cyan-500 rounded-lg py-2 font-medium disabled:opacity-50">{loading?"Signing in…":"Sign in"}</button>
        <p className="text-sm text-slate-500">No account? <Link href="/register" className="text-cyan-400">Register</Link></p>
      </form>
    </div>
  );
}
