
// Coming-soon hook (Jim 2026-09-08): While you’re waiting for this amazing page, check out some of our social media posts!
/**
 * The Healthy Pitmaster — scrolling social ticker
 * Loads feed.json and renders: [logo] Platform DisplayName @handle — post text
 *
 * Usage (GHL Custom Code / HTML element):
 *   <div id="thp-ticker" data-feed="https://YOUR-HOST/ticker/feed.json" data-asset-base="https://YOUR-HOST/ticker/" data-position="top"></div>
 *   <link rel="stylesheet" href="https://YOUR-HOST/ticker/ticker.css">
 *   <script src="https://YOUR-HOST/ticker/ticker.js" defer><\/script>
 */
(function () {
  'use strict';

  var ROOT_ID = 'thp-ticker';
  var DEFAULT_SPEED = 69; // ~25% slower than 55 // seconds per loop


  // Fresh copy built daily by the Barry service (has the Metricool keys for X/IG/FB);
  // falls back to the GitHub Pages copy if that service is slow or down.
  var LIVE_BASE = 'https://barry-production-c225.up.railway.app/site-ticker/';
  function fetchJsonWithFallback(primary, fallback) {
    function get(url, ms) {
      var ctl = window.AbortController ? new AbortController() : null;
      var t = ctl ? setTimeout(function () { ctl.abort(); }, ms) : null;
      return fetch(url, { credentials: 'omit', cache: 'no-cache', signal: ctl ? ctl.signal : undefined })
        .then(function (r) { if (t) clearTimeout(t); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
    }
    if (!primary || primary === fallback) return get(fallback, 15000);
    return get(primary, 6000).catch(function () { return get(fallback, 15000); });
  }

  function qs(sel, el) { return (el || document).querySelector(sel); }

  function resolveConfig(el) {
    var script = document.currentScript;
    var assetBase = (el.getAttribute('data-asset-base') || (script && script.getAttribute('data-asset-base')) || '').replace(/\/?$/, '/');
    var explicit = el.getAttribute('data-feed') || (script && script.getAttribute('data-feed'));
    var feed = explicit || (assetBase + 'feed.json');
    // The homepage once pointed at a one-time uploaded copy (filesafe); use the daily Pages copy instead.
    if (/filesafe\.space/.test(feed)) feed = 'https://the-healthy-pitmaster.github.io/site-ticker/feed.json';
    var position = (el.getAttribute('data-position') || 'top').toLowerCase();
    var speed = parseFloat(el.getAttribute('data-speed') || DEFAULT_SPEED);
    if (!isFinite(speed) || speed < 10) speed = DEFAULT_SPEED;
    return { feed: feed, live: LIVE_BASE + 'feed.json', assetBase: assetBase, position: position, speed: speed };
  }

  function iconUrl(assetBase, platform) {
    return assetBase + 'icons/' + platform + '.svg';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderItem(item, assetBase) {
    var a = document.createElement('a');
    a.className = 'thp-ticker__item';
    a.href = item.url || '#';
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.title = (item.platformLabel || '') + ' ' + (item.displayName || '') + ' ' + (item.handle || '');

    a.innerHTML =
      '<span class="thp-ticker__logo" aria-hidden="true">' +
        '<img src="' + escapeHtml(iconUrl(assetBase, item.platform || 'x')) + '" alt="">' +
      '</span>' +
      '<span class="thp-ticker__meta">' +
        '<span class="thp-ticker__platform">' + escapeHtml(item.platformLabel || item.platform || '') + '</span>' +
        '<span class="thp-ticker__name">' + escapeHtml(item.displayName || '') + '</span>' +
        '<span class="thp-ticker__handle">' + escapeHtml(item.handle || '') + '</span>' +
      '</span>' +
      '<span class="thp-ticker__sep" aria-hidden="true">—</span>' +
      '<span class="thp-ticker__text">' + escapeHtml(item.text || '') + '</span>';
    return a;
  }

  function mount(el, items, cfg) {
    el.classList.add('thp-ticker');
    el.setAttribute('role', 'region');
    el.setAttribute('aria-label', 'Recent social posts');
    el.style.setProperty('--thp-speed', cfg.speed + 's');

    if (cfg.position === 'top' || cfg.position === 'fixed-top') {
      el.style.position = cfg.position === 'fixed-top' ? 'fixed' : 'relative';
      if (cfg.position === 'fixed-top') {
        el.style.top = '0';
        el.style.left = '0';
        el.style.right = '0';
      }
    } else if (cfg.position === 'fixed-bottom' || cfg.position === 'bottom') {
      el.style.position = cfg.position.indexOf('fixed') === 0 ? 'fixed' : 'relative';
      if (cfg.position.indexOf('fixed') === 0) {
        el.style.bottom = '0';
        el.style.left = '0';
        el.style.right = '0';
      }
    }

    el.innerHTML = '';
    var track = document.createElement('div');
    track.className = 'thp-ticker__track';

    // Duplicate items for seamless loop
    var seq = items.concat(items);
    seq.forEach(function (item) {
      track.appendChild(renderItem(item, cfg.assetBase));
    });
    el.appendChild(track);
  }

  function showStatus(el, msg) {
    el.classList.add('thp-ticker');
    el.innerHTML = '<div class="thp-ticker__status">' + escapeHtml(msg) + '</div>';
  }

  function boot() {
    var el = document.getElementById(ROOT_ID);
    if (!el) return;
    var cfg = resolveConfig(el);
    showStatus(el, 'Loading recent posts…');

    fetchJsonWithFallback(cfg.live, cfg.feed)
      .then(function (data) {
        var items = (data && data.items) || [];
        if (!items.length) {
          showStatus(el, 'No posts in feed yet.');
          return;
        }
        mount(el, items, cfg);
      })
      .catch(function (err) {
        showStatus(el, 'Ticker feed unavailable. (' + (err && err.message ? err.message : 'error') + ')');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
