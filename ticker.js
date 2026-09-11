
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
  var DEFAULT_SPEED = 55; // seconds per loop

  function qs(sel, el) { return (el || document).querySelector(sel); }

  function resolveConfig(el) {
    var script = document.currentScript;
    var assetBase = (el.getAttribute('data-asset-base') || (script && script.getAttribute('data-asset-base')) || '').replace(/\/?$/, '/');
    var feed = el.getAttribute('data-feed') || (script && script.getAttribute('data-feed')) || (assetBase + 'feed.json');
    var position = (el.getAttribute('data-position') || 'top').toLowerCase();
    var speed = parseFloat(el.getAttribute('data-speed') || DEFAULT_SPEED);
    if (!isFinite(speed) || speed < 10) speed = DEFAULT_SPEED;
    return { feed: feed, assetBase: assetBase, position: position, speed: speed };
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

    fetch(cfg.feed, { credentials: 'omit', cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
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
