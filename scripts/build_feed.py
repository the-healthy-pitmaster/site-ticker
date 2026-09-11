#!/usr/bin/env python3
"""Regenerate feed.json for the social ticker (America/Denver).

Always: Mastodon public statuses, YouTube RSS, TILvids recent.
Optional: Metricool multi-network when METRICOOL_* env credentials present.
Preserves non-stale Metricool-sourced items from existing feed.json when Metricool unavailable.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "feed.json"

YT_CHANNEL = "UCFZpCMwcMX6EZicbuG-r6WA"
YT_RSS = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL}"
TILVIDS_API = "https://tilvids.com/api/v1/accounts/therealjimbbq/videos?count=20"
MASTODON_ACCT = "therealjimbbq"
MASTODON_HOST = "https://mastodon.social"
DISPLAY_NAME = "The Healthy Pitmaster"
BLOG_ID = "3895705"
UA = "TheHealthyPitmaster-site-ticker/1.0 (+https://the-healthy-pitmaster.github.io/site-ticker/)"
CLIP = 220
MIN_ITEMS = 15
MAX_ITEMS = 24

PLATFORM_META = {
    "x": {"platformLabel": "X", "handle": "@therealjimbbq", "profileUrl": "https://x.com/therealjimbbq"},
    "facebook": {"platformLabel": "Facebook", "handle": "@therealjimbbq", "profileUrl": "https://www.facebook.com/"},
    "instagram": {"platformLabel": "Instagram", "handle": "@therealjimbbq", "profileUrl": "https://www.instagram.com/therealjimbbq/"},
    "linkedin": {"platformLabel": "LinkedIn", "handle": "@therealjimbbq", "profileUrl": "https://www.linkedin.com/"},
    "tiktok": {"platformLabel": "TikTok", "handle": "@therealjimbbq", "profileUrl": "https://www.tiktok.com/@therealjimbbq"},
    "bluesky": {"platformLabel": "Bluesky", "handle": "@therealjimbbq.bsky.social", "profileUrl": "https://bsky.app/profile/therealjimbbq.bsky.social"},
    "threads": {"platformLabel": "Threads", "handle": "@therealjimbbq", "profileUrl": "https://www.threads.com/@therealjimbbq"},
    "youtube": {"platformLabel": "YouTube", "handle": "@therealjimbbq", "profileUrl": f"https://www.youtube.com/channel/{YT_CHANNEL}"},
    "pinterest": {"platformLabel": "Pinterest", "handle": "@therealjimbbq", "profileUrl": "https://www.pinterest.com/therealjimbbq/"},
    "mastodon": {"platformLabel": "Mastodon", "handle": "@therealjimbbq@mastodon.social", "profileUrl": "https://mastodon.social/@therealjimbbq"},
    "tilvids": {"platformLabel": "TILvids", "handle": "@therealjimbbq", "profileUrl": "https://tilvids.com/a/therealjimbbq/video-channels"},
}


def http_get(url: str, headers: Optional[dict] = None, timeout: int = 45) -> bytes:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str, headers: Optional[dict] = None) -> Any:
    return json.loads(http_get(url, headers=headers).decode("utf-8"))


def clip_text(s: str, n: int = CLIP) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    s = html.unescape(s)
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0] if " " in s[:n] else s[: n - 1]
    return cut.rstrip(",;:") + "…"


def to_denver_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TZ).isoformat()


def parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"\d{14}", s):
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=TZ)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def normalize_item(
    *,
    platform: str,
    item_id: str,
    published_at: str,
    text: str,
    url: str,
    source: str,
    handle: Optional[str] = None,
    profile_url: Optional[str] = None,
) -> dict:
    meta = PLATFORM_META.get(platform, {"platformLabel": platform.title(), "handle": "@therealjimbbq", "profileUrl": url})
    return {
        "platform": platform,
        "platformLabel": meta["platformLabel"],
        "handle": handle or meta["handle"],
        "profileUrl": profile_url or meta["profileUrl"],
        "displayName": DISPLAY_NAME,
        "id": item_id,
        "publishedAt": published_at,
        "text": clip_text(text),
        "url": url,
        "source": source,
    }


# --- Sources -----------------------------------------------------------------

def fetch_mastodon() -> list[dict]:
    try:
        acct = http_get_json(f"{MASTODON_HOST}/api/v1/accounts/lookup?acct={MASTODON_ACCT}")
        aid = acct["id"]
        statuses = http_get_json(f"{MASTODON_HOST}/api/v1/accounts/{aid}/statuses?limit=20&exclude_replies=true&exclude_reblogs=true")
    except Exception as e:
        print(f"Mastodon failed: {e}", file=sys.stderr)
        return []
    out = []
    for st in statuses:
        if st.get("reblog") or st.get("visibility") not in (None, "public", "unlisted"):
            # still allow public/unlisted; skip None carefully
            pass
        if st.get("visibility") not in ("public", "unlisted"):
            continue
        text = st.get("content") or ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        dt = parse_iso(st.get("created_at") or "")
        if not dt:
            continue
        out.append(
            normalize_item(
                platform="mastodon",
                item_id=f"masto-{st.get('id')}",
                published_at=to_denver_iso(dt),
                text=text,
                url=st.get("url") or st.get("uri") or "",
                source="mastodon",
            )
        )
    return out


def fetch_youtube_rss() -> list[dict]:
    try:
        raw = http_get(YT_RSS)
    except Exception as e:
        print(f"YouTube RSS failed: {e}", file=sys.stderr)
        return []
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(raw)
    out = []
    for entry in root.findall("atom:entry", ns)[:12]:
        vid = (entry.find("yt:videoId", ns).text if entry.find("yt:videoId", ns) is not None else "") or ""
        title = (entry.find("atom:title", ns).text if entry.find("atom:title", ns) is not None else "") or ""
        pub = (entry.find("atom:published", ns).text if entry.find("atom:published", ns) is not None else "") or ""
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={vid}"
        desc_el = entry.find("media:group/media:description", ns)
        desc = (desc_el.text if desc_el is not None else "") or title
        dt = parse_iso(pub)
        if not dt or not vid:
            continue
        out.append(
            normalize_item(
                platform="youtube",
                item_id=f"yt-{vid}",
                published_at=to_denver_iso(dt),
                text=desc or title,
                url=link,
                source="youtube-rss",
            )
        )
    return out


def fetch_tilvids() -> list[dict]:
    try:
        data = http_get_json(TILVIDS_API)
    except Exception as e:
        print(f"TILvids failed: {e}", file=sys.stderr)
        return []
    rows = data.get("data") if isinstance(data, dict) else data
    out = []
    for v in (rows or [])[:12]:
        dt = parse_iso(v.get("publishedAt") or v.get("createdAt") or "")
        if not dt:
            continue
        desc = v.get("truncatedDescription") or v.get("description") or v.get("name") or ""
        out.append(
            normalize_item(
                platform="tilvids",
                item_id=f"til-{v.get('shortUUID') or v.get('id')}",
                published_at=to_denver_iso(dt),
                text=desc,
                url=v.get("url") or "",
                source="tilvids",
            )
        )
    return out


def metricool_credentials() -> Optional[tuple[str, str, str]]:
    token = (
        os.environ.get("METRICOOL_USER_TOKEN")
        or os.environ.get("METRICOOL_TOKEN")
        or ""
    ).strip()
    user_id = (os.environ.get("METRICOOL_USER_ID") or "").strip()
    blog_id = (os.environ.get("METRICOOL_BLOG_ID") or BLOG_ID).strip()
    if token and user_id:
        return token, user_id, blog_id
    return None


def fetch_metricool() -> list[dict]:
    creds = metricool_credentials()
    if not creds:
        return []
    token, user_id, blog_id = creds
    end = datetime.now(TZ).date()
    start = end - timedelta(days=14)
    headers = {"X-Mc-Auth": token}
    # Network-specific analytics post endpoints differ; try a few known shapes.
    network_tries = [
        ("twitter", "x", "https://app.metricool.com/api/v2/analytics/posts/twitter"),
        ("instagram", "instagram", "https://app.metricool.com/api/v2/analytics/posts/instagram"),
        ("facebook", "facebook", "https://app.metricool.com/api/v2/analytics/posts/facebook"),
        ("linkedin", "linkedin", "https://app.metricool.com/api/v2/analytics/posts/linkedin"),
        ("bluesky", "bluesky", "https://app.metricool.com/api/v2/analytics/posts/bluesky"),
        ("threads", "threads", "https://app.metricool.com/api/v2/analytics/posts/threads"),
        ("pinterest", "pinterest", "https://app.metricool.com/api/v2/analytics/posts/pinterest"),
        ("tiktok", "tiktok", "https://app.metricool.com/api/v2/analytics/posts/tiktok"),
        ("youtube", "youtube", "https://app.metricool.com/api/v2/analytics/videos/youtube"),
    ]
    out: list[dict] = []
    for net, platform, base in network_tries:
        qs = urllib.parse.urlencode(
            {
                "userId": user_id,
                "blogId": blog_id,
                "from": f"{start.isoformat()}T00:00:00-06:00",
                "to": f"{end.isoformat()}T23:59:59-06:00",
            }
        )
        url = f"{base}?{qs}"
        try:
            data = http_get_json(url, headers=headers)
        except Exception as e:
            print(f"Metricool {net} skipped: {e}", file=sys.stderr)
            continue
        rows = data if isinstance(data, list) else (
            data.get("data") or data.get("rows") or data.get("posts") or data.get("result") or []
        )
        for r in rows:
            try:
                item = _metricool_row_to_item(platform, r)
            except Exception:
                continue
            if item:
                out.append(item)
    return out


def _metricool_row_to_item(platform: str, r: Any) -> Optional[dict]:
    if isinstance(r, list) and len(r) >= 3:
        dt = parse_iso(str(r[0]))
        text = str(r[1] or "")
        raw_id = str(r[2] or "")
        url = ""
        if platform == "x" and raw_id.isdigit():
            url = f"https://x.com/therealjimbbq/status/{raw_id}"
            item_id = f"x-{raw_id}"
        elif platform == "youtube" and "youtube.com" in str(r[2]):
            url = str(r[2])
            m = re.search(r"[?&]v=([\w-]{6,})", url) or re.search(r"youtu\.be/([\w-]{6,})", url)
            item_id = f"yt-{m.group(1)}" if m else f"yt-{raw_id}"
            # list shape for YT from MCP was [date, title, url]
            text = str(r[1] or "")
        else:
            item_id = f"{platform}-{raw_id}"
            url = str(r[2]) if str(r[2]).startswith("http") else ""
        if not dt:
            return None
        return normalize_item(
            platform=platform,
            item_id=item_id,
            published_at=to_denver_iso(dt),
            text=text,
            url=url or PLATFORM_META.get(platform, {}).get("profileUrl", ""),
            source="metricool",
        )
    if isinstance(r, dict):
        text = r.get("text") or r.get("content") or r.get("title") or ""
        url = r.get("url") or r.get("permalink") or ""
        raw_id = str(r.get("id") or r.get("postId") or "")
        dt = parse_iso(str(r.get("publishedAt") or r.get("date") or r.get("datetime") or ""))
        if not dt:
            return None
        if platform == "x" and raw_id and not url:
            url = f"https://x.com/therealjimbbq/status/{re.sub(r'^x-', '', raw_id)}"
        return normalize_item(
            platform=platform,
            item_id=f"{platform}-{raw_id}" if raw_id else f"{platform}-{int(dt.timestamp())}",
            published_at=to_denver_iso(dt),
            text=text,
            url=url or PLATFORM_META.get(platform, {}).get("profileUrl", ""),
            source="metricool",
        )
    return None


def load_preserved_metricool(existing: dict, cutoff: datetime) -> list[dict]:
    """Keep Metricool-sourced items newer than cutoff when live Metricool pull unavailable."""
    out = []
    for it in existing.get("items") or []:
        if it.get("source") != "metricool":
            continue
        dt = parse_iso(it.get("publishedAt") or "")
        if not dt:
            continue
        if dt.astimezone(UTC) >= cutoff.astimezone(UTC):
            # re-normalize clip
            it = dict(it)
            it["text"] = clip_text(it.get("text") or "")
            out.append(it)
    return out


def dedupe_sort(items: list[dict]) -> list[dict]:
    seen = set()
    uniq = []
    for it in items:
        key = (it.get("platform"), it.get("id") or it.get("url"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    def sort_key(it: dict):
        dt = parse_iso(it.get("publishedAt") or "") or datetime(1970, 1, 1, tzinfo=UTC)
        return dt.astimezone(UTC)

    uniq.sort(key=sort_key, reverse=True)
    return uniq


def main() -> int:
    existing = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Could not read existing feed.json: {e}", file=sys.stderr)

    items: list[dict] = []
    items.extend(fetch_mastodon())
    items.extend(fetch_youtube_rss())
    items.extend(fetch_tilvids())

    metricool_items = fetch_metricool()
    if metricool_items:
        items.extend(metricool_items)
        notes_metricool = f"Metricool REST pull ({len(metricool_items)} rows)."
    else:
        cutoff = datetime.now(UTC) - timedelta(days=14)
        preserved = load_preserved_metricool(existing, cutoff)
        items.extend(preserved)
        notes_metricool = (
            f"Metricool unavailable (no METRICOOL_USER_TOKEN/METRICOOL_USER_ID); "
            f"preserved {len(preserved)} Metricool items from existing feed within 14d."
        )

    items = dedupe_sort(items)
    if len(items) > MAX_ITEMS:
        items = items[:MAX_ITEMS]
    # If under MIN_ITEMS, keep more from existing non-metricool older public items
    if len(items) < MIN_ITEMS and existing.get("items"):
        extras = []
        for it in existing["items"]:
            if it.get("source") == "metricool":
                continue
            extras.append(it)
        items = dedupe_sort(items + extras)[:MAX_ITEMS]

    payload = {
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "America/Denver",
        "brand": "The Healthy Pitmaster",
        "blogId": BLOG_ID,
        "displayFormat": "{platformLabel} {displayName} {handle} — {text}",
        "example": "X The Healthy Pitmaster @therealjimbbq — Liver post",
        "notes": [
            f"Refreshed by scripts/build_feed.py. {notes_metricool}",
            "Always includes Mastodon public API + YouTube RSS + TILvids.",
            "Skip empty networks; never invent posts.",
        ],
        "items": items,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(items)} items")
    for it in items[:5]:
        print(f"  {it['platform']:10} {it['publishedAt'][:19]} {it['text'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
