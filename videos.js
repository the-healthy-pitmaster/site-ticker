/**
 * The Healthy Pitmaster — homepage DYNAMIC VIDEO SPOTs loader
 * Fetches videos.json and fills .replay-card[data-spot="1|2|3"].
 *
 * Usage:
 *   <div class="replay-grid" data-videos-feed="https://…/videos.json">…</div>
 *   <script src="https://…/videos.js" defer></script>
 *
 * Or set data-videos-feed on document.documentElement / body.
 * Default feed: ./videos.json (same-origin on GitHub Pages).
 */
(function () {
  'use strict';

  var DEFAULT_FEED = './videos.json';
  var PLATFORM_LABEL = {
    youtube: 'YouTube',
    tilvids: 'TILvids',
    x: 'X',
    twitter: 'X'
  };

  function qs(sel, el) { return (el || document).querySelector(sel); }
  function qsa(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function shortTitle(title, max) {
    max = max || 64;
    var t = String(title || '').replace(/\s+/g, ' ').trim();
    if (t.length <= max) return t;
    var cut = t.slice(0, max - 1);
    var sp = cut.lastIndexOf(' ');
    if (sp > 24) cut = cut.slice(0, sp);
    return cut.replace(/[,;:.\-–—]+$/, '') + '…';
  }

  function resolveFeed() {
    var grid = qs('.replay-grid[data-videos-feed]') || qs('[data-videos-feed]');
    if (grid && grid.getAttribute('data-videos-feed')) {
      return grid.getAttribute('data-videos-feed');
    }
    var script = document.currentScript;
    if (script && script.getAttribute('data-videos-feed')) {
      return script.getAttribute('data-videos-feed');
    }
    // Infer from this script's src directory when hosted on Pages
    if (script && script.src) {
      try {
        var u = new URL(script.src, location.href);
        u.pathname = u.pathname.replace(/[^/]+$/, 'videos.json');
        u.search = '';
        u.hash = '';
        return u.toString();
      } catch (e) { /* ignore */ }
    }
    return DEFAULT_FEED;
  }

  function findCard(spot) {
    return (
      qs('.replay-card[data-spot="' + spot + '"]') ||
      qs('#video-spot-' + spot) ||
      qs('[data-video-spot="' + spot + '"]')
    );
  }

  function setLabel(card, platform, title) {
    var label = qs('.spot-label', card);
    if (!label) return;
    var pl = PLATFORM_LABEL[platform] || platform || '';
    var t = shortTitle(title, 52);
    label.textContent = pl && t ? (pl + ' · ' + t) : (t || pl || label.textContent);
  }

  function setThumb(card, thumbUrl, title) {
    var img = qs('.replay-thumb img', card) || qs('img', card);
    if (!img || !thumbUrl) return;
    img.src = thumbUrl;
    img.alt = title ? shortTitle(title, 80) : '';
    img.loading = img.loading || 'lazy';
  }

  function mountYoutubeEmbed(card, spot) {
    var thumb = qs('.replay-thumb', card);
    if (!thumb || !spot.embedUrl) return;
    card.addEventListener('click', function (ev) {
      // Replace thumb with iframe on first click; keep card as container
      if (card.getAttribute('data-embed-active') === '1') return;
      ev.preventDefault();
      card.setAttribute('data-embed-active', '1');
      var src = spot.embedUrl + (spot.embedUrl.indexOf('?') >= 0 ? '&' : '?') + 'autoplay=1&rel=0';
      thumb.innerHTML =
        '<iframe class="replay-iframe" src="' + escapeHtml(src) + '" title="' +
        escapeHtml(spot.title || 'YouTube video') +
        '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen loading="lazy"></iframe>';
      card.classList.add('is-playing');
    }, { once: false });
  }

  function applySpot(spot) {
    if (!spot || !spot.spot) return;
    var card = findCard(String(spot.spot));
    if (!card) return;
    if (!spot.url && !spot.embedUrl) return;

    card.setAttribute('data-platform', spot.platform || '');
    card.setAttribute('data-video-loaded', '1');
    if (spot.fallback) card.setAttribute('data-fallback', '1');

    if (spot.url) {
      card.href = spot.url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
    }

    setThumb(card, spot.thumbUrl, spot.title);
    setLabel(card, spot.platform, spot.title);

    var platform = (spot.platform || '').toLowerCase();
    if (platform === 'youtube' && spot.embedUrl) {
      mountYoutubeEmbed(card, spot);
    }
    // X / TILvids: link + thumb (embed available via spot.embedUrl for future lightbox)
    if ((platform === 'x' || platform === 'twitter' || platform === 'tilvids') && spot.embedUrl) {
      card.setAttribute('data-embed-url', spot.embedUrl);
    }
  }

  function boot() {
    var feed = resolveFeed();
    fetch(feed, { credentials: 'omit', cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('videos.json HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var spots = (data && data.spots) || [];
        spots.forEach(applySpot);
        document.documentElement.setAttribute('data-videos-ready', '1');
      })
      .catch(function (err) {
        console.warn('[thp-videos]', err);
        document.documentElement.setAttribute('data-videos-ready', '0');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
