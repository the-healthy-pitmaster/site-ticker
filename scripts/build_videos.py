#!/usr/bin/env python3
"""Build videos.json for homepage DYNAMIC VIDEO SPOTs (America/Denver).

Spot 1 (today): newest YouTube Short (fallback: newest YT on/before today)
Spot 2 (yesterday): newest TILvids
Spot 3 (two days ago): newest X video post

Never invent posts. Writes videos.json next to this scripts/ dir's parent.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "videos.json"

YT_CHANNEL = "UCFZpCMwcMX6EZicbuG-r6WA"
YT_RSS = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL}"
TILVIDS_API = "https://tilvids.com/api/v1/accounts/therealjimbbq/videos?count=50"
X_HANDLE = "therealjimbbq"
UA = "TheHealthyPitmaster-site-ticker/1.0 (+https://the-healthy-pitmaster.github.io/site-ticker/)"


def http_get(url: str, headers: Optional[dict] = None, timeout: int = 45) -> bytes:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str, headers: Optional[dict] = None) -> Any:
    return json.loads(http_get(url, headers=headers).decode("utf-8"))


def to_denver_date(dt: datetime) -> datetime.date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TZ).date()


def parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # Metricool compact: 20260910220241
    if re.fullmatch(r"\d{14}", s):
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=TZ)
    return datetime.fromisoformat(s)


def pick_for_day(items: list[dict], target_day, published_key: str = "publishedAt") -> tuple[Optional[dict], bool]:
    """Return (item, fallback). Prefer exact calendar day; else newest on/before."""
    dated = []
    for it in items:
        raw = it.get(published_key) or ""
        try:
            dt = parse_iso(raw) if not isinstance(raw, datetime) else raw
        except Exception:
            continue
        day = to_denver_date(dt)
        dated.append((day, dt, it))
    dated.sort(key=lambda x: x[1], reverse=True)
    exact = [x for x in dated if x[0] == target_day]
    if exact:
        return exact[0][2], False
    before = [x for x in dated if x[0] <= target_day]
    if before:
        return before[0][2], True
    return None, False


def empty_spot(spot: int, day_offset: int, platform: str) -> dict:
    return {
        "spot": spot,
        "dayOffset": day_offset,
        "platform": platform,
        "title": "",
        "url": "",
        "embedUrl": "",
        "thumbUrl": "",
        "publishedAt": "",
        "fallback": False,
    }


# --- YouTube -----------------------------------------------------------------

def fetch_youtube_api() -> list[dict]:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    # search recent uploads, then durations via videos.list
    search_url = (
        "https://www.googleapis.com/youtube/v3/search?"
        + urllib.parse.urlencode(
            {
                "key": key,
                "channelId": YT_CHANNEL,
                "part": "snippet",
                "order": "date",
                "type": "video",
                "maxResults": "25",
            }
        )
    )
    try:
        data = http_get_json(search_url)
    except Exception as e:
        print(f"YouTube API search failed: {e}", file=sys.stderr)
        return []
    ids = [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        return []
    vids_url = (
        "https://www.googleapis.com/youtube/v3/videos?"
        + urllib.parse.urlencode(
            {
                "key": key,
                "id": ",".join(ids),
                "part": "snippet,contentDetails",
            }
        )
    )
    try:
        vdata = http_get_json(vids_url)
    except Exception as e:
        print(f"YouTube API videos failed: {e}", file=sys.stderr)
        return []

    def parse_duration(iso_dur: str) -> int:
        # PT#H#M#S
        m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso_dur or "")
        if not m:
            return 9999
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s

    out = []
    for v in vdata.get("items", []):
        sn = v.get("snippet", {})
        dur = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        vid = v["id"]
        # Prefer Shorts: duration <= 60 OR /shorts/ style (API doesn't mark Shorts reliably)
        out.append(
            {
                "id": vid,
                "title": sn.get("title") or "",
                "url": f"https://www.youtube.com/shorts/{vid}" if dur <= 60 else f"https://www.youtube.com/watch?v={vid}",
                "embedUrl": f"https://www.youtube.com/embed/{vid}",
                "thumbUrl": (sn.get("thumbnails") or {}).get("high", {}).get("url")
                or (sn.get("thumbnails") or {}).get("medium", {}).get("url")
                or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "publishedAt": sn.get("publishedAt") or "",
                "duration": dur,
                "isShort": dur <= 60,
            }
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
        is_short = "/shorts/" in (link or "")
        thumb = thumb_el.get("url") if thumb_el is not None else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        out.append(
            {
                "id": vid,
                "title": (title_el.text if title_el is not None else "") or "",
                "url": link,
                "embedUrl": f"https://www.youtube.com/embed/{vid}",
                "thumbUrl": thumb,
                "publishedAt": (pub_el.text if pub_el is not None else "") or "",
                "duration": 60 if is_short else 999,
                "isShort": is_short,
            }
        )
    return out


def youtube_spot(target_day) -> dict:
    api_items = fetch_youtube_api()
    items = api_items or fetch_youtube_rss()
    shorts = [i for i in items if i.get("isShort") or (i.get("duration") or 999) <= 60]
    pool = shorts if shorts else items
    # Prefer short on exact/fallback day; if shorts pool empty for day, try all then shorts fallback day
    chosen, fb = pick_for_day(shorts if shorts else items, target_day)
    if chosen is None and shorts and items:
        chosen, fb = pick_for_day(items, target_day)
        if chosen and not chosen.get("isShort"):
            # Prefer a short on/before day even if longer video is same day
            short_fb, short_is_fb = pick_for_day(shorts, target_day)
            if short_fb:
                chosen, fb = short_fb, short_is_fb
    spot = empty_spot(1, 0, "youtube")
    if not chosen:
        return spot
    spot.update(
        {
            "title": chosen.get("title") or "",
            "url": chosen.get("url") or "",
            "embedUrl": chosen.get("embedUrl") or "",
            "thumbUrl": chosen.get("thumbUrl") or "",
            "publishedAt": chosen.get("publishedAt") or "",
            "fallback": fb,
        }
    )
    return spot


# --- TILvids -----------------------------------------------------------------

def fetch_tilvids() -> list[dict]:
    try:
        data = http_get_json(TILVIDS_API)
    except Exception as e:
        print(f"TILvids failed: {e}", file=sys.stderr)
        return []
    rows = data.get("data") if isinstance(data, dict) else data
    out = []
    for v in rows or []:
        embed_path = v.get("embedPath") or ""
        thumb_path = v.get("thumbnailPath") or ""
        out.append(
            {
                "title": v.get("name") or "",
                "url": v.get("url") or "",
                "embedUrl": ("https://tilvids.com" + embed_path) if embed_path else "",
                "thumbUrl": ("https://tilvids.com" + thumb_path) if thumb_path else "",
                "publishedAt": v.get("publishedAt") or v.get("createdAt") or "",
            }
        )
    return out


def tilvids_spot(target_day) -> dict:
    items = fetch_tilvids()
    chosen, fb = pick_for_day(items, target_day)
    spot = empty_spot(2, 1, "tilvids")
    if not chosen:
        return spot
    spot.update(
        {
            "title": chosen.get("title") or "",
            "url": chosen.get("url") or "",
            "embedUrl": chosen.get("embedUrl") or "",
            "thumbUrl": chosen.get("thumbUrl") or "",
            "publishedAt": chosen.get("publishedAt") or "",
            "fallback": fb,
        }
    )
    return spot


# --- X / Twitter -------------------------------------------------------------

def metricool_x_posts() -> list[dict]:
    """Best-effort Metricool REST pull when tokens present."""
    token = (
        os.environ.get("METRICOOL_USER_TOKEN")
        or os.environ.get("METRICOOL_TOKEN")
        or os.environ.get("X_MC_AUTH")
        or ""
    ).strip()
    user_id = (os.environ.get("METRICOOL_USER_ID") or "").strip()
    blog_id = (os.environ.get("METRICOOL_BLOG_ID") or "3895705").strip()
    if not token or not user_id:
        return []
    # Common timeline-ish endpoints vary by plan; try tweets analytics export shape.
    end = datetime.now(TZ).date()
    start = end - timedelta(days=14)
    qs = urllib.parse.urlencode(
        {
            "userId": user_id,
            "blogId": blog_id,
            "from": f"{start.isoformat()}T00:00:00-06:00",
            "to": f"{end.isoformat()}T23:59:59-06:00",
            "network": "twitter",
        }
    )
    urls = [
        f"https://app.metricool.com/api/v2/analytics/posts/twitter?{qs}",
        f"https://app.metricool.com/api/stats/timeline/twitterPosts?{qs}",
    ]
    headers = {"X-Mc-Auth": token}
    for url in urls:
        try:
            data = http_get_json(url, headers=headers)
        except Exception as e:
            print(f"Metricool X try failed ({url.split('?')[0]}): {e}", file=sys.stderr)
            continue
        rows = data if isinstance(data, list) else data.get("data") or data.get("rows") or data.get("posts") or []
        out = []
        for r in rows:
            if isinstance(r, list) and len(r) >= 3:
                # [datetime, text, id]
                out.append({"id": str(r[2]), "text": str(r[1]), "publishedAt": str(r[0]), "source": "metricool"})
            elif isinstance(r, dict):
                pid = str(r.get("id") or r.get("postId") or r.get("tweetId") or "")
                out.append(
                    {
                        "id": pid,
                        "text": r.get("text") or r.get("content") or "",
                        "publishedAt": r.get("publishedAt") or r.get("date") or r.get("datetime") or "",
                        "source": "metricool",
                    }
                )
        if out:
            return out
    return []


def fxtwitter_status(tweet_id: str) -> Optional[dict]:
    try:
        data = http_get_json(f"https://api.fxtwitter.com/status/{tweet_id}")
    except Exception:
        return None
    return data.get("tweet") or data


def parse_twitter_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        # "Wed Sep 09 11:31:18 +0000 2026"
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        try:
            return parse_iso(s)
        except Exception:
            return None


def enrich_x_as_video(post: dict) -> Optional[dict]:
    tid = re.sub(r"^x-", "", str(post.get("id") or ""))
    if not tid.isdigit():
        # extract from url
        m = re.search(r"/status/(\d+)", post.get("url") or "")
        tid = m.group(1) if m else ""
    if not tid:
        return None
    tw = fxtwitter_status(tid)
    if not tw:
        # Heuristic from text only when fxtwitter unavailable
        text = post.get("text") or ""
        if not any(k in text.lower() for k in ("broadcast", "/video/", "http")):
            return None
        pub = post.get("publishedAt") or ""
        try:
            dt = parse_iso(pub)
            pub_iso = dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except Exception:
            pub_iso = pub
        return {
            "id": tid,
            "title": (text.split("\n")[0][:120] if text else f"X post {tid}"),
            "url": f"https://x.com/{X_HANDLE}/status/{tid}",
            "embedUrl": f"https://platform.twitter.com/embed/Tweet.html?id={tid}",
            "thumbUrl": "",
            "publishedAt": pub_iso,
            "hasVideo": False,
            "videoIndicators": True,
        }
    media = tw.get("media") or {}
    videos = media.get("videos") or []
    text = tw.get("text") or post.get("text") or ""
    indicators = bool(videos) or ("broadcasts" in text) or ("/i/broadcasts/" in text)
    # Also treat twitter_card player as video-ish
    card = tw.get("twitter_card")
    if isinstance(card, dict) and "player" in json.dumps(card).lower():
        indicators = True
    if not indicators and not videos:
        return None
    created = parse_twitter_date(tw.get("created_at") or "")
    pub_iso = created.astimezone(UTC).isoformat().replace("+00:00", "Z") if created else (post.get("publishedAt") or "")
    thumb = ""
    if videos:
        thumb = videos[0].get("thumbnail_url") or videos[0].get("url") or ""
    elif media.get("photos"):
        thumb = (media["photos"][0] or {}).get("url") or ""
    title = text.split("\n")[0].strip()[:120] if text else f"X video {tid}"
    return {
        "id": tid,
        "title": title,
        "url": tw.get("url") or f"https://x.com/{X_HANDLE}/status/{tid}",
        "embedUrl": f"https://platform.twitter.com/embed/Tweet.html?id={tid}",
        "thumbUrl": thumb,
        "publishedAt": pub_iso,
        "hasVideo": bool(videos),
        "videoIndicators": True,
    }


def candidate_x_ids_from_public() -> list[dict]:
    """Collect recent status IDs from Metricool-shaped env dump, local feed, and lightweight public hints."""
    posts: list[dict] = []
    posts.extend(metricool_x_posts())

    # Optional committed seed of recent status IDs (public); never invent content
    seed_path = Path(__file__).resolve().parent / "x-id-seed.txt"
    if seed_path.exists():
        for tid in re.findall(r"\d{15,}", seed_path.read_text()):
            posts.append({"id": tid, "text": "", "publishedAt": "", "source": "seed"})

    # Preserve / merge IDs from existing feed.json in repo
    feed_path = ROOT / "feed.json"
    if feed_path.exists():
        try:
            feed = json.loads(feed_path.read_text())
            for it in feed.get("items") or []:
                if it.get("platform") != "x":
                    continue
                pid = str(it.get("id") or "")
                m = re.search(r"(\d{15,})", pid + " " + (it.get("url") or ""))
                if not m:
                    continue
                posts.append(
                    {
                        "id": m.group(1),
                        "text": it.get("text") or "",
                        "publishedAt": it.get("publishedAt") or "",
                        "url": it.get("url") or "",
                        "source": "feed",
                    }
                )
        except Exception as e:
            print(f"feed.json X read failed: {e}", file=sys.stderr)

    # Deduplicate by id
    seen = set()
    uniq = []
    for p in posts:
        tid = re.sub(r"^x-", "", str(p.get("id") or ""))
        m = re.search(r"(\d{15,})", tid)
        if not m:
            continue
        tid = m.group(1)
        if tid in seen:
            continue
        seen.add(tid)
        p = dict(p)
        p["id"] = tid
        uniq.append(p)
    return uniq


def discover_more_x_ids(seed_ids: list[str], limit: int = 40) -> list[str]:
    """Walk nearby numeric IDs is unsafe. Instead expand via fxtwitter on seeds only."""
    return seed_ids[:limit]


def fetch_x_videos() -> list[dict]:
    candidates = candidate_x_ids_from_public()
    # Also try a few known recent Metricool IDs if env provided a JSON blob
    extra = os.environ.get("X_STATUS_IDS", "").strip()
    if extra:
        for tid in re.findall(r"\d{15,}", extra):
            candidates.append({"id": tid, "text": "", "publishedAt": ""})

    videos = []
    for p in candidates:
        try:
            v = enrich_x_as_video(p)
        except Exception as e:
            print(f"X enrich {p.get('id')}: {e}", file=sys.stderr)
            continue
        if v:
            videos.append(v)
    # Prefer native videos over broadcast-only when sorting later; keep all with indicators
    videos.sort(key=lambda x: x.get("publishedAt") or "", reverse=True)
    return videos


def x_spot(target_day) -> dict:
    items = fetch_x_videos()
    # Prefer hasVideo True
    native = [i for i in items if i.get("hasVideo")]
    pool = native if native else items
    chosen, fb = pick_for_day(pool, target_day)
    if chosen is None and native is not pool:
        chosen, fb = pick_for_day(items, target_day)
    spot = empty_spot(3, 2, "x")
    if not chosen:
        return spot
    spot.update(
        {
            "title": chosen.get("title") or "",
            "url": chosen.get("url") or "",
            "embedUrl": chosen.get("embedUrl") or "",
            "thumbUrl": chosen.get("thumbUrl") or "",
            "publishedAt": chosen.get("publishedAt") or "",
            "fallback": fb,
        }
    )
    return spot


def main() -> int:
    now = datetime.now(TZ)
    today = now.date()
    spots = [
        youtube_spot(today),
        tilvids_spot(today - timedelta(days=1)),
        x_spot(today - timedelta(days=2)),
    ]
    payload = {
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "America/Denver",
        "spots": spots,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    for s in spots:
        print(
            f"  spot {s['spot']} {s['platform']}: "
            f"{(s['title'] or '(empty)')[:60]} fallback={s['fallback']} {s['url']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
