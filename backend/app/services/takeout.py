"""Google Takeout importer.

Parses a Takeout ZIP (as exported from takeout.google.com) and turns the
highest-value datasets into unified events:

- Location History/Records.json            raw GPS points (timestamp, lat, lng, accuracy)
- Location History/SemanticLocationHistory.json  inferred place visits ("Home", "Office", ...)
- My Activity/**/*.json                    per-product activity entries (title/time)
- YouTube and YouTube Music/history/history-and-search-activity.json  watch history

Only metadata is stored; no file contents are kept beyond what these
activity records themselves contain.
"""
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger("ghosttrace.takeout")

MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # zip-bomb guard


def _ms_to_dt(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _to_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _parse_iso(s) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _entry_hash(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:24]


def _iter_json_members(zf: zipfile.ZipFile):
    for info in zf.infolist():
        if info.is_dir() or not info.filename.lower().endswith(".json"):
            continue
        if info.file_size > 200 * 1024 * 1024:
            logger.warning("skipping oversized takeout member %s", info.filename)
            continue
        try:
            with zf.open(info) as fh:
                yield info.filename, json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("takeout member %s not parseable: %s", info.filename, e)


def import_takeout(db: Session, user_id: str, raw: bytes) -> dict:
    from app.services.events import ingest_event

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return {"ok": False, "error": "not a valid zip file"}

    total_uncompressed = sum(i.file_size for i in zf.infolist())
    if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
        return {"ok": False, "error": "takeout zip too large (>500MB uncompressed)"}

    counts = {"locations": 0, "place_visits": 0, "activities": 0, "youtube": 0}

    for name, data in _iter_json_members(zf):
        n = name.replace("\\", "/")
        if n.endswith("Location History/Records.json"):
            for loc in (data or {}).get("locations", []):
                dt = _ms_to_dt(loc.get("timestampMs"))
                if dt is None or loc.get("latitudeE7") is None:
                    continue
                lat, lng = loc["latitudeE7"] / 1e7, loc["longitudeE7"] / 1e7
                ingest_event(
                    db, user_id, source="google_takeout", integration_kind="takeout",
                    event_type="location.point", category="location",
                    description=f"Location {lat:.4f}, {lng:.4f} (±{loc.get('accuracy', '?')}m)",
                    timestamp=dt,
                    metadata={"latitude": lat, "longitude": lng, "accuracy": loc.get("accuracy"),
                              "source": "takeout:Location History"},
                    collection_method="takeout_import", permission_status="authorized", confidence=1.0,
                    dedup_key=f"takeout:loc:{loc.get('timestampMs')}:{round(lat, 4)}:{round(lng, 4)}",
                )
                counts["locations"] += 1

        elif n.endswith("Location History/SemanticLocationHistory.json"):
            for pl in (data or {}).get("placements", []):
                start = _ms_to_dt(pl.get("startTimestampMs"))
                if start is None:
                    continue
                atts = pl.get("placeAttendances") or []
                top = atts[0] if atts else {}
                conf = (top.get("location", {}).get("locationContextConfidenceLocations") or [{}])[0].get("confidence")
                lat = (top.get("location", {}).get("latLng") or {}).get("latitude", 0) / 1e7
                lng = (top.get("location", {}).get("latLng") or {}).get("longitude", 0) / 1e7
                names = [a.get("structuredAttribution", {}).get("center", {}).get("name")
                         for a in atts if a.get("structuredAttribution", {}).get("center", {}).get("name")]
                place = names[0] if names else "unknown place"
                end = _ms_to_dt(pl.get("endTimestampMs"))
                ingest_event(
                    db, user_id, source="google_takeout", integration_kind="takeout",
                    event_type="location.place_visit", category="location",
                    description=f"At {place}" + (f" until {end.isoformat()}" if end else ""),
                    timestamp=start,
                    metadata={"place": place, "candidates": names, "confidence": conf,
                              "latitude": lat, "longitude": lng,
                              "duration_ms": _to_int(pl.get("endTimestampMs")) - _to_int(pl.get("startTimestampMs")),
                              "source": "takeout:SemanticLocationHistory"},
                    collection_method="takeout_import", permission_status="authorized", confidence=0.9,
                    dedup_key=f"takeout:place:{pl.get('startTimestampMs')}:{pl.get('placeId', _entry_hash(place, start))}",
                )
                counts["place_visits"] += 1

        elif n.endswith("history-and-search-activity.json") and "YouTube" in n:
            for item in (data or {}).get("items", []):
                dt = _parse_iso(item.get("creationTimestamp"))
                title = item.get("description") or "YouTube activity"
                details = {d.get("name"): d.get("value") for d in item.get("details", []) if isinstance(d, dict)}
                video = details.get("Name") or ""
                ingest_event(
                    db, user_id, source="google_takeout", integration_kind="takeout",
                    event_type="youtube.watch", category="media",
                    description=f"{title}: {video}" if video else title,
                    timestamp=dt,
                    metadata={"subpair": item.get("header"), "video": video,
                              "source": "takeout:YouTube"},
                    collection_method="takeout_import", permission_status="authorized", confidence=1.0,
                    dedup_key=f"takeout:yt:{_entry_hash(video, dt)}",
                )
                counts["youtube"] += 1

        elif n.startswith("My Activity/") or "/My Activity/" in n:
            entries = data if isinstance(data, list) else (data or {}).get("activities", [])
            for item in entries:
                if not isinstance(item, dict):
                    continue
                dt = _parse_iso(item.get("time"))
                title = item.get("title") or item.get("name")
                if not title or dt is None:
                    continue
                products = item.get("products") or []
                ingest_event(
                    db, user_id, source="google_takeout", integration_kind="takeout",
                    event_type="activity.entry", category="activity",
                    description=title,
                    timestamp=dt,
                    metadata={"products": products, "source": "takeout:My Activity"},
                    collection_method="takeout_import", permission_status="authorized", confidence=1.0,
                    dedup_key=f"takeout:act:{_entry_hash(title, dt.isoformat())}",
                )
                counts["activities"] += 1

    return {"ok": True, **counts, "total_ingested": sum(counts.values())}