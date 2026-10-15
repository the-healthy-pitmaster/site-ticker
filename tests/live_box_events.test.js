const assert = require('assert');
const { nextShow } = require('../live-box.js');
const sched = { timezone: 'America/Denver', timezoneLabel: 'MT', shows: [
  { id: 'dr-dieter', weekday: 'Mon', time: '18:00', durationMinutes: 90 },
  { id: 'trent', weekday: 'Tue', time: '19:00', durationMinutes: 90 },
  { id: 'two-sista-docs', weekday: 'Wed', time: '19:00', durationMinutes: 90 },
  { id: 'dr-nick', weekday: 'Sun', time: '18:00', durationMinutes: 90 },
  { id: 'dieter-thu', weekday: 'Thu', time: '10:00', durationMinutes: 90, timezone: 'America/Denver' },
  { id: 'pao-thu', weekday: 'Thu', time: '19:00', durationMinutes: 90, timezone: 'America/Denver' },
  { id: 'pao-tue', weekday: 'Tue', time: '13:00', durationMinutes: 90, timezone: 'America/Denver' },
  { id: 'nyc-once', date: '2026-10-17', time: '12:00', durationMinutes: 60, timezone: 'America/New_York', timezoneLabel: 'ET' },
]};
const at = (s) => nextShow(sched, new Date(s));
// Thu Oct 15 2026, MDT = UTC-6
assert.equal(at('2026-10-15T15:00:00Z').show.id, 'dieter-thu');        // 9:00 MT -> Dieter 10:00
assert.equal(at('2026-10-15T17:29:00Z').show.id, 'dieter-thu');        // 11:29 still inside Dieter
assert.equal(at('2026-10-15T17:30:00Z').show.id, 'pao-thu');           // 11:30 Dieter ended -> Pao 7 PM
assert.equal(at('2026-10-16T02:29:00Z').show.id, 'pao-thu');           // 8:29 PM inside Pao
const r = at('2026-10-16T02:30:00Z');                                  // Pao over -> one-off Sat noon ET
assert.equal(r.show.id, 'nyc-once'); assert.ok(/12:00 PM ET/.test(r.when), r.when);
assert.equal(at('2026-10-17T17:00:00Z').show.id, 'dr-nick');           // one-off over -> Sun Nick
assert.equal(at('2026-10-19T19:00:00Z').show.id, 'dr-dieter');         // Mon 1 PM -> Dieter Mon
assert.equal(at('2026-10-20T15:00:00Z').show.id, 'pao-tue');           // Tue 9 AM -> Pao Tue 1 PM
assert.equal(at('2026-10-20T20:31:00Z').show.id, 'trent');             // Pao Tue over -> Trent
assert.equal(at('2026-10-21T15:00:00Z').show.id, 'two-sista-docs');
// DST: Thu Nov 5 2026 MST = UTC-7; Pao 7 PM MT = 02:00Z next day
assert.equal(at('2026-11-05T20:00:00Z').start.toISOString(), '2026-11-06T02:00:00.000Z');
console.log('live_box_events.test.js OK');
// Skip: Pao Thu Oct 15 skipped -> after Dieter ends, the one-off Saturday is next
sched.shows[5].skip = ['2026-10-15'];
assert.equal(at('2026-10-15T17:30:00Z').show.id, 'nyc-once');
assert.equal(at('2026-10-20T15:00:00Z').show.id, 'pao-tue');
console.log('skip OK');
