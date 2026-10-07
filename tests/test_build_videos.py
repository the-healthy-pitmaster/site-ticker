"""Offline tests for the PeerTube homepage video spot (no network)."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_videos as bv  # noqa: E402


def pt_row(name, short, published, **extra):
    row = {
        "name": name,
        "uuid": f"uuid-{short}",
        "shortUUID": short,
        "url": f"https://x.example/videos/watch/uuid-{short}",
        "embedPath": f"/videos/embed/{short}",
        "thumbnailPath": f"/lazy-static/thumbnails/{short}.jpg",
        "publishedAt": published,
        "isLive": False,
        "privacy": {"id": 1, "label": "Public"},
    }
    row.update(extra)
    return row


TIL_RAW = {
    "total": 3,
    "data": [
        pt_row("Matcha and cancer: what the new research shows", "til3", "2026-10-07T13:13:27Z"),
        pt_row("Off insulin in 75 days with type 1 diabetes", "til2", "2026-10-06T22:06:23Z"),
        pt_row("Insulin resistance and your brain", "til1", "2026-10-06T13:13:02Z"),
    ],
}
TIL = bv.parse_peertube_videos(TIL_RAW, "https://tilvids.com", watch_style="url")
YESTERDAY = date(2026, 10, 7)  # build runs Oct 8 -> spot 2 targets Oct 7 (MT)


class ParseTests(unittest.TestCase):
    def test_peertube_links_use_short_w_url_and_embed(self):
        rows = bv.parse_peertube_videos({"data": [pt_row("A", "abc", "2026-10-07T22:00:00Z")]}, bv.PEERTUBE_BASE)
        self.assertEqual(rows[0]["url"], "https://peertube.wtf/w/abc")
        self.assertEqual(rows[0]["embedUrl"], "https://peertube.wtf/videos/embed/abc")
        self.assertEqual(rows[0]["thumbUrl"], "https://peertube.wtf/lazy-static/thumbnails/abc.jpg")

    def test_skips_live_and_non_public(self):
        rows = bv.parse_peertube_videos(
            {"data": [
                pt_row("Live", "l", "2026-10-07T22:00:00Z", isLive=True),
                pt_row("Unlisted", "u", "2026-10-07T22:00:00Z", privacy={"id": 2}),
                pt_row("Ok", "ok", "2026-10-07T21:00:00Z"),
            ]},
            bv.PEERTUBE_BASE,
        )
        self.assertEqual([r["title"] for r in rows], ["Ok"])

    def test_sorted_newest_first(self):
        rows = bv.parse_peertube_videos(
            {"data": [pt_row("Old", "o", "2026-10-01T00:00:00Z"), pt_row("New", "n", "2026-10-07T00:00:00Z")]},
            bv.PEERTUBE_BASE,
        )
        self.assertEqual([r["title"] for r in rows], ["New", "Old"])

    def test_thumbnails_array_fallback(self):
        row = pt_row("A", "abc", "2026-10-07T22:00:00Z")
        row.pop("thumbnailPath")
        row["thumbnails"] = [{"path": "/t/small.jpg", "width": 280}, {"path": "/t/big.jpg", "width": 1280}]
        rows = bv.parse_peertube_videos({"data": [row]}, bv.PEERTUBE_BASE)
        self.assertEqual(rows[0]["thumbUrl"], "https://peertube.wtf/t/big.jpg")

    def test_norm_title(self):
        self.assertEqual(bv.norm_title("Off insulin in 75 days — Type 1!"), bv.norm_title("off insulin in 75 days type 1"))


class SlotTests(unittest.TestCase):
    def test_empty_peertube_fills_with_tilvids(self):
        picks = bv.build_video_slots([], TIL, 1, YESTERDAY)
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0]["platform"], "tilvids")
        self.assertEqual(picks[0]["source"], "tilvids-fill")
        self.assertEqual(picks[0]["title"], "Matcha and cancer: what the new research shows")

    def test_peertube_wins_once_it_has_enough(self):
        pt = bv.parse_peertube_videos(
            {"data": [pt_row("Matcha and cancer: what the new research shows", "p1", "2026-10-07T22:00:00Z")]},
            bv.PEERTUBE_BASE,
        )
        picks = bv.build_video_slots(pt, TIL, 1, YESTERDAY)
        self.assertEqual([p["platform"] for p in picks], ["peertube"])
        self.assertEqual(picks[0]["url"], "https://peertube.wtf/w/p1")
        self.assertFalse(picks[0]["fallback"])

    def test_peertube_newer_than_target_day_still_used(self):
        pt = bv.parse_peertube_videos(
            {"data": [pt_row("Brand new", "p9", "2026-10-09T22:00:00Z")]}, bv.PEERTUBE_BASE
        )
        picks = bv.build_video_slots(pt, TIL, 1, YESTERDAY)
        self.assertEqual(picks[0]["platform"], "peertube")
        self.assertTrue(picks[0]["fallback"])

    def test_fill_skips_videos_already_on_peertube(self):
        pt = bv.parse_peertube_videos(
            {"data": [pt_row("MATCHA and cancer - what the new research shows", "p1", "2026-10-07T22:00:00Z")]},
            bv.PEERTUBE_BASE,
        )
        picks = bv.build_video_slots(pt, TIL, 3, YESTERDAY)
        self.assertEqual(
            [(p["platform"], p["title"]) for p in picks],
            [
                ("peertube", "MATCHA and cancer - what the new research shows"),
                ("tilvids", "Off insulin in 75 days with type 1 diabetes"),
                ("tilvids", "Insulin resistance and your brain"),
            ],
        )

    def test_both_empty(self):
        self.assertEqual(bv.build_video_slots([], [], 1, YESTERDAY), [])


class SpotTests(unittest.TestCase):
    def setUp(self):
        self._pt, self._til = bv.fetch_peertube, bv.fetch_tilvids

    def tearDown(self):
        bv.fetch_peertube, bv.fetch_tilvids = self._pt, self._til

    def test_does_not_call_tilvids_when_peertube_has_enough(self):
        bv.fetch_peertube = lambda: bv.parse_peertube_videos(
            {"data": [pt_row("A", "a", "2026-10-07T22:00:00Z")]}, bv.PEERTUBE_BASE
        )

        def boom():
            raise AssertionError("TILvids should not be fetched")

        bv.fetch_tilvids = boom
        spot = bv.peertube_spot(YESTERDAY)
        self.assertEqual(spot["spot"], 2)
        self.assertEqual(spot["platform"], "peertube")
        self.assertEqual(spot["channelUrl"], "https://peertube.wtf/c/thehealthypitmaster")

    def test_tilvids_fill_when_peertube_down_or_empty(self):
        bv.fetch_peertube = lambda: []
        bv.fetch_tilvids = lambda: TIL
        spot = bv.peertube_spot(YESTERDAY)
        self.assertEqual((spot["platform"], spot["source"]), ("tilvids", "tilvids-fill"))
        self.assertTrue(spot["embedUrl"].startswith("https://tilvids.com/videos/embed/"))

    def test_empty_spot_shape(self):
        bv.fetch_peertube = lambda: []
        bv.fetch_tilvids = lambda: []
        spot = bv.peertube_spot(YESTERDAY)
        self.assertEqual(spot["url"], "")
        self.assertEqual(spot["platform"], "peertube")
        self.assertEqual(spot["channelUrl"], bv.PEERTUBE_CHANNEL_URL)


if __name__ == "__main__":
    unittest.main()
