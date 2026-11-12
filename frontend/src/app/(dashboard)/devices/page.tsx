"use client";
import { useEffect, useState } from "react";
import { devicesApi } from "@/lib/api";
import type { Device } from "@/lib/types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const load = () => devicesApi.list().then((r) => setDevices(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const register = async (deviceType = "android", platform = "Android") => {
    if (!name) return;
    const r = await devicesApi.register(name, deviceType, platform);
    setKey(r.data.device_key);
    load();
  };
  const copyKey = async () => {
    try { await navigator.clipboard.writeText(key); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Device Intelligence</h2>
      <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-5 flex flex-col md:flex-row gap-2 md:items-end">
        <div className="flex-1">
          <label className="text-xs text-slate-500" htmlFor="device-name">Device name</label>
          <input id="device-name" value={name} onChange={(e) => setName(e.target.value)} className="w-full bg-[#0a0e1a] border border-slate-700 rounded-lg px-3 py-2" />
        </div>
        <button onClick={() => register()} className="bg-cyan-600 hover:bg-cyan-500 rounded-lg px-4 py-2">Register Android Device</button>
        <button onClick={() => register("ios", "iOS")} className="bg-violet-600 hover:bg-violet-500 rounded-lg px-4 py-2">Register iPhone</button>
      </div>
      {key && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 text-sm">
          <div className="font-semibold text-yellow-300">Device key (save on device, shown once):</div>
          <div className="flex items-center gap-2">
            <code className="break-all text-xs">{key}</code>
            <button onClick={copyKey} className="text-xs text-cyan-400 hover:text-cyan-300 shrink-0">{copied ? "Copied!" : "Copy"}</button>
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {devices.map((d) => (
          <div key={d.id} className="bg-[#0d1224] border border-slate-800 rounded-xl p-5">
            <div className="flex justify-between">
              <div className="font-semibold">{d.name}</div>
              <span className="text-xs text-slate-500">{d.status}</span>
            </div>
            <div className="text-xs text-slate-400 mt-2 space-y-1">
              <div>Type: {d.device_type} · {d.platform}</div>
              <div>Battery: {d.battery_level ?? "—"}% · Network: {d.network_type ?? "—"}</div>
              <div>Last seen: {d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "never"}</div>
              {d.last_location && <div>Location: {JSON.stringify(d.last_location)}</div>}
            </div>
            <button onClick={() => { devicesApi.delete(d.id).then(load); }} className="mt-3 text-xs text-red-400 hover:text-red-300">Remove</button>
          </div>
        ))}
      </div>
      {devices.length === 0 && <div className="text-slate-500 text-sm">No devices registered.</div>}
    </div>
  );
}