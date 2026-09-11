# site-ticker — The Healthy Pitmaster

Public GitHub Pages host for the homepage social ticker and dynamic video spots.

**Live:** https://the-healthy-pitmaster.github.io/site-ticker/

## What’s here

| File | Purpose |
|------|---------|
| `feed.json` | Recent social posts for the scrolling ticker |
| `ticker.js` / `ticker.css` / `icons/` | Embeddable ticker widget |
| `videos.json` | Three homepage DYNAMIC VIDEO SPOTs (Today / Yesterday / Two days ago) |
| `videos.js` | Client loader — fills `.replay-card[data-spot]` from `videos.json` |
| `scripts/build_feed.py` | Regenerates `feed.json` |
| `scripts/build_videos.py` | Regenerates `videos.json` |
| `.github/workflows/daily-refresh.yml` | Daily 12:00 UTC refresh + `workflow_dispatch` |

## Videos schema (`videos.json`)

```json
{
  "generatedAt": "ISO-UTC",
  "timezone": "America/Denver",
  "spots": [
    {"spot":1,"dayOffset":0,"platform":"youtube","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false},
    {"spot":2,"dayOffset":1,"platform":"tilvids","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false},
    {"spot":3,"dayOffset":2,"platform":"x","title":"","url":"","embedUrl":"","thumbUrl":"","publishedAt":"","fallback":false}
  ]
}
```

- **Spot 1 (today):** newest YouTube Short (duration ≤60s when API key present; else newest channel RSS item, preferring `/shorts/` links)
- **Spot 2 (yesterday):** newest TILvids (PeerTube `therealjimbbq` on tilvids.com)
- **Spot 3 (two days ago):** newest X video post (Metricool if configured; else public fxtwitter enrich of known status IDs)
- Day matching uses **America/Denver** calendar dates; `fallback: true` means newest on/before the target day

## Actions refresh

Workflow: `.github/workflows/daily-refresh.yml`

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

## Local regenerate

```bash
python3 scripts/build_feed.py
python3 scripts/build_videos.py
```
