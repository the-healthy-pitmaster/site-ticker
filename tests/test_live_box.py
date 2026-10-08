"""Homepage live video box (live-box.js + shows.json)."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LiveBoxJsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_logic(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "live_box.test.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_schedule_source_barry_then_shows_json(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "live_box_schedule.test.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_stream_keys_in_client(self):
        src = (ROOT / "live-box.js").read_text().lower()
        for bad in ("rtmp", "stream_key", "streamkey", "live/key"):
            self.assertNotIn(bad, src)

    def test_videos_js_loads_live_box(self):
        self.assertIn("live-box.js", (ROOT / "videos.js").read_text())


class ShowsJsonTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "shows.json").read_text())

    def test_schedule_shape(self):
        self.assertEqual(self.data["timezone"], "America/Denver")
        ids = [s["id"] for s in self.data["shows"]]
        self.assertEqual(ids, ["dr-nick", "dr-dieter", "trent", "two-sista-docs"])
        for s in self.data["shows"]:
            self.assertIn(s["weekday"], ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"))
            self.assertRegex(s["time"], r"^\d{1,2}:\d{2}$")

    def test_flyers_exist(self):
        for s in self.data["shows"]:
            if s.get("flyer"):
                self.assertTrue((ROOT / s["flyer"].split("?")[0]).is_file(), s["flyer"])

    def test_set_flyer_script(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed")
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "scripts").mkdir()
            shutil.copy(ROOT / "scripts" / "set_flyer.py", repo / "scripts")
            shutil.copy(ROOT / "shows.json", repo / "shows.json")
            img = repo / "in.png"
            Image.new("RGB", (1152, 2048), "navy").save(img)
            subprocess.run(["python3", str(repo / "scripts" / "set_flyer.py"), "trent", str(img)], check=True, capture_output=True)
            data = json.loads((repo / "shows.json").read_text())
            trent = next(s for s in data["shows"] if s["id"] == "trent")
            self.assertRegex(trent["flyer"], r"^flyers/trent\.jpg\?v=[0-9a-f]{10}$")
            with Image.open(repo / "flyers" / "trent.jpg") as out:
                self.assertLessEqual(out.size[1], 1280)
            subprocess.run(["python3", str(repo / "scripts" / "set_flyer.py"), "trent", "--clear"], check=True, capture_output=True)
            data = json.loads((repo / "shows.json").read_text())
            self.assertEqual(next(s for s in data["shows"] if s["id"] == "trent")["flyer"], "")


if __name__ == "__main__":
    unittest.main()
