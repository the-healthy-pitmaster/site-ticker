# site-ticker — The Healthy Pitmaster

Public GitHub Pages host for the homepage social ticker and dynamic video spots.

**Live:** https://the-healthy-pitmaster.github.io/site-ticker/

## What’s here

| File | Purpose |
|------|---------|
| `feed.json` | Recent social posts for the scrolling ticker |
| `ticker.js` / `ticker.css` / `icons/` | Embeddable ticker widget |
| `videos.json` | Three homepage DYNAMIC VIDEO SPOTs (Today / Yesterday / Two days ago) |
| `videos.js` | Client loader — fills `.replay-card[data-spot]` from `videos.json`; also loads `live-box.js` |
| `live-box.js` | Live video box — turns the homepage "Upcoming Event" card into a live player / next-show flyer |
| `shows.json` | Weekly live-show schedule (Mountain Time) + flyer per show, for the live video box |
| `flyers/` | Web-sized show flyers referenced by `shows.json` |
| `scripts/set_flyer.py` | Swap (or clear) one show's flyer: resizes, writes `flyers/<id>.jpg`, updates `shows.json` |
| `scripts/build_feed.py` | Regenerates `feed.json` |
| `scripts/build_videos.py` | Regenerates `videos.json` |
| `scripts/daily-refresh.yml` | Workflow YAML (move to `.github/workflows/` once PAT has `workflow` scope) |

## Live video box (`live-box.js`)

The homepage "Upcoming Event" card (`.live-grid .event-card`) shows, in priority order:

1. **Live player** while Jim is live — PeerTube permanent live (`peertube.wtf/w/1gBXURNMWzNVLeTzEMMRN6`) first,
   YouTube channel live as backup. Muted autoplay in the box, "Tap for sound", and "Watch bigger" opens a popup
   with sound (closing it removes the big player).
2. **Next show's flyer** (from `shows.json`) with its day/time in MT; tapping opens the flyer in the same popup.
   A show stays "next" until `start + durationMinutes` (default 90) so a late stream still shows its flyer.
3. **The normal event card, untouched**, when the next show has no flyer (e.g. `"flyer": ""`).

Live status comes from Barry `GET https://barry-production-c225.up.railway.app/api/live-status` (server checks
PeerTube's public API and YouTube's public `/channel/<id>/live` page, cached 60 s; no API quota, no keys). If
Barry can't be reached the box asks PeerTube's public API directly. Polls once a minute while the tab is visible.
No stream keys anywhere; only public watch ids.

Weekly Trent flyer: `python3 scripts/set_flyer.py trent path/to/flyer.jpg`, then commit + push `shows.json` and
`flyers/trent.jpg`. Same for any show (`dr-nick`, `dr-dieter`, `two-sista-docs`); `--clear` removes a flyer.

Jim can also upload, crop or remove a flyer in Barry admin (**Show flyers**, `/admin/show-flyers`). The box reads
Barry's `GET /api/live-shows` first: that is this `shows.json` with Jim's admin choices merged in, and the **newest
change wins** (an admin choice remembers which `?v=` flyer the site had; a later `set_flyer.py` push has a new `?v=`
and takes over). If Barry can't be reached the box reads `shows.json` here directly, so `set_flyer.py` keeps working
exactly as before.

## Videos schema (`videos.json`)

```json
{
  "generatedAt": "ISO-UTC",
  "timezone": "America/Denver",
  "spots": [
    {"spot":1,"dayOffset":0,"platform":"youtube","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false},
    {"spot":2,"dayOffset":1,"platform":"peertube","source":"peertube","channelUrl":"https://peertube.wtf/c/therealjimbbq_channel","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false},
    {"spot":3,"dayOffset":2,"platform":"x","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false}
  ]
}
```

- **Spot 1 (today):** newest YouTube Short (duration ≤60s when API key present; else newest channel RSS item, preferring `/shorts/` links)
- **Spot 2 (yesterday):** newest PeerTube video from https://peertube.wtf/c/therealjimbbq_channel (`platform: "peertube"`, link `https://peertube.wtf/w/<id>`). While the PeerTube channel has fewer videos than `PEERTUBE_SLOTS` (1), the gap is filled with the newest TILvids video **not already on PeerTube** (matched by title; `platform: "tilvids"`, `source: "tilvids-fill"`). Once PeerTube has enough, it's PeerTube-only automatically and TILvids isn't even fetched. `channelUrl` always points to the PeerTube channel.
- **Spot 3 (two days ago):** newest X video post (Metricool if configured; else public fxtwitter enrich of known status IDs)
- Day matching uses **America/Denver** calendar dates; `fallback: true` means newest on/before the target day

## Actions refresh

Workflow source: `scripts/daily-refresh.yml` → copy to `.github/workflows/daily-refresh.yml` (requires GitHub PAT **workflow** scope to commit under `.github/workflows/`)

- Cron: `0 12 * * *` (12:00 UTC ≈ 6:00 AM MT)
- Also runnable via **Actions → Daily ticker + videos refresh → Run workflow**
- Commits as `github-actions[bot]` when `feed.json` / `videos.json` change

### Optional repo secrets

| Secret | Used for |
|--------|----------|
| `YOUTUBE_API_KEY` | Prefer Shorts by duration via YouTube Data API (else RSS) |
| `METRICOOL_USER_TOKEN` or `METRICOOL_TOKEN` | Multi-network feed pull + richer X video discovery |
| `METRICOOL_USER_ID` | Required with Metricool token (`X-Mc-Auth` + `userId` + `blogId`) |
| `METRICOOL_BLOG_ID` | Defaults to `3895705` if unset |

Without Metricool secrets, feed still refreshes from **Mastodon + YouTube RSS + TILvids**, and keeps recent Metricool-sourced rows already in `feed.json` (≤14 days).

## Homepage wiring

```html
<div class="replay-grid"
     data-videos-feed="https://the-healthy-pitmaster.github.io/site-ticker/videos.json">
  <a class="replay-card" id="video-spot-1" data-spot="1" …>…</a>
  …
</div>
<script src="https://the-healthy-pitmaster.github.io/site-ticker/videos.js" defer></script>
```

Ticker mount (unchanged):

```html
<div id="thp-ticker"
     data-feed="https://the-healthy-pitmaster.github.io/site-ticker/feed.json"
     data-asset-base="https://the-healthy-pitmaster.github.io/site-ticker/"
     data-position="inline"></div>
<script src="https://the-healthy-pitmaster.github.io/site-ticker/ticker.js" defer></script>
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Local regenerate

```bash
python3 scripts/build_feed.py
python3 scripts/build_videos.py
```

## Phone hero fix (`ticker.css`, bottom)

The homepage hero CSS lives in the GHL page, but `ticker.css` is loaded on the homepage, so the phone hero
override rides here. At 860px and narrower the hero photo (gold script logo baked into a wide 16:9 image) is shown
whole across the top, with the headline and Start Here button underneath, instead of being zoomed into a tall box
that cut off the logo. Scoped to `.hero-bg[aria-label="Jim Grasser in a professional kitchen"]`; desktop untouched.
