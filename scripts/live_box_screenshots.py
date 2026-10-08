"""Screenshots of the live video box on the REAL homepage, with our branch's JS swapped in.

Network routing (nothing is deployed):
  site-ticker/videos.js, site-ticker/live-box.js -> local live-video-box branch files
  Barry /api/live-status -> scenario JSON (real current answer for 'event card')
"""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

TICKER = pathlib.Path('/workspace/live-video-box-ticker')
OUT = pathlib.Path('/workspace/live-video-box-screenshots'); OUT.mkdir(exist_ok=True)
REAL = json.load(open('/workspace/live-video-box-work/real_status_now.json'))

PT_LIVE = {  # simulated: PeerTube permanent live streaming (embed uses a real PeerTube video so the frame shows picture)
  "live": True, "source": "peertube", "title": "The Science Behind FGS",
  "videoId": "1gBXURNMWzNVLeTzEMMRN6", "watchUrl": "https://peertube.wtf/w/1gBXURNMWzNVLeTzEMMRN6",
  "embedUrl": "https://peertube.wtf/videos/embed/oXW8dJ2aJZDVk3MTK1j512", "embeddable": True, "pollSeconds": 60}
YT_LIVE = {  # simulated: PeerTube not live, YouTube live (embed uses one of Jim's real YouTube videos)
  "live": True, "source": "youtube", "title": "Feel Great Q&A with Trent — LIVE",
  "videoId": "nRa5NXH1gO4", "watchUrl": "https://www.youtube.com/watch?v=nRa5NXH1gO4",
  "embedUrl": "https://www.youtube-nocookie.com/embed/nRa5NXH1gO4", "embeddable": True, "pollSeconds": 60}

from datetime import datetime, timezone, timedelta
MT = timezone(timedelta(hours=-6))  # MDT in October
CLOCK = {
    'event-card': datetime(2026, 10, 7, 21, 0, tzinfo=MT),        # Wed 9 PM: next = Sun Dr. Nick (no flyer yet)
    'flyer-dieter': datetime(2026, 10, 11, 20, 0, tzinfo=MT),     # Sun 8 PM: next = Mon Dr. Dieter
    'flyer-two-sista': datetime(2026, 10, 13, 21, 0, tzinfo=MT),  # Tue 9 PM: next = Wed Two Sista' Docs
}

def run(p, device, scen):
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                          args=['--autoplay-policy=no-user-gesture-required'])
    if device == 'desktop':
        ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    else:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1')
    status = {'peertube-live': PT_LIVE, 'youtube-fallback': YT_LIVE}.get(scen, REAL)
    hits = {'status': 0}
    import re as _re
    BASE = 'https://the-healthy-pitmaster.github.io/site-ticker/'
    def serve_local(r):
        path = r.request.url[len(BASE):].split('?')[0]
        f = TICKER / path
        ct = {'js': 'application/javascript', 'json': 'application/json', 'jpg': 'image/jpeg'}[path.rsplit('.', 1)[1]]
        r.fulfill(status=200, content_type=ct, body=f.read_bytes())
    ctx.route(_re.compile(r'^https://the-healthy-pitmaster\.github\.io/site-ticker/(videos\.js|live-box\.js|shows\.json|flyers/[\w-]+\.jpg)(\?.*)?$'), serve_local)
    if scen in CLOCK:
        ctx.clock.set_fixed_time(CLOCK[scen])
    def st(r):
        hits['status'] += 1
        r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(status))
    ctx.route('https://barry-production-c225.up.railway.app/api/live-status*', st)
    pg = ctx.new_page()
    logs = []
    pg.on('console', lambda m: logs.append(m.text) if 'live-box' in m.text else None)
    pg.goto('https://www.thehealthypitmaster.com/', wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_function("document.querySelector('.event-card[data-live-box-ready]')", timeout=30000)
    pg.wait_for_timeout(2500)
    live = pg.locator('#live')
    live.scroll_into_view_if_needed()
    pg.evaluate("window.scrollBy(0, -70)")
    pg.wait_for_timeout(9000 if scen.endswith('live') or scen.startswith('youtube') else 3000)
    tag = f"{scen}-{device}"
    state = pg.evaluate("({live: document.documentElement.getAttribute('data-live-box'), cls: document.querySelector('.event-card').className, iframe: (document.querySelector('.thp-live-box iframe')||{}).src||null, when: (document.querySelector('.thp-live-when')||{}).textContent||null, replays: document.querySelectorAll('.replay-card[data-video-loaded]').length})")
    if device == 'desktop':
        live.screenshot(path=str(OUT / f"{tag}.png"))
    else:
        pg.locator('.live-grid').screenshot(path=str(OUT / f"{tag}.png"))
    print(tag, state, 'status-hits', hits['status'], logs)
    if scen in ('peertube-live', 'youtube-fallback', 'flyer-dieter'):
        if scen == 'flyer-dieter':
            pg.locator('.thp-flyer-frame').click()  # tapping the flyer itself
        else:
            pg.locator('.thp-live-actions .btn').click()
        pg.wait_for_timeout(9000 if scen != 'flyer-dieter' else 2000)
        pg.screenshot(path=str(OUT / f"{scen}-popup-{device}.png"))
        st2 = pg.evaluate("({modalIframe: (document.querySelector('.thp-live-modal iframe')||{}).src||null, modalImg: (document.querySelector('.thp-live-modal img')||{}).src||null, smallIframe: !!document.querySelector('.thp-live-box iframe'), away: !!document.querySelector('.thp-live-away')})")
        print('  popup open', st2)
        pg.locator('.thp-live-close').click()
        pg.wait_for_timeout(500)
        st3 = pg.evaluate("({modal: !!document.querySelector('.thp-live-modal'), smallIframe: (document.querySelector('.thp-live-box iframe')||{}).src||null, htmlCls: document.documentElement.className})")
        print('  popup closed', st3)
    b.close()

with sync_playwright() as p:
    scens = sys.argv[1:] or ['event-card', 'flyer-dieter', 'flyer-two-sista', 'peertube-live', 'youtube-fallback']
    for scen in scens:
        for device in ('desktop', 'mobile'):
            run(p, device, scen)
