/**
 * The Healthy Pitmaster — homepage DYNAMIC VIDEO SPOTs
 * Muted in-card preview (autoplay). Click opens the real platform URL (sound there).
 * Never plays audio on the homepage.
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

  function mutedEmbedSrc(platform, embedUrl) {
    if (!embedUrl) return '';
    var p = (platform || '').toLowerCase();
    var join = embedUrl.indexOf('?') >= 0 ? '&' : '?';
    if (p === 'youtube') {
      // muted loop preview — no homepage audio
      return embedUrl + join + 'autoplay=1&mute=1&controls=0&playsinline=1&loop=1&rel=0&modestbranding=1';
    }
    if (p === 'tilvids') {
      // PeerTube: muted autoplay loop
      return embedUrl + join + 'autoplay=1&muted=1&title=0&warningTitle=0&peertubeLink=0&loop=1';
    }
    // X tweet embed — often static; still try muted-ish; click goes to X for sound
    if (p === 'x' || p === 'twitter') {
      return embedUrl + join + 'dnt=true';
    }
    return embedUrl;
  }

  function mountMutedPreview(card, spot) {
    var thumb = qs('.replay-thumb', card);
    if (!thumb) return;
    var platform = (spot.platform || '').toLowerCase();
    var src = mutedEmbedSrc(platform, spot.embedUrl);

    // Always keep card as link-out for sound on the real site
    if (spot.url) {
      card.href = spot.url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
    }

    if (!src) {
      // thumb-only fallback
      var img = qs('img', thumb);
      if (img && spot.thumbUrl) {
        img.src = spot.thumbUrl;
        img.alt = spot.title ? shortTitle(spot.title, 80) : '';
      }
      return;
    }

    // Overlay play hint stays clickable via parent <a>
    thumb.innerHTML =
      '<iframe class="replay-iframe" src="' + escapeHtml(src) + '" title="' +
      escapeHtml(spot.title || 'Video preview') +
      '" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" ' +
      'allowfullscreen loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe>' +
      '<span class="play-btn" aria-hidden="true"></span>';

    // Click must leave site (sound on platform). Stop iframe from swallowing navigation:
    // pointer-events none on iframe so the <a> receives the click.
    var iframe = qs('iframe', thumb);
    if (iframe) iframe.style.pointerEvents = 'none';
    card.classList.add('is-previewing');
    card.setAttribute('data-embed-active', 'preview');
  }

  function applySpot(spot) {
    if (!spot || !spot.spot) return;
    var card = findCard(String(spot.spot));
    if (!card) return;
    if (!spot.url && !spot.embedUrl) return;

    card.setAttribute('data-platform', spot.platform || '');
    card.setAttribute('data-video-loaded', '1');
    if (spot.fallback) card.setAttribute('data-fallback', '1');

    setLabel(card, spot.platform, spot.title);
    mountMutedPreview(card, spot);
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
