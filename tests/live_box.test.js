// Pure-logic checks for live-box.js (run by tests/test_live_box.py via node).
'use strict';
const assert = require('assert');
const path = require('path');
const lb = require(path.join(__dirname, '..', 'live-box.js'));
const shows = require(path.join(__dirname, '..', 'shows.json'));

// --- live status normalisation
const ptWaiting = { shortUUID: '1gBXURNMWzNVLeTzEMMRN6', name: 'The Science Behind FGS', isLive: true, state: { id: 4, label: 'Waiting for livestream' } };
const ptLive = Object.assign({}, ptWaiting, { state: { id: 1, label: 'Published' } });
assert.strictEqual(lb.normalizeStatus(ptWaiting).live, false);
const n = lb.normalizeStatus(ptLive);
assert.strictEqual(n.live, true);
assert.strictEqual(n.source, 'peertube');
assert.strictEqual(n.embedUrl, 'https://peertube.wtf/videos/embed/1gBXURNMWzNVLeTzEMMRN6');
assert.strictEqual(lb.normalizeStatus({ live: false, source: null }).live, false);
assert.strictEqual(lb.normalizeStatus({ live: true, source: 'youtube', embedUrl: 'https://www.youtube-nocookie.com/embed/abcDEF12345' }).source, 'youtube');
assert.strictEqual(lb.normalizeStatus({ live: true, source: 'evil', embedUrl: 'https://x' }).live, false);
assert.strictEqual(lb.normalizeStatus(null), null);
assert.strictEqual(lb.normalizeStatus({ hello: 1 }), null);

// --- embed URLs: muted autoplay in the box, sound in the popup
const yt = { source: 'youtube', embedUrl: 'https://www.youtube-nocookie.com/embed/abcDEF12345' };
assert.ok(lb.embedSrc(yt).includes('autoplay=1&mute=1&playsinline=1'));
assert.ok(lb.embedSrc(yt, { muted: false }).includes('mute=0'));
const pt = { source: 'peertube', embedUrl: 'https://peertube.wtf/videos/embed/x' };
assert.ok(lb.embedSrc(pt).includes('autoplay=1&muted=1'));
assert.ok(lb.embedSrc(pt, { muted: false }).includes('muted=0'));

// --- next show (Mountain Time)
function next(iso) { return lb.nextShow(shows, new Date(iso)); }
let r = next('2026-10-08T03:00:00Z'); // Wed Oct 7, 9:00 PM MT
assert.strictEqual(r.show.id, 'dr-nick');
assert.strictEqual(r.when, 'Sun, Oct 11 · 6:00 PM MT');
r = next('2026-10-12T02:00:00Z'); // Sun 8:00 PM MT (Nick's window over)
assert.strictEqual(r.show.id, 'dr-dieter');
assert.strictEqual(r.when, 'Mon, Oct 12 · 6:00 PM MT');
r = next('2026-10-12T00:45:00Z'); // Sun 6:45 PM MT: still Nick's show window
assert.strictEqual(r.show.id, 'dr-nick');
r = next('2026-10-14T03:00:00Z'); // Tue 9:00 PM MT
assert.strictEqual(r.show.id, 'two-sista-docs');
assert.strictEqual(r.when, 'Wed, Oct 14 · 7:00 PM MT');
r = next('2026-10-31T18:00:00Z'); // Sat before the DST change -> still 6:00 PM wall clock
assert.strictEqual(r.when, 'Sun, Nov 1 · 6:00 PM MT');
assert.strictEqual(r.start.toISOString(), '2026-11-02T01:00:00.000Z');
assert.strictEqual(lb.nextShow({ shows: [] }, new Date()), null);
assert.strictEqual(lb.nextShow({ shows: [{ weekday: 'Funday', time: '18:00' }] }, new Date()), null);

// --- schedule payload check (Barry /api/live-shows or shows.json)
assert.strictEqual(lb.validSchedule(shows), true);
assert.strictEqual(lb.validSchedule({ shows: [] }), false);
assert.strictEqual(lb.validSchedule({ ok: false, error: 'schedule unavailable' }), false);
assert.strictEqual(lb.validSchedule(null), false);
assert.strictEqual(lb.DEFAULTS.showsApiUrl, 'https://barry-production-c225.up.railway.app/api/live-shows');

console.log('live_box.test.js OK');
