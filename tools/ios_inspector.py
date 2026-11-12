#!/usr/bin/env python3
"""iPhone USB inspector -> GHOSTTRACE telemetry.

Reads real device state over USB using pymobiledevice3 (your own, trusted device)
and pushes it to the GHOSTTRACE /devices/telemetry endpoint.

Setup:
    pip install pymobiledevice3
    # Windows/macOS: keep iTunes/Apple Mobile Device Support running
    # Linux: sudo systemctl start usbmuxd

Usage:
    python ios_inspector.py --backend http://localhost:8000 --device-key gt_XXXX
    python ios_inspector.py ... --interval 60        # continuous
    python ios_inspector.py ... --once

The device key comes from Devices page -> Register iOS Device.
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

try:
    from pymobiledevice3.lockdown import create_using_usbmux
except ImportError:
    sys.exit("pymobiledevice3 not installed. Run: pip install pymobiledevice3")


def collect(lockdown) -> dict:
    vals = lockdown.all_values
    out = {
        "device_name": vals.get("DeviceName"),
        "model": vals.get("ProductType"),
        "ios_version": vals.get("ProductVersion"),
        "build": vals.get("BuildVersion"),
        "udid": vals.get("UniqueDeviceID"),
        "capacity_gb": round((vals.get("TotalDiskCapacity") or 0) / 1e9, 1),
    }
    # Battery needs the diagnostics service; best-effort.
    try:
        from pymobiledevice3.services.diagnostics import DiagnosticsService
        with DiagnosticsService(lockdown) as diag:
            batt = diag.battery_status or {}
            out["battery_level"] = batt.get("CurrentCapacity")
            out["battery_state"] = batt.get("ExternalConnected") and "charging" or "on battery"
    except Exception as e:
        out["battery_error"] = str(e)[:80]
    return out


def push(backend: str, device_key: str, payload: dict) -> int:
    req = urllib.request.Request(
        f"{backend}/api/v1/devices/telemetry",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Device-Key": device_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", default="http://localhost:8000")
    ap.add_argument("--device-key", required=True)
    ap.add_argument("--interval", type=int, default=0, help="seconds between pushes; 0 = once")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    lockdown = create_using_usbmux()
    print(f"Connected: {lockdown.display_name} ({lockdown.product_type})")

    while True:
        info = collect(lockdown)
        now = datetime.now(timezone.utc).isoformat()
        events = [{
            "application": "iOS Device",
            "event_type": "device.inspection",
            "category": "device",
            "timestamp": now,
            "description": f"{info['device_name']} on iOS {info['ios_version']}",
            "metadata": info,
            "dedup_key": f"ios-inspect:{now}",
        }]
        payload = {
            "os_version": info.get("ios_version"),
            "app_version": "ios_inspector/1.0",
            "events": events,
        }
        if info.get("battery_level") is not None:
            payload["battery_level"] = info["battery_level"]
        status = push(args.backend, args.device_key, payload)
        print(f"[{now}] pushed (HTTP {status}) battery={info.get('battery_level')}% model={info.get('model')}")
        if args.once or args.interval <= 0:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()