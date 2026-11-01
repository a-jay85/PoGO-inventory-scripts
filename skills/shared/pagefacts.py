"""What the door needs to know, read off the list tile and the Pokémon's own page instead of searches.

  tile_icons(path, tile)   shiny (the dark sparkle under the CP) and background (the pale blue snowflake beside the
                           sprite), from the list capture the tile was tapped on
  candy_xl(texts)          the Candy XL count on the page's top half (the number over "CANDY XL")
  bottom(reads)            the page's bottom: traded ("OBTAINED IN A TRADE"), the catch or hatch place, in
                           California or not (not: 100 km+ away, like the distance100- search)

Each says None when it can't tell. Pixel sizes are the Android capture's (406 px wide): other sizes are scaled.
Taught 2026-10-31 on Pixel captures: shiny tiles score 56-62 sparkle pixels (others 0), background tiles 0.54-1.0
icon match (others 0).
"""
import re

import ui

CAP_W = 406  # the Android capture's width, that the boxes below are measured in

# shiny: dark teal sparkle pixels left of the sprite, under the CP. Machamp's blue doesn't pass (g - r too small)
SPARKLE_BOX = (-36, -8, -44, -18)  # x0, x1, y0, y1 from the middle of the tile image
SPARKLE_MIN = 25
sparkle = lambda p: p[1] - p[0] > 25 and 5 < p[2] - p[1] < 45 and p[0] + p[1] + p[2] < 330

# background: an icon's shape in pale blue pixels, anywhere around the sprite (it sits wherever the sprite leaves
# room: right of it, or over its left side on a wide one like Venusaur). Two icons: the snowflake (a special
# background) and the globe (a location background, like Golden Gate's or Pikachu's)
ICON_BOX = (-60, 60, -30, 40)
ICON_MIN = 0.6  # best overlap (shared / either) of a shape with the tile's pale blue pixels
# pale blue, and bluer than green: the soft teal glow some tiles have behind the sprite (Baltoy, Bronzor) is as
# green as it is blue (b - g -20..0), and it read as a background (2026-11-01). The icons' b - g is mostly 0..60
pale_blue = lambda p: p[2] > 200 and p[2] - p[0] > 25 and p[1] > 170 and p[2] - p[1] >= 0
SNOWFLAKE = """
..................#...
.......#.......#.##...
......###......######.
..#...###..##...#####.
..###.###.###.########
..###########.########
...#########...######.
....##...##....####.##
#####.###.#####..##...
#####.###.#####.......
.####.##..####...#....
...###.#.###...#####..
..###########..#####..
.####.###.###..#####..
..##..###..##..#####..
......###........#....
......##..............
"""
GLOBE = """
.......########.......
.....############.....
....#####.##.#####....
...##.##..##..##.##...
..###.##..##..##..##..
.####################.
.##.##############.##.
##...##...##...##...##
##..##....##....##..##
##..##....##....##..##
######################
######################
##..##....##....##..##
##..##....##....##..##
##...##...##....#...##
.##.##############.##.
.####################.
..######..##...#####..
...##.##..##..##.###..
....#####.##.#####....
.....############.....
.......########.......
"""
shape = lambda art: {(x, y) for y, row in enumerate(art.split()) for x, ch in enumerate(row) if ch == "#"}
SHAPES = {"snowflake": shape(SNOWFLAKE), "globe": shape(GLOBE)}


def _pixels(im, box, test):
    W, H = im.size
    px = im.load()
    x0, y0, x1, y1 = box
    return {(x, y) for y in range(max(y0, 0), min(y1, H)) for x in range(max(x0, 0), min(x1, W)) if test(px[x, y])}


def _match(on, box, shape):
    """best overlap of shape with the on-pixels, anywhere in box"""
    x0, y0, x1, y1 = box
    w, h = max(x for x, _ in shape) + 1, max(y for _, y in shape) + 1
    best = 0
    for y in range(y0, y1 - h + 1):
        for x in range(x0, x1 - w + 1):
            both = sum((x + a, y + b) in on for a, b in shape)
            if both * 2 < len(shape):
                continue
            here = sum((x + a, y + b) in on for a in range(w) for b in range(h))
            best = max(best, both / (len(shape) + here - both))
    return best


def icon_score(im, box):
    """the best match of any background icon in box (0..1)"""
    on = _pixels(im, box, pale_blue)
    return max(_match(on, box, s) for s in SHAPES.values())


def tile_icons(path, tile):
    """tile: (name, cp, x, y) from ui.tiles on this capture -> {"shiny": bool, "background": bool}, or {} if the
    picture can't be read"""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
    except Exception:
        return {}
    if im.size[0] != CAP_W:  # the boxes are in Android capture pixels
        im = im.resize((CAP_W, round(im.size[1] * CAP_W / im.size[0])))
    W, H = im.size
    cx, cy = tile[2] * W, tile[3] * H
    at = lambda b: (int(cx + b[0]), int(cy + b[2]), int(cx + b[1]), int(cy + b[3]))
    shiny = len(_pixels(im, at(SPARKLE_BOX), sparkle)) >= SPARKLE_MIN
    background = icon_score(im, at(ICON_BOX)) >= ICON_MIN
    return {"shiny": shiny, "background": background}


def candy_xl(texts):
    """the Candy XL count: the number over the "CANDY XL" label (OCR may split it: "... CANDY" then "XL" under it).
    -> int, or None if it doesn't read (a one-digit count often doesn't at the capture's size)"""
    labels = [t for t in texts if re.search(r"\bCANDY XL$", ui.norm(t[4]))]
    if not labels:
        xl = [t for t in texts if ui.norm(t[4]) == "XL"]
        labels = [c for c in texts if xl and re.search(r"\bCANDY$", ui.norm(c[4]))
                  and any(0 < x[1] - c[1] < 0.04 and abs(x[0] - c[0]) < 0.15 for x in xl)]
    if len(labels) != 1:
        return None
    lab = labels[0]
    got = [int(re.sub(r"\D", "", t[4])) for t in texts if 0.01 < lab[1] - t[1] < 0.06
           and abs((t[0] + t[2] / 2) - (lab[0] + lab[2] / 2)) < 0.12 and re.fullmatch(r"\d[\d,.]*", t[4].strip())]
    return got[0] if len(got) == 1 else None


def candy_xl_close(path, texts=None):
    """candy_xl on a 3x crop of the candy row, for a count too small to read whole. texts: the same capture's read,
    to find the row (a Dynamax one's Max Moves box pushes it down). None when the row isn't on screen"""
    from PIL import Image
    im = Image.open(path)
    W, H = im.size
    rows = [t[1] for t in texts or () if re.search(r"\bCANDY\b", ui.norm(t[4]))]
    if texts is not None and not rows:
        return None
    y0, y1 = (min(rows) - 0.08, max(rows) + 0.06) if rows else (0.55, 0.8)
    top, bottom = int(max(y0, 0) * H), int(min(y1, 1) * H)
    crop = im.crop((0, top, W, bottom)).resize((W * 3, (bottom - top) * 3), Image.LANCZOS)
    tmp = ui.TMP + "_xl.png"
    crop.save(tmp)
    k = (bottom - top) / H  # back to the whole page's fractions
    return candy_xl([(t[0], top / H + t[1] * k, t[2], t[3] * k, t[4]) for t in ui.ocr(tmp)])


def bottom(reads):
    """reads: the page bottom's texts, one list per read (trades.scrolled_bottom). -> {"traded", "california"}:
    True / False, or None where it can't tell (the caught or hatched box didn't read)"""
    out = {"traded": None, "california": None}
    for texts in reads:
        rows = sorted(texts, key=lambda t: t[1])
        label = [t for t in rows if re.search(r"\b(CAUGHT|HATCHED)\b", ui.norm(t[4]))]
        if len(label) != 1:
            continue
        traded = any("OBTAINED IN A TRADE" in ui.norm(t[4]) for t in rows)
        date = next((t for t in rows if t[1] > label[0][1] and re.search(r"\b\d{1,2}/\d{1,2}/20\d\d\b", t[4])), None)
        place = " ".join(t[4] for t in rows if label[0][1] < t[1] < (date[1] if date else 1) and t[0] < 0.6)
        california = "CALIFORNIA" in ui.norm(place) if place.strip() else None
        for k, v in (("traded", traded), ("california", california)):
            if v is not None:
                out[k] = v if out[k] in (None, v) else None  # two reads that disagree: can't tell
    return out
