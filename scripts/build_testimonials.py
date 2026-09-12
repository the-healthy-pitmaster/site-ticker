#!/usr/bin/env python3
"""Build testimonials.json from Jim's Feel Great Stories YouTube playlist RSS.

Fetches playlist RSS, parses videoId + title, dedupes near-duplicates
(same title ignoring punctuation / Unicity variants — keep newest id),
writes testimonials.json for homepage Real Stories cards.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "testimonials.json"

PLAYLIST_ID = "PLz8OCtggaTtLMHoDs-ntLo44xOmjm1e85"
PLAYLIST_URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?playlist_id={PLAYLIST_ID}"
UA = "TheHealthyPitmaster-site-ticker/1.0 (+https://the-healthy-pitmaster.github.io/site-ticker/)"


def http_get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def normalize_title_key(title: str) -> str:
    """Dedupe key: ignore punctuation and Unicity variants."""
    t = (title or "").lower()
    t = re.sub(r"\bunicity\b", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_iso(s: str) -> datetime:
    s = (s or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def fetch_playlist_rss() -> list[dict]:
    try:
        raw = http_get(RSS_URL)
    except Exception as e:
        print(f"Playlist RSS failed: {e}", file=sys.stderr)
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(raw)
    out: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        vid_el = entry.find("yt:videoId", ns)
        title_el = entry.find("atom:title", ns)
        pub_el = entry.find("atom:published", ns)
        link_el = entry.find("atom:link", ns)
        thumb_el = entry.find("media:group/media:thumbnail", ns)
        vid = (vid_el.text if vid_el is not None else "") or ""
        if not vid:
            continue
        link = link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={vid}"
        # Prefer watch URL for click-out (shorts links still work on YT)
        watch = f"https://www.youtube.com/watch?v={vid}"
        thumb = (
            thumb_el.get("url")
            if thumb_el is not None
            else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        )
        published = (pub_el.text if pub_el is not None else "") or ""
        title = (title_el.text if title_el is not None else "") or ""
        out.append(
            {
                "id": vid,
                "title": title,
                "url": watch if "/shorts/" in (link or "") or not link else (link or watch),
                "embedUrl": f"https://www.youtube.com/embed/{vid}",
                "thumbUrl": thumb,
                "publishedAt": published,
            }
        )
    # Normalize url to watch for consistency
    for it in out:
        it["url"] = f"https://www.youtube.com/watch?v={it['id']}"
    return out


def dedupe_keep_newest(items: list[dict]) -> list[dict]:
    """Same title ignoring punctuation / Unicity — keep newest published id."""
    best: dict[str, dict] = {}
    for it in items:
        key = normalize_title_key(it.get("title") or "")
        if not key:
            key = f"id:{it.get('id')}"
        prev = best.get(key)
        if prev is None:
            best[key] = it
            continue
        try:
            dt_new = parse_iso(it.get("publishedAt") or "")
            dt_old = parse_iso(prev.get("publishedAt") or "")
            if dt_new >= dt_old:
                best[key] = it
        except Exception:
            # Prefer the one that appears first in RSS (typically newest)
            # Only replace if we can't parse old but can parse new
            try:
                parse_iso(it.get("publishedAt") or "")
                best[key] = it
            except Exception:
                pass
    # Preserve newest-first order by publishedAt
    merged = list(best.values())

    def sort_key(x: dict):
        try:
            return parse_iso(x.get("publishedAt") or "")
        except Exception:
            return datetime.min.replace(tzinfo=UTC)

    merged.sort(key=sort_key, reverse=True)
    return merged


def main() -> int:
    raw_items = fetch_playlist_rss()
    items = dedupe_keep_newest(raw_items)
    payload_items = [
        {
            "id": it["id"],
            "title": it["title"],
            "url": it["url"],
            "embedUrl": it["embedUrl"],
            "thumbUrl": it["thumbUrl"],
        }
        for it in items
    ]
    payload = {
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "playlistId": PLAYLIST_ID,
        "playlistUrl": PLAYLIST_URL,
        "timezone": "America/Denver",
        "items": payload_items,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  raw RSS entries: {len(raw_items)}")
    print(f"  after dedupe:    {len(payload_items)}")
    for it in payload_items:
        print(f"  - {it['id']}  {it['title'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
