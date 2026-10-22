#!/usr/bin/env python3
"""Look at the phone (or a saved png) for as few tokens as possible. Claude pays for a picture by its
pixels (about width x height / 750 tokens), so read the text first and crop before looking.

  peek.py [png] --text               the screen's text, one row per line, top to bottom ("12| CP 927  HP 120")
                                     The number is how far down the row sits, in % of the screen height.
  peek.py [png] [--crop C] [--max N] save a small picture to /tmp/peek.png and print its size and cost. Read that.
                                     C: top, mid, bottom, or x0,y0,x1,y1 as fractions (0,0.6,1,0.8).
                                     N: longest side in pixels after the crop (default 800).

With no png it takes a fresh capture (ui.capture(); set POGO_PHONE=android for the Pixel). A crop of a fresh
Android capture uses the phone's full-size screenshot, so small text stays sharp.
"""
import argparse, os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ui

OUT = "/tmp/peek.png"
CROPS = {"top": (0, 0, 1, 0.25), "mid": (0, 0.25, 1, 0.75), "bottom": (0, 0.75, 1, 1)}


def rows(texts, gap=0.012):
    """OCR boxes -> rows of text, top to bottom, left to right"""
    out = []
    for x, y, w, h, t in sorted(texts, key=lambda b: b[1] + b[3] / 2):
        mid = y + h / 2
        if out and mid - out[-1][0] < gap:
            out[-1][1].append((x, t))
        else:
            out.append([mid, [(x, t)]])
    return [(mid, "  ".join(t for _, t in sorted(r))) for mid, r in out]


def main():
    p = argparse.ArgumentParser(usage=__doc__)
    p.add_argument("png", nargs="?")
    p.add_argument("--text", action="store_true")
    p.add_argument("--crop")
    p.add_argument("--max", type=int, default=800)
    a = p.parse_args()

    path = a.png or ui.capture()[0]
    if a.text:
        for mid, line in rows(ui.ocr(path)):
            print(f"{round(mid * 100):2d}| {line}")
        return

    box = CROPS.get(a.crop) if a.crop in CROPS else tuple(map(float, a.crop.split(","))) if a.crop else None
    if box and not a.png and ui.ANDROID:
        path = ui.android.sharp()
    im = Image.open(path).convert("RGB")
    if box:
        W, H = im.size
        im = im.crop((round(box[0] * W), round(box[1] * H), round(box[2] * W), round(box[3] * H)))
    im.thumbnail((a.max, a.max))
    im.save(OUT)
    print(f"{OUT}  {im.width}x{im.height}  ~{im.width * im.height // 750} tokens")


if __name__ == "__main__":
    try:
        main()
    except ui.Refused as e:
        sys.exit(str(e))
