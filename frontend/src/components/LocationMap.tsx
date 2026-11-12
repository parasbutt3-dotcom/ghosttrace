"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { eventsApi } from "@/lib/api";
import type { EventItem } from "@/lib/types";

interface MarkerPoint {
  id: string;
  lat: number;
  lng: number;
  title: string;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function extractCoords(meta: Record<string, unknown> | null | undefined): { lat: number; lng: number } | null {
  if (!meta) return null;
  const lat = toNumber(meta.latitude ?? meta.lat);
  const lng = toNumber(meta.longitude ?? meta.lng ?? meta.lon);
  if (lat === null || lng === null) return null;
  return { lat, lng };
}

export default function LocationMap() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const [points, setPoints] = useState<MarkerPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    eventsApi
      .list({ limit: 500 })
      .then((r) => {
        if (cancelled) return;
        const next: MarkerPoint[] = [];
        for (const e of r.data.items as EventItem[]) {
          const coords = extractCoords(e.metadata ?? undefined);
          if (!coords) continue;
          next.push({
            id: e.id,
            lat: coords.lat,
            lng: coords.lng,
            title: `${e.event_type} · ${new Date(e.timestamp).toLocaleString()}`,
          });
        }
        setPoints(next);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load location events.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { zoomControl: true }).setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    for (const p of points) {
      const marker = L.circleMarker([p.lat, p.lng], {
        radius: 6,
        color: "#22d3ee",
        fillColor: "#22d3ee",
        fillOpacity: 0.8,
        weight: 1,
      });
      marker.bindPopup(p.title);
      layer.addLayer(marker);
    }
    if (points.length > 0) {
      const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng] as [number, number]));
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
    }
  }, [points]);

  return (
    <div className="bg-[#0d1224] border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Location map</h3>
        <span className="text-xs text-slate-500">{loading ? "Loading…" : `${points.length} markers`}</span>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <div ref={containerRef} className="h-96 w-full rounded-lg overflow-hidden" />
    </div>
  );
}