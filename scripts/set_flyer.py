#!/usr/bin/env python3
"""Swap the flyer for one show in shows.json (homepage "Upcoming Event" box).

  python3 scripts/set_flyer.py trent ~/Downloads/trent-oct-13.jpg   # new weekly Trent flyer
  python3 scripts/set_flyer.py two-sista-docs new-flyer.png
  python3 scripts/set_flyer.py dr-nick --clear                       # no flyer -> normal event card

Resizes to a phone-friendly JPEG (max 720x1280), writes flyers/<show-id>.jpg, and
points that show's "flyer" at it with a ?v=<hash> so browsers pick up the new one.
Commit + push shows.json and the flyer afterwards (GitHub Pages serves them).
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOWS = ROOT / "shows.json"
MAX_W, MAX_H = 720, 1280


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show_id")
    ap.add_argument("image", nargs="?")
    ap.add_argument("--clear", action="store_true", help="remove the flyer for this show")
    args = ap.parse_args(argv)

    data = json.loads(SHOWS.read_text())
    show = next((s for s in data["shows"] if s.get("id") == args.show_id), None)
    if not show:
        ids = ", ".join(s.get("id", "?") for s in data["shows"])
        sys.exit(f"Unknown show id {args.show_id!r}. Known: {ids}")

    if args.clear:
        show["flyer"] = ""
    else:
        if not args.image:
            sys.exit("Give an image path, or --clear.")
        from PIL import Image  # pip install Pillow

        im = Image.open(args.image).convert("RGB")
        im.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
        raw = buf.getvalue()
        out = ROOT / "flyers" / f"{args.show_id}.jpg"
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(raw)
        show["flyer"] = f"flyers/{out.name}?v={hashlib.sha256(raw).hexdigest()[:10]}"
        print(f"Wrote {out.relative_to(ROOT)} ({len(raw)//1024} KB, {im.size[0]}x{im.size[1]})")

    SHOWS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{show['name']}: flyer = {show['flyer'] or '(none: normal event card)'}")


if __name__ == "__main__":
    main()
