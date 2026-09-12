/**
 * THP Real Stories — muted YT playlist previews; random cycle; click opens YouTube for sound.
 *
 * Usage:
 *   <div class="card-grid" data-editable="featured-testimonials"
 *        data-testimonials-feed="https://…/testimonials.json">…</div>
 *   <script src="https://…/testimonials.js" defer></script>
 */
(function () {
  'use strict';

  var DEFAULT_FEED = './testimonials.json';
  var CYCLE_MS = 10000;
  var CARD_SEL =
    '.card-grid[data-editable="featured-testimonials"] .testimonial-card, ' +
    '.testimonial-card[data-testimonial-spot], ' +
    '.testimonial-card[data-spot]';

  function qs(sel, el) { return (el || document).querySelector(sel); }
  function qsa(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function cleanLabel(title) {
    var t = String(title || '').replace(/\s+/g, ' ').trim();
    t = t.replace(/\bunicity\b/gi, '');
    t = t.replace(/\bfeel\s+great\s+stor(y|ies)\b/gi, '');
    t = t.replace(/[!?.:,\-–—]+/g, ' ');
    t = t.replace(/\s+/g, ' ').trim();
    // "Gina's" / "Dave's" / "Fran's" → first name
    var m = t.match(/^([A-Za-z][A-Za-z'’\-]+?)(?:'s|’s)?$/);
    if (m) return m[1].replace(/'s$/i, '').replace(/’s$/i, '');
    // "Blenda Dunn" stays; "Gina's …" after fluff strip may be "Gina's"
    t = t.replace(/'s$/i, '').replace(/’s$/i, '').trim();
    if (!t) t = String(title || '').replace(/\s+/g, ' ').trim().slice(0, 40);
    return t;
  }

  function shortQuote(name) {
    var n = name || 'This';
    return '“' + n + '’s Feel Great story.”';
  }

  function resolveFeed() {
    var grid =
      qs('.card-grid[data-editable="featured-testimonials"][data-testimonials-feed]') ||
      qs('[data-testimonials-feed]');
    if (grid && grid.getAttribute('data-testimonials-feed')) {
      return grid.getAttribute('data-testimonials-feed');
    }
    var script = document.currentScript;
    if (script && script.getAttribute('data-testimonials-feed')) {
      return script.getAttribute('data-testimonials-feed');
    }
    if (script && script.src) {
      try {
        var u = new URL(script.src, location.href);
        u.pathname = u.pathname.replace(/[^/]+$/, 'testimonials.json');
        u.search = '';
        u.hash = '';
        return u.toString();
      } catch (e) { /* ignore */ }
    }
    return DEFAULT_FEED;
  }

  function findCards() {
    var grid = qs('.card-grid[data-editable="featured-testimonials"]');
    if (grid) {
      var cards = qsa('.testimonial-card', grid);
      if (cards.length) return cards;
    }
    var bySpot = qsa('.testimonial-card[data-testimonial-spot], .testimonial-card[data-spot]');
    return bySpot.length ? bySpot.slice(0, 3) : qsa('.testimonial-card').slice(0, 3);
  }

  function ytEmbedSrc(id) {
    return (
      'https://www.youtube.com/embed/' + encodeURIComponent(id) +
      '?autoplay=1&mute=1&controls=0&playsinline=1&rel=0&modestbranding=1' +
      '&loop=1&playlist=' + encodeURIComponent(id)
    );
  }

  function ensureMedia(card) {
    var media = qs('.t-media', card);
    if (media) return media;
    media = document.createElement('div');
    media.className = 't-media';
    media.setAttribute('aria-hidden', 'true');
    var avatar = qs('.avatar', card);
    if (avatar && avatar.parentNode === card) {
      card.replaceChild(media, avatar);
    } else {
      card.insertBefore(media, card.firstChild);
    }
    return media;
  }

  function setText(card, item) {
    var name = cleanLabel(item.title);
    var label = qs('.spot-label', card) || qs('.t-name', card);
    if (label) label.textContent = name;
    var quote = qs('.t-quote', card);
    if (quote) quote.textContent = shortQuote(name);
  }

  function mountPreview(card, item) {
    if (!item || !item.id) return;
    var media = ensureMedia(card);
    var src = ytEmbedSrc(item.id);
    media.innerHTML =
      '<iframe class="t-iframe" src="' + escapeHtml(src) + '" title="' +
      escapeHtml(item.title || 'Testimonial') +
      '" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" ' +
      'allowfullscreen loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe>' +
      '<span class="play-btn" aria-hidden="true"></span>';
    var iframe = qs('iframe', media);
    if (iframe) iframe.style.pointerEvents = 'none';
    card.classList.add('is-previewing');
    card.setAttribute('data-video-id', item.id);
    card.setAttribute('data-testimonial-loaded', '1');
    if (item.url) {
      card.setAttribute('data-watch-url', item.url);
      card.style.cursor = 'pointer';
      card.setAttribute('role', 'link');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', 'Watch ' + cleanLabel(item.title) + ' on YouTube');
    }
    setText(card, item);
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i];
      a[i] = a[j];
      a[j] = tmp;
    }
    return a;
  }

  function pickDistinct(items, count, avoidIds) {
    avoidIds = avoidIds || [];
    var pool = items.filter(function (it) {
      return avoidIds.indexOf(it.id) < 0;
    });
    if (pool.length < count) pool = items.slice();
    var picked = shuffle(pool).slice(0, count);
    // If still not enough uniqueness, fill from full shuffle
    if (picked.length < count) {
      var extra = shuffle(items);
      for (var i = 0; i < extra.length && picked.length < count; i++) {
        var ok = true;
        for (var k = 0; k < picked.length; k++) {
          if (picked[k].id === extra[i].id) { ok = false; break; }
        }
        if (ok || items.length < count) picked.push(extra[i]);
      }
    }
    // Ensure no two cards same id when enough items
    if (items.length >= count) {
      var seen = {};
      var unique = [];
      var rest = shuffle(items);
      for (var r = 0; r < rest.length && unique.length < count; r++) {
        if (!seen[rest[r].id]) {
          seen[rest[r].id] = 1;
          unique.push(rest[r]);
        }
      }
      return unique;
    }
    return picked;
  }

  function wireClick(card) {
    if (card.getAttribute('data-t-click') === '1') return;
    card.setAttribute('data-t-click', '1');
    function openWatch(ev) {
      var url = card.getAttribute('data-watch-url');
      if (!url) return;
      if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      window.open(url, '_blank', 'noopener,noreferrer');
    }
    card.addEventListener('click', openWatch);
    card.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') {
        openWatch(ev);
      }
    });
  }

  function cycle(cards, items) {
    if (!cards.length || !items.length) return;
    var chosen = pickDistinct(items, cards.length, []);
    for (var i = 0; i < cards.length; i++) {
      var item = chosen[i % chosen.length];
      mountPreview(cards[i], item);
      wireClick(cards[i]);
    }
  }

  function boot() {
    var feed = resolveFeed();
    var cards = findCards();
    if (!cards.length) {
      console.warn('[thp-testimonials] no cards found');
      return;
    }
    fetch(feed, { credentials: 'omit', cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('testimonials.json HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var items = (data && data.items) || [];
        if (!items.length) {
          document.documentElement.setAttribute('data-testimonials-ready', '0');
          return;
        }
        cycle(cards, items);
        document.documentElement.setAttribute('data-testimonials-ready', '1');
        document.documentElement.setAttribute('data-testimonials-count', String(items.length));
        setInterval(function () {
          cycle(cards, items);
        }, CYCLE_MS);
      })
      .catch(function (err) {
        console.warn('[thp-testimonials]', err);
        document.documentElement.setAttribute('data-testimonials-ready', '0');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
