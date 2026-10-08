/**
 * THP LIVE VIDEO BOX — turns the homepage "Upcoming Event" card into a live player
 * whenever Jim is live, and puts the normal card back when he isn't.
 *
 * Priority: PeerTube permanent live (peertube.wtf) first, YouTube live as backup.
 * Status comes from Barry's cached /api/live-status (server checks both, ~1/min).
 * If that endpoint can't be reached, we ask PeerTube's public API directly.
 * Only public watch ids are used here — never any stream key.
 *
 * When nothing is live, the card shows the flyer for the NEXT show from shows.json
 * (weekly schedule, Mountain Time). A show with no flyer leaves the normal card as is.
 *
 * Auto-loaded by videos.js (no homepage edit needed). Optional overrides on the
 * .event-card (or this <script>): data-live-status="<url>", data-live-shows="<url>",
 * data-live-poll="60".
 */
(function (root) {
  'use strict';

  var DEFAULTS = {
    statusUrl: 'https://barry-production-c225.up.railway.app/api/live-status',
    peertubeInstance: 'https://peertube.wtf',
    peertubeVideoId: '1gBXURNMWzNVLeTzEMMRN6',
    pollSeconds: 60,
    // Need this many "not live" answers in a row before swapping back to the card,
    // so one hiccup mid-show doesn't yank the player.
    offlineConfirmations: 2
  };
  var SOURCE_LABEL = { peertube: 'PeerTube', youtube: 'YouTube' };

  // ------------------------------------------------------------------ pure helpers
  function addParams(url, params) {
    var join = url.indexOf('?') >= 0 ? '&' : '?';
    return url + join + params;
  }
  function embedSrc(status, opts) {
    opts = opts || {};
    var muted = opts.muted !== false;
    if (!status || !status.embedUrl) return '';
    if (status.source === 'youtube') {
      return addParams(status.embedUrl,
        'autoplay=1&mute=' + (muted ? 1 : 0) + '&playsinline=1&rel=0&modestbranding=1&controls=1');
    }
    return addParams(status.embedUrl,
      'autoplay=1&muted=' + (muted ? 1 : 0) + '&title=0&warningTitle=0&peertubeLink=0');
  }
  /** Normalise either Barry's /api/live-status or a raw PeerTube video payload. */
  function normalizeStatus(data, cfg) {
    cfg = cfg || DEFAULTS;
    if (!data || typeof data !== 'object') return null;
    if (data.state && typeof data.state === 'object' && 'isLive' in data) {
      // Raw PeerTube /api/v1/videos/<id>: state 1 = published = streaming now.
      var id = data.shortUUID || data.uuid || cfg.peertubeVideoId;
      var live = !!data.isLive && data.state.id === 1;
      return {
        live: live,
        source: live ? 'peertube' : null,
        title: data.name || '',
        watchUrl: live ? cfg.peertubeInstance + '/w/' + id : '',
        embedUrl: live ? cfg.peertubeInstance + '/videos/embed/' + id : '',
        embeddable: true
      };
    }
    if (!('live' in data)) return null;
    var ok = !!data.live && !!data.embedUrl && (data.source === 'peertube' || data.source === 'youtube');
    return {
      live: ok,
      source: ok ? data.source : null,
      title: data.title || '',
      watchUrl: data.watchUrl || '',
      embedUrl: ok ? data.embedUrl : '',
      thumbUrl: data.thumbUrl || '',
      embeddable: data.embeddable !== false,
      pollSeconds: data.pollSeconds
    };
  }
  function liveKey(s) { return s && s.live ? s.source + '|' + s.embedUrl : ''; }

  // ---- weekly schedule (shows.json) ----
  var WEEKDAYS = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
  var WEEK_MIN = 7 * 1440;
  function zoneParts(date, tz) {
    var parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(date);
    var o = {};
    parts.forEach(function (p) { o[p.type] = p.value; });
    return { weekday: WEEKDAYS[String(o.weekday).slice(0, 3).toLowerCase()], hour: +o.hour % 24, minute: +o.minute };
  }
  function parseShowTime(show) {
    var wd = WEEKDAYS[String(show.weekday || '').slice(0, 3).toLowerCase()];
    var m = /^(\d{1,2}):(\d{2})$/.exec(String(show.time || '').trim());
    if (wd == null || !m) return null;
    return wd * 1440 + (+m[1]) * 60 + (+m[2]);
  }
  function formatWhen(date, tz, tzLabel) {
    var d = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', month: 'short', day: 'numeric' }).format(date);
    var t = new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: 'numeric', minute: '2-digit' }).format(date);
    return d + ' · ' + t + ' ' + (tzLabel || 'MT');
  }
  /**
   * Next show from the weekly schedule. A show stays "next" until its start +
   * durationMinutes (default 90), so a late-starting stream still shows its flyer.
   * Returns {show, start: Date, when: "Mon, Oct 12 · 6:00 PM MT"} or null.
   */
  function nextShow(schedule, now) {
    if (!schedule || !schedule.shows || !schedule.shows.length) return null;
    var tz = schedule.timezone || 'America/Denver';
    now = now || new Date();
    var np = zoneParts(now, tz);
    var nowMin = np.weekday * 1440 + np.hour * 60 + np.minute;
    var best = null;
    schedule.shows.forEach(function (show) {
      if (!show || show.enabled === false) return;
      var st = parseShowTime(show);
      if (st == null) return;
      var dur = Math.max(0, +show.durationMinutes || 90);
      var delta = ((st - nowMin) % WEEK_MIN + WEEK_MIN) % WEEK_MIN; // minutes until next start
      if (delta > WEEK_MIN - dur) delta -= WEEK_MIN;                 // currently inside its window
      if (!best || delta < best.delta) best = { show: show, delta: delta, st: st };
    });
    if (!best) return null;
    var start = new Date(Math.floor(now.getTime() / 60000) * 60000 + best.delta * 60000);
    // Daylight-saving change between now and the show: nudge to the intended wall-clock time.
    var sp = zoneParts(start, tz);
    var drift = best.st - (sp.weekday * 1440 + sp.hour * 60 + sp.minute);
    if (drift > WEEK_MIN / 2) drift -= WEEK_MIN;
    if (drift < -WEEK_MIN / 2) drift += WEEK_MIN;
    if (drift && Math.abs(drift) <= 120) start = new Date(start.getTime() + drift * 60000);
    return { show: best.show, start: start, when: formatWhen(start, tz, schedule.timezoneLabel) };
  }

  var api = { embedSrc: embedSrc, normalizeStatus: normalizeStatus, liveKey: liveKey, nextShow: nextShow, DEFAULTS: DEFAULTS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ DOM
  var script = document.currentScript;
  function qs(sel, el) { return (el || document).querySelector(sel); }
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function attr(name, card) {
    var v = card && card.getAttribute(name);
    if (!v) { var l = qs('#live'); v = l && l.getAttribute(name); }
    if (!v && script) v = script.getAttribute(name);
    return v || '';
  }

  var CSS = [
    '.event-card.thp-has-box{padding:14px 14px 16px;text-align:left}',
    '.event-card.thp-has-box>:not(.thp-live-box){display:none!important}',
    '.thp-next-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(197,160,89,.8);color:#e0c089;border-radius:999px;',
    'padding:4px 10px;font:700 10.5px/1.2 Montserrat,Inter,system-ui,sans-serif;letter-spacing:.14em}',
    '.thp-live-when{color:#fff;font:600 13px/1.2 Montserrat,Inter,system-ui,sans-serif}',
    '.thp-live-frame.thp-flyer-frame{cursor:zoom-in;aspect-ratio:4/3;padding:0;display:block;font:inherit;color:inherit}',
    '.thp-flyer-frame .thp-flyer-bg{position:absolute;inset:-20px;background-size:cover;background-position:center;filter:blur(18px) brightness(.55)}',
    '.thp-flyer-frame img.thp-flyer-img{object-fit:cover;z-index:1}',
    '.thp-flyer-hint{left:8px;bottom:8px;pointer-events:none}',
    '.thp-live-modal-flyer{width:auto;max-width:100%;align-items:center}',
    '.thp-live-modal-flyer .thp-live-modal-bar{align-self:stretch}',
    '.thp-live-modal-flyer img{display:block;max-width:min(100%,560px);max-height:calc(100vh - 110px);width:auto;height:auto;border-radius:10px;border:1px solid rgba(197,160,89,.55)}',
    '.thp-live-box{display:flex;flex-direction:column;gap:10px}',
    '.thp-live-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}',
    '.thp-live-pill{display:inline-flex;align-items:center;gap:6px;background:#d32f2f;color:#fff;border-radius:999px;',
    'padding:4px 10px;font:700 10.5px/1.2 Montserrat,Inter,system-ui,sans-serif;letter-spacing:.14em}',
    '.thp-live-pill i{width:7px;height:7px;border-radius:50%;background:#fff;display:inline-block;animation:thpLivePulse 1.4s ease-in-out infinite}',
    '@keyframes thpLivePulse{0%,100%{opacity:1}50%{opacity:.25}}',
    '.thp-live-src{color:#c5a059;font:600 12px/1.2 Montserrat,Inter,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase}',
    '.thp-live-frame{position:relative;width:100%;aspect-ratio:16/9;background:#000;border:1px solid rgba(197,160,89,.55);border-radius:8px;overflow:hidden}',
    '.thp-live-frame iframe,.thp-live-frame img{position:absolute;inset:0;width:100%;height:100%;border:0;object-fit:cover}',
    '.thp-live-frame .thp-live-away{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#c5a059;',
    'font:600 13px/1.3 Montserrat,Inter,system-ui,sans-serif;text-align:center;padding:12px}',
    '.thp-live-ctl{position:absolute;z-index:2;border:1px solid rgba(197,160,89,.7);background:rgba(0,0,0,.72);color:#fff;cursor:pointer;',
    'font:600 12px/1 Montserrat,Inter,system-ui,sans-serif;border-radius:999px;padding:7px 11px;display:inline-flex;align-items:center;gap:6px}',
    '.thp-live-ctl:hover,.thp-live-ctl:focus-visible{background:rgba(0,0,0,.9);border-color:#e0a86e;outline:none}',
    '.thp-live-sound{left:8px;bottom:8px}',
    '.thp-live-expand{right:8px;top:8px;padding:6px 9px}',
    '.thp-live-title{margin:0;color:#fff;font:600 15px/1.3 "Playfair Display",Georgia,serif;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}',
    '.thp-live-actions{display:flex;justify-content:center}',
    '.thp-live-actions .btn{cursor:pointer}',
    '.thp-live-modal{position:fixed;inset:0;z-index:2147483000;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;padding:24px}',
    '.thp-live-modal-inner{width:min(1100px,100%);display:flex;flex-direction:column;gap:10px}',
    '.thp-live-modal-bar{display:flex;align-items:center;gap:12px;color:#fff;min-width:0}',
    '.thp-live-modal-title{flex:1;min-width:0;font:600 17px/1.3 "Playfair Display",Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.thp-live-modal-when{display:block;color:#e0c089;font:600 12.5px/1.4 Montserrat,Inter,system-ui,sans-serif}',
    '.thp-live-modal-bar a{color:#c5a059;font:600 12px/1.2 Montserrat,Inter,system-ui,sans-serif;text-decoration:none;white-space:nowrap}',
    '.thp-live-close{width:40px;height:40px;flex:0 0 auto;border-radius:50%;border:1px solid rgba(197,160,89,.7);background:#000;color:#fff;font-size:24px;line-height:1;cursor:pointer}',
    '.thp-live-modal-frame{position:relative;width:100%;aspect-ratio:16/9;max-height:calc(100vh - 110px);background:#000;border:1px solid rgba(197,160,89,.55);border-radius:10px;overflow:hidden}',
    '.thp-live-modal-frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}',
    'html.thp-live-modal-open,html.thp-live-modal-open body{overflow:hidden!important}',
    '@media (max-width:640px){.thp-live-modal{padding:0}.thp-live-modal-inner{gap:8px}',
    '.thp-live-modal-bar{padding:0 10px}.thp-live-modal-frame{border-radius:0;border-left:0;border-right:0}.thp-live-modal-title{font-size:15px}}'
  ].join('\n');

  function injectCss() {
    if (document.getElementById('thp-live-box-css')) return;
    var st = document.createElement('style');
    st.id = 'thp-live-box-css';
    st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  function LiveBox(card) {
    this.card = card;
    var showsDefault = 'shows.json';
    try { if (script && script.src) showsDefault = new URL('shows.json', script.src).toString(); } catch (e) {}
    this.cfg = {
      statusUrl: attr('data-live-status', card) || DEFAULTS.statusUrl,
      showsUrl: attr('data-live-shows', card) || showsDefault,
      peertubeInstance: DEFAULTS.peertubeInstance,
      peertubeVideoId: attr('data-live-peertube-id', card) || DEFAULTS.peertubeVideoId,
      pollSeconds: parseInt(attr('data-live-poll', card), 10) || DEFAULTS.pollSeconds
    };
    this.mode = 'card';      // 'card' | 'flyer' | 'live'
    this.current = null;     // live status while live
    this.next = null;        // {show, start, when, flyerUrl} while showing a flyer
    this.schedule = null;
    this.scheduleAt = 0;
    this.offlineCount = 0;
    this.lastPoll = 0;
    this.timer = null;
    this.modal = null;
    this.unmuted = false;
    this.inflight = false;
  }

  LiveBox.prototype.fetchJson = function (url) {
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var t = ctl ? setTimeout(function () { ctl.abort(); }, 10000) : null;
    return fetch(url, { credentials: 'omit', cache: 'no-cache', signal: ctl ? ctl.signal : undefined })
      .then(function (r) {
        if (t) clearTimeout(t);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }, function (e) { if (t) clearTimeout(t); throw e; });
  };

  LiveBox.prototype.loadSchedule = function () {
    var self = this;
    if (self.schedule && Date.now() - self.scheduleAt < 15 * 60 * 1000) return Promise.resolve();
    return self.fetchJson(self.cfg.showsUrl)
      .then(function (data) { self.schedule = data; self.scheduleAt = Date.now(); })
      .catch(function (err) { if (root.console) console.warn('[thp-live-box] shows.json', err && err.message); });
  };

  LiveBox.prototype.poll = function () {
    var self = this;
    if (self.inflight) return Promise.resolve();
    self.inflight = true;
    self.lastPoll = Date.now();
    var cfg = self.cfg;
    var direct = cfg.peertubeInstance + '/api/v1/videos/' + encodeURIComponent(cfg.peertubeVideoId);
    var status = self.fetchJson(cfg.statusUrl)
      .catch(function () { return self.fetchJson(direct); }) // Barry unreachable -> PeerTube only
      .then(function (data) { return normalizeStatus(data, cfg); })
      .catch(function (err) { if (root.console) console.warn('[thp-live-box]', err && err.message); return null; });
    return Promise.all([status, self.loadSchedule()])
      .then(function (r) { self.apply(r[0]); })
      .catch(function (err) { if (root.console) console.warn('[thp-live-box]', err && err.message); })
      .then(function () { self.inflight = false; self.schedule_(); });
  };

  LiveBox.prototype.schedule_ = function () {
    var self = this;
    if (self.timer) clearTimeout(self.timer);
    var secs = Math.min(300, Math.max(30, self.cfg.pollSeconds || 60));
    self.timer = setTimeout(function () {
      if (document.hidden) return; // resume on visibilitychange
      self.poll();
    }, secs * 1000);
  };

  /** Decide what the box shows: live player > next show's flyer > normal card. */
  LiveBox.prototype.apply = function (status) {
    if (status && status.live) {
      this.offlineCount = 0;
      if (this.mode !== 'live' || liveKey(status) !== liveKey(this.current)) this.showLive(status);
      else this.current = status;
      return;
    }
    if (this.mode === 'live') {
      if (!status) return; // unknown answer mid-show: keep the player up
      this.offlineCount += 1;
      if (this.offlineCount < DEFAULTS.offlineConfirmations) return;
    }
    this.showIdle();
  };

  LiveBox.prototype.showIdle = function () {
    var nx = nextShow(this.schedule, new Date());
    var flyer = nx && nx.show && nx.show.flyer ? String(nx.show.flyer) : '';
    if (!flyer) { this.showCard(); return; }
    var flyerUrl = flyer;
    try { flyerUrl = new URL(flyer, this.cfg.showsUrl).toString(); } catch (e) {}
    nx.flyerUrl = flyerUrl;
    var key = flyerUrl + '|' + nx.when;
    if (this.mode === 'flyer' && this.next && this.next.key === key) return;
    nx.key = key;
    this.showFlyer(nx);
  };

  LiveBox.prototype.ensureBox = function () {
    injectCss();
    var card = this.card;
    var box = qs('.thp-live-box', card);
    if (!box) {
      box = document.createElement('div');
      box.className = 'thp-live-box';
      card.appendChild(box);
      var self = this;
      box.addEventListener('click', function (e) {
        var t = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
        if (!t) return;
        e.preventDefault();
        if (t.getAttribute('data-act') === 'sound') self.turnSoundOn();
        else if (t.getAttribute('data-act') === 'big') self.openModal();
      });
    }
    card.classList.add('thp-has-box');
    return box;
  };

  LiveBox.prototype.smallPlayerHtml = function (s) {
    var label = SOURCE_LABEL[s.source] || '';
    if (s.embeddable === false) {
      return (s.thumbUrl ? '<img src="' + esc(s.thumbUrl) + '" alt="">' : '') +
        '<a class="thp-live-ctl thp-live-sound" href="' + esc(s.watchUrl) + '" target="_blank" rel="noopener">Watch on ' + esc(label) + ' ↗</a>';
    }
    return '<iframe src="' + esc(embedSrc(s, { muted: !this.unmuted })) + '" title="' + esc(s.title || 'Live now') + '" ' +
      'allow="autoplay; fullscreen; picture-in-picture; encrypted-media" allowfullscreen ' +
      'referrerpolicy="strict-origin-when-cross-origin"></iframe>' +
      (this.unmuted ? '' : '<button type="button" class="thp-live-ctl thp-live-sound" data-act="sound" aria-label="Turn sound on">🔇 Tap for sound</button>') +
      '<button type="button" class="thp-live-ctl thp-live-expand" data-act="big" aria-label="Watch bigger">⤢</button>';
  };

  LiveBox.prototype.showLive = function (s) {
    var wasModal = !!this.modal && this.mode === 'live';
    if (this.modal && !wasModal) this.closeModal();
    this.mode = 'live';
    this.current = s;
    this.next = null;
    var box = this.ensureBox();
    var label = SOURCE_LABEL[s.source] || '';
    box.innerHTML =
      '<div class="thp-live-head"><span class="thp-live-pill"><i></i>LIVE NOW</span>' +
      '<span class="thp-live-src">on ' + esc(label) + '</span></div>' +
      '<div class="thp-live-frame">' + this.smallPlayerHtml(s) + '</div>' +
      (s.title ? '<p class="thp-live-title">' + esc(s.title) + '</p>' : '') +
      '<div class="thp-live-actions"><button type="button" class="btn btn-copper btn-sm" data-act="big">Watch bigger ⤢</button></div>';
    this.card.classList.add('thp-is-live');
    this.card.setAttribute('data-live-box', 'live');
    this.card.setAttribute('data-live-source', s.source);
    document.documentElement.setAttribute('data-live-box', s.source);
    if (wasModal) { this.renderModal(); this.pauseSmall(); } // source switched while the popup was open
  };

  LiveBox.prototype.showFlyer = function (nx) {
    if (this.modal && this.mode !== 'flyer') this.closeModal();
    this.mode = 'flyer';
    this.current = null;
    this.offlineCount = 0;
    this.unmuted = false;
    this.next = nx;
    var show = nx.show;
    var name = show.title || show.name || 'Upcoming live';
    var focus = show.flyerFocus || '50% 50%';
    var box = this.ensureBox();
    box.innerHTML =
      '<div class="thp-live-head"><span class="thp-next-pill">NEXT LIVE</span>' +
      '<span class="thp-live-when">' + esc(nx.when) + '</span></div>' +
      '<button type="button" class="thp-live-frame thp-flyer-frame" data-act="big" aria-label="View the ' + esc(name) + ' flyer">' +
      '<span class="thp-flyer-bg" style="background-image:url(&quot;' + esc(nx.flyerUrl) + '&quot;)"></span>' +
      '<img class="thp-flyer-img" src="' + esc(nx.flyerUrl) + '" alt="' + esc(name) + ' flyer" style="object-position:' + esc(focus) + ';object-fit:' + (show.flyerFit === 'contain' ? 'contain' : 'cover') + '" loading="lazy">' +
      '<span class="thp-live-ctl thp-flyer-hint">🔍 Tap to view flyer</span></button>' +
      '<p class="thp-live-title">' + esc(name) + '</p>' +
      '<div class="thp-live-actions"><button type="button" class="btn btn-copper btn-sm" data-act="big">View flyer ⤢</button></div>';
    this.card.classList.remove('thp-is-live');
    this.card.removeAttribute('data-live-source');
    this.card.setAttribute('data-live-box', 'flyer');
    document.documentElement.setAttribute('data-live-box', 'flyer');
    if (this.modal) this.renderModal();
  };

  LiveBox.prototype.showCard = function () {
    this.closeModal();
    this.mode = 'card';
    this.current = null;
    this.next = null;
    this.offlineCount = 0;
    this.unmuted = false;
    var box = qs('.thp-live-box', this.card);
    if (box) box.parentNode.removeChild(box);
    this.card.classList.remove('thp-is-live', 'thp-has-box');
    this.card.removeAttribute('data-live-source');
    this.card.removeAttribute('data-live-box');
    document.documentElement.setAttribute('data-live-box', 'off');
  };

  LiveBox.prototype.turnSoundOn = function () {
    // Reload the small player unmuted; the tap counts as the user gesture browsers need.
    this.unmuted = true;
    var frame = qs('.thp-live-frame', this.card);
    if (frame && this.current) frame.innerHTML = this.smallPlayerHtml(this.current);
  };

  LiveBox.prototype.renderModal = function () {
    if (!this.modal) return;
    var inner;
    if (this.mode === 'live' && this.current) {
      var s = this.current;
      var label = SOURCE_LABEL[s.source] || '';
      inner =
        '<div class="thp-live-modal-inner">' +
        '<div class="thp-live-modal-bar"><span class="thp-live-pill"><i></i>LIVE</span>' +
        '<span class="thp-live-modal-title">' + esc(s.title || 'Live now') + '</span>' +
        (s.watchUrl ? '<a href="' + esc(s.watchUrl) + '" target="_blank" rel="noopener">Open on ' + esc(label) + ' ↗</a>' : '') +
        '<button type="button" class="thp-live-close" data-act="close" aria-label="Close">×</button></div>' +
        '<div class="thp-live-modal-frame"><iframe src="' + esc(embedSrc(s, { muted: false })) + '" title="' + esc(s.title || 'Live now') + '" ' +
        'allow="autoplay; fullscreen; picture-in-picture; encrypted-media" allowfullscreen ' +
        'referrerpolicy="strict-origin-when-cross-origin"></iframe></div></div>';
    } else if (this.mode === 'flyer' && this.next) {
      var nx = this.next;
      var name = nx.show.title || nx.show.name || 'Upcoming live';
      inner =
        '<div class="thp-live-modal-inner thp-live-modal-flyer">' +
        '<div class="thp-live-modal-bar"><span class="thp-next-pill">NEXT LIVE</span>' +
        '<span class="thp-live-modal-title">' + esc(name) + '<small class="thp-live-modal-when">' + esc(nx.when) + '</small></span>' +
        '<button type="button" class="thp-live-close" data-act="close" aria-label="Close">×</button></div>' +
        '<img src="' + esc(nx.flyerUrl) + '" alt="' + esc(name) + ' flyer"></div>';
    } else {
      this.closeModal();
      return;
    }
    this.modal.innerHTML = inner;
    var close = qs('.thp-live-close', this.modal);
    if (close) close.focus();
  };

  LiveBox.prototype.pauseSmall = function () {
    // Stop the small player while the big one plays (no double audio / double bandwidth).
    var frame = this.mode === 'live' && qs('.thp-live-frame', this.card);
    if (frame) frame.innerHTML = '<div class="thp-live-away">▶ Playing in the big player</div>';
  };

  LiveBox.prototype.openModal = function () {
    if (this.mode === 'card') return;
    var s = this.current;
    if (this.mode === 'live' && s && s.embeddable === false) { root.open(s.watchUrl, '_blank', 'noopener'); return; }
    var self = this;
    if (!self.modal) {
      var m = document.createElement('div');
      m.className = 'thp-live-modal';
      m.setAttribute('role', 'dialog');
      m.setAttribute('aria-modal', 'true');
      m.setAttribute('aria-label', self.mode === 'live' ? 'Live video' : 'Show flyer');
      m.addEventListener('click', function (e) {
        var t = e.target;
        if (t === m || (t.closest && t.closest('[data-act="close"]'))) self.closeModal();
      });
      self.onKey = function (e) { if (e.key === 'Escape') self.closeModal(); };
      document.addEventListener('keydown', self.onKey);
      document.body.appendChild(m);
      self.modal = m;
    }
    self.renderModal();
    document.documentElement.classList.add('thp-live-modal-open');
    self.pauseSmall();
  };

  LiveBox.prototype.closeModal = function () {
    if (!this.modal) return;
    // Removing the iframe stops the big player.
    if (this.modal.parentNode) this.modal.parentNode.removeChild(this.modal);
    this.modal = null;
    if (this.onKey) document.removeEventListener('keydown', this.onKey);
    document.documentElement.classList.remove('thp-live-modal-open');
    var frame = qs('.thp-live-frame', this.card);
    if (frame && this.mode === 'live' && this.current) { this.unmuted = false; frame.innerHTML = this.smallPlayerHtml(this.current); }
  };

  function boot() {
    var card = qs('[data-live-box-card]') || qs('.live-grid .event-card') || qs('.event-card');
    if (!card || card.getAttribute('data-live-box-ready')) return;
    card.setAttribute('data-live-box-ready', '1');
    var box = new LiveBox(card);
    root.THPLiveBox = box;
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && Date.now() - box.lastPoll > box.cfg.pollSeconds * 1000) box.poll();
    });
    box.poll();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})(typeof window !== 'undefined' ? window : this);
