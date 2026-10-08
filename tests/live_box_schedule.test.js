// Where live-box.js gets its schedule: Barry /api/live-shows first (admin-uploaded flyers merged in),
// shows.json from GitHub Pages if Barry can't be reached. Runs live-box.js against a tiny fake DOM.
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'live-box.js'), 'utf8');
const shows = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'shows.json'), 'utf8'));
const API = 'https://barry-production-c225.up.railway.app/api/live-shows';
const STATUS = 'https://barry-production-c225.up.railway.app/api/live-status';
const PAGES = 'https://the-healthy-pitmaster.github.io/site-ticker/';

function el(tag) {
  const e = {
    tagName: tag, children: [], attrs: {}, style: {}, innerHTML: '', parentNode: null,
    classList: { _s: new Set(), add(...c) { c.forEach((x) => this._s.add(x)); }, remove(...c) { c.forEach((x) => this._s.delete(x)); } },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; }, addEventListener() {},
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); },
    querySelector(sel) { return sel === '.thp-live-box' ? this.children.find((c) => c.className === 'thp-live-box') || null : null; },
  };
  return e;
}

function run(fetchMap, now) {
  const card = el('div');
  const doc = {
    readyState: 'complete', hidden: false, currentScript: { src: PAGES + 'live-box.js', getAttribute: () => null },
    documentElement: el('html'), head: el('head'), body: el('body'),
    querySelector: (s) => (s === '.event-card' ? card : null), getElementById: () => null,
    createElement: el, addEventListener() {}, removeEventListener() {},
  };
  const calls = [];
  const fetch = (url) => {
    calls.push(url);
    const key = Object.keys(fetchMap).find((k) => url.startsWith(k));
    const v = key ? fetchMap[key] : null;
    if (!v || v === 'down') return Promise.reject(new TypeError('Failed to fetch'));
    return Promise.resolve({ ok: v.status ? v.status < 300 : true, status: v.status || 200, json: () => Promise.resolve(v.body) });
  };
  const RealDate = Date;
  class FakeDate extends RealDate { constructor(...a) { super(...(a.length ? a : [now])); } static now() { return now; } }
  const win = { console: { warn() {} } };
  const ctx = { window: win, document: doc, fetch, URL, Intl, Promise, Date: FakeDate, setTimeout: () => 0, clearTimeout() {}, Object, String, Math, Array };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  return new Promise((r) => setTimeout(r, 20)).then(() => ({ box: win.THPLiveBox, card, calls }));
}

const NOT_LIVE = { body: { live: false, source: null } };
const MON_8PM_MT = Date.parse('2026-10-12T20:00:00-06:00'); // next = Trent (Tue 7 PM)
const merged = JSON.parse(JSON.stringify(shows));
merged.shows.find((s) => s.id === 'trent').flyer = API + '/flyers/trent-0123456789.jpg';

(async () => {
  // 1) Barry answers: its merged schedule (with Jim's uploaded Trent flyer) is used.
  let r = await run({ [STATUS]: NOT_LIVE, [API]: { body: merged } }, MON_8PM_MT);
  assert.strictEqual(r.box.scheduleBase, API);
  assert.strictEqual(r.box.mode, 'flyer');
  assert.strictEqual(r.box.next.show.id, 'trent');
  assert.strictEqual(r.box.next.flyerUrl, API + '/flyers/trent-0123456789.jpg');
  assert.ok(!r.calls.some((u) => u.startsWith(PAGES + 'shows.json')), 'no need for shows.json');

  // 2) Barry down: falls back to shows.json; relative flyer paths resolve against GitHub Pages.
  const SUN_8PM_MT = Date.parse('2026-10-11T20:00:00-06:00'); // next = Dr. Dieter
  r = await run({ [STATUS]: 'down', [API]: 'down', 'https://peertube.wtf/': { body: { isLive: true, state: { id: 4 } } },
    [PAGES + 'shows.json']: { body: shows } }, SUN_8PM_MT);
  assert.strictEqual(r.box.scheduleBase, PAGES + 'shows.json');
  assert.strictEqual(r.box.next.show.id, 'dr-dieter');
  assert.ok(r.box.next.flyerUrl.startsWith(PAGES + 'flyers/dr-dieter.jpg?v='), r.box.next.flyerUrl);

  // 3) Barry answers with an error / junk: also falls back.
  r = await run({ [STATUS]: NOT_LIVE, [API]: { status: 503, body: { ok: false } }, [PAGES + 'shows.json']: { body: shows } }, SUN_8PM_MT);
  assert.strictEqual(r.box.scheduleBase, PAGES + 'shows.json');
  r = await run({ [STATUS]: NOT_LIVE, [API]: { body: { shows: [] } }, [PAGES + 'shows.json']: { body: shows } }, SUN_8PM_MT);
  assert.strictEqual(r.box.scheduleBase, PAGES + 'shows.json');

  // 4) Admin removed the flyer: Barry says flyer "" -> plain event card even though shows.json has one.
  const removed = JSON.parse(JSON.stringify(shows));
  removed.shows.find((s) => s.id === 'dr-dieter').flyer = '';
  r = await run({ [STATUS]: NOT_LIVE, [API]: { body: removed }, [PAGES + 'shows.json']: { body: shows } }, SUN_8PM_MT);
  assert.strictEqual(r.box.mode, 'card');

  console.log('live_box_schedule.test.js OK');
})().catch((e) => { console.error(e); process.exit(1); });
