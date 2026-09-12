/**
 * THP DYNAMIC VIDEO SPOTs — muted playing previews; click opens platform for sound.
 */
(function () {
  'use strict';
  var DEFAULT_FEED = './videos.json';
  var PLATFORM_LABEL = { youtube: 'YouTube', tilvids: 'TILvids', x: 'X', twitter: 'X' };

  function qs(sel, el) { return (el || document).querySelector(sel); }
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
    if (grid && grid.getAttribute('data-videos-feed')) return grid.getAttribute('data-videos-feed');
    var script = document.currentScript;
    if (script && script.getAttribute('data-videos-feed')) return script.getAttribute('data-videos-feed');
    if (script && script.src) {
      try {
        var u = new URL(script.src, location.href);
        u.pathname = u.pathname.replace(/[^/]+$/, 'videos.json');
        u.search = ''; u.hash = '';
        return u.toString();
      } catch (e) {}
    }
    return DEFAULT_FEED;
  }
  function findCard(spot) {
    return qs('.replay-card[data-spot="' + spot + '"]') || qs('#video-spot-' + spot) || qs('[data-video-spot="' + spot + '"]');
  }
  function setLabel(card, platform, title) {
    var label = qs('.spot-label', card);
    if (!label) return;
    var pl = PLATFORM_LABEL[platform] || platform || '';
    var t = shortTitle(title, 52);
    label.textContent = pl && t ? (pl + ' · ' + t) : (t || pl || label.textContent);
  }
  function ytEmbed(embedUrl) {
    var join = embedUrl.indexOf('?') >= 0 ? '&' : '?';
    var idMatch = embedUrl.match(/embed\/([^?&/]+)/);
    var id = idMatch ? idMatch[1] : '';
    var src = embedUrl + join + 'autoplay=1&mute=1&controls=0&playsinline=1&rel=0&modestbranding=1';
    if (id) src += '&loop=1&playlist=' + encodeURIComponent(id);
    return src;
  }
  function tilEmbed(embedUrl) {
    var join = embedUrl.indexOf('?') >= 0 ? '&' : '?';
    return embedUrl + join + 'autoplay=1&muted=1&title=0&warningTitle=0&peertubeLink=0&loop=1';
  }
  function mountMutedPreview(card, spot) {
    var thumb = qs('.replay-thumb', card);
    if (!thumb) return;
    var platform = (spot.platform || '').toLowerCase();
    if (spot.url) {
      card.href = spot.url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
    }
    var html = '';
    // Prefer direct muted <video> when we have a playable file (X especially)
    if (spot.previewUrl) {
      html =
        '<video class="replay-iframe" src="' + escapeHtml(spot.previewUrl) + '" ' +
        'poster="' + escapeHtml(spot.thumbUrl || '') + '" muted autoplay loop playsinline ' +
        'preload="metadata" referrerpolicy="no-referrer" crossorigin="anonymous"></video>' +
        '<span class="play-btn" aria-hidden="true"></span>';
    } else if (platform === 'youtube' && spot.embedUrl) {
      html =
        '<iframe class="replay-iframe" src="' + escapeHtml(ytEmbed(spot.embedUrl)) + '" title="' +
        escapeHtml(spot.title || 'YouTube') +
        '" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" ' +
        'allowfullscreen loading="lazy"></iframe><span class="play-btn" aria-hidden="true"></span>';
    } else if (platform === 'tilvids' && spot.embedUrl) {
      html =
        '<iframe class="replay-iframe" src="' + escapeHtml(tilEmbed(spot.embedUrl)) + '" title="' +
        escapeHtml(spot.title || 'TILvids') +
        '" allow="autoplay; fullscreen" allowfullscreen loading="lazy"></iframe>' +
        '<span class="play-btn" aria-hidden="true"></span>';
    } else if (spot.thumbUrl) {
      html =
        '<img src="' + escapeHtml(spot.thumbUrl) + '" alt="' + escapeHtml(shortTitle(spot.title, 80)) +
        '" width="640" height="360" loading="lazy" /><span class="play-btn" aria-hidden="true"></span>';
    }
    if (!html) return;
    thumb.innerHTML = html;
    var iframe = qs('iframe', thumb);
    if (iframe) iframe.style.pointerEvents = 'none';
    var vid = qs('video', thumb);
    if (vid) {
      vid.style.pointerEvents = 'none';
      vid.muted = true;
      var p = vid.play();
      if (p && p.catch) p.catch(function () {});
    }
    card.classList.add('is-previewing');
  }
  function applySpot(spot) {
    if (!spot || !spot.spot) return;
    var card = findCard(String(spot.spot));
    if (!card) return;
    if (!spot.url && !spot.embedUrl && !spot.previewUrl) return;
    card.setAttribute('data-platform', spot.platform || '');
    card.setAttribute('data-video-loaded', '1');
    if (spot.fallback) card.setAttribute('data-fallback', '1');
    setLabel(card, spot.platform, spot.title);
    mountMutedPreview(card, spot);
  }
  function boot() {
    fetch(resolveFeed(), { credentials: 'omit', cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('videos.json HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        ((data && data.spots) || []).forEach(applySpot);
        document.documentElement.setAttribute('data-videos-ready', '1');
      })
      .catch(function (err) {
        console.warn('[thp-videos]', err);
        document.documentElement.setAttribute('data-videos-ready', '0');
      });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
