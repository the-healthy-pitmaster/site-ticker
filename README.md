# Healthy Pitmaster — site ticker

Public static assets for the homepage social ticker.

## GitHub Pages

Enable Pages on this repo (Settings → Pages → Deploy from branch `main` / root).

Public base (after Pages is live):
`https://the-healthy-pitmaster.github.io/site-ticker/`

## Embed (GHL)

```html
<div id="thp-ticker"
     data-feed="https://the-healthy-pitmaster.github.io/site-ticker/feed.json"
     data-asset-base="https://the-healthy-pitmaster.github.io/site-ticker/"
     data-position="inline"
     data-speed="60"></div>
<link rel="stylesheet" href="https://the-healthy-pitmaster.github.io/site-ticker/ticker.css">
<script src="https://the-healthy-pitmaster.github.io/site-ticker/ticker.js" defer></script>
```

Do **not** inline `ticker.js` inside a Custom Code `<script>` block that still contains a literal `</script>` in a comment — that dumps source as visible text.

Owned by Jim Grasser / org `the-healthy-pitmaster`.
