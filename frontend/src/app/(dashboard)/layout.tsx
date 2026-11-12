"use client";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, Shield, Monitor, Server, BarChart3, LogOut, Home, Cog, Menu, X, TrendingUp } from "lucide-react";

const nav = [
  { href: "/overview", label: "Overview", icon: Home },
  { href: "/timeline", label: "Activity Timeline", icon: Activity },
  { href: "/insights", label: "Insights", icon: TrendingUp },
  { href: "/devices", label: "Device Intelligence", icon: Monitor },
  { href: "/security", label: "Security Center", icon: Shield },
  { href: "/integrations", label: "Integrations", icon: Server },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Cog },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, logoutAll } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => { if (!loading && !user) router.push("/login"); }, [loading, user, router]);
  if (loading) return <div className="flex items-center justify-center min-h-screen text-slate-400">Loading…</div>;
  if (!user) return null;
  return (
    <div className="flex min-h-screen">
      {open && (
        <div className="fixed inset-0 bg-black/60 z-40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />
      )}
      <aside className={`w-64 shrink-0 border-r border-slate-800 bg-[#0d1224] flex flex-col fixed md:static inset-y-0 left-0 z-50 transform transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-wider text-cyan-400">GHOSTTRACE</h1>
            <p className="text-xs text-slate-500 mt-1">Personal Intel Platform</p>
          </div>
          <button onClick={() => setOpen(false)} className="md:hidden text-slate-400 hover:text-slate-200" aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 p-3 space-y-1" aria-label="Main navigation">
          {nav.map((n) => {
            const Icon = n.icon;
            const active = pathname === n.href;
            return (
              <Link key={n.href} href={n.href} onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${active ? "bg-cyan-500/10 text-cyan-300" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}>
                <Icon size={18} /> {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <div className="text-xs text-slate-500 mb-2 truncate">{user.email}</div>
          <div className="flex flex-col gap-2">
            <button onClick={logout} className="flex items-center gap-2 text-sm text-slate-400 hover:text-red-400">
              <LogOut size={16} /> Sign out
            </button>
            <button onClick={logoutAll} title="Revokes every session and token, everywhere" className="flex items-center gap-2 text-sm text-slate-500 hover:text-red-400">
              <Shield size={16} /> Sign out everywhere
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-6 overflow-auto">
        <button onClick={() => setOpen(true)} className="md:hidden mb-4 flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200" aria-label="Open menu">
          <Menu size={20} /> Menu
        </button>
        {children}
      </main>
    </div>
  );
}