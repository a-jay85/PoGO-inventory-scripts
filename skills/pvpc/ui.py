#!/usr/bin/env python3
"""Screen reader + tap planner for the /pvpc skill. Reads the iPhone Mirroring window as text so
Claude doesn't need screenshots, and hands back fuzzed tap spots in screenshot coordinates.

  ui.py calib <sx> <sy>   after mouse_move to (sx, sy) in a screenshot: learn screenshot->screen scale
  ui.py read [png]        what's on screen: detail (name/CP/HP), menu, appraisal (IVs + verdict), ...
  ui.py tap <target>      "x y" to click, in screenshot coords. Targets: tile N, menu, close, dialog,
                          pencil, field, search, star, or a word on screen (APPRAISE, TAG, DONE, OK, CANCEL,
                          PvpC, Nope, IVC, Pokémon tab)
  ui.py look              save the window capture to /tmp/pvpc_cap.png (Read it if you must see it)
  ui.py press <target>    plan a tap like `tap` and do it (Android: adb taps the phone, no clicking needed)

With POGO_PHONE=android the screen comes from the phone's own screenshots and taps go through adb (see android.py).
"""
import json, os, random, re, shutil, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "helper")
CALIB = os.path.join(HERE, ".calib.json")
STATE = os.path.join(HERE, ".state.json")
CAP = "/tmp/pvpc_cap.png"
ANDROID = os.environ.get("POGO_PHONE", "").lower() == "android"
if ANDROID:
    import android

# Never produce a tap on or near these.
HAZARDS = ("TRANSFER", "POWER UP", "EVOLVE", "PURIFY", "MEGA EVOLVE", "UNLOCK", "TRADE", "BUDDY", "NEW ATTACK")
HAZARD_MARGIN = 0.02  # of window height, around each hazard box


class Refused(Exception):
    """a tap the script won't plan; message starts with REFUSED where it's a safety call"""


class Moving(Refused):
    """screen still animating: try again in a moment"""


TAPS = ("click", "drag", "scroll", "key", "type")
_seen = None  # (when, path copy, texts, bounds, screen): the latest look, until the next tap or key
_older = None  # the look before _seen


def remember(path, texts, bounds):
    """keep a look so plan() can count it as its first one (no tap since, so it's still the screen)"""
    global _seen, _older
    _older = _seen  # the look before, if no tap came between: two that agree make plan()'s stillness check
    copy = "/tmp/pvpc_seen%d.png" % (not (_seen and _seen[1].endswith("0.png")))
    shutil.copyfile(path, copy)
    _seen = (time.time(), copy, texts, list(bounds), classify(texts))


def sh(*a):
    global _seen, _older
    if a[:1] == (HELPER,) and len(a) > 1 and a[1] in TAPS:
        _seen = _older = None
    if ANDROID and a[:1] == (HELPER,) and len(a) > 1 and a[1] in android.ACTIONS:
        return android.act(*a[1:])
    return subprocess.run(a, capture_output=True, text=True, check=True).stdout


def ensure_helper():
    src = os.path.join(HERE, "helper.swift")
    if not os.path.exists(HELPER) or os.path.getmtime(HELPER) < os.path.getmtime(src):
        sh("swiftc", "-O", src, "-o", HELPER)


def window():
    ensure_helper()
    try:
        wid, x, y, w, h = sh(HELPER, "win").split()
    except subprocess.CalledProcessError:
        raise Refused("iPhone Mirroring window not found (is it open and on screen?)")
    return int(wid), float(x), float(y), float(w), float(h)


def capture():
    if ANDROID:
        ensure_helper()
        try:
            return android.capture(CAP)
        except android.NotReady as e:
            raise Refused(str(e))
    wid, *bounds = window()
    sh("screencapture", "-l", str(wid), "-o", "-x", CAP)
    return CAP, bounds


def ocr(path):
    ensure_helper()
    out = []
    for line in sh(HELPER, "ocr", path).splitlines():
        box, _, text = line.partition("\t")
        x, y, w, h = map(float, box.split())
        out.append((x, y, w, h, text.strip().translate(LOOKALIKES)))
    return out


# OCR now and then reads a Latin letter as its Cyrillic twin ('сP 927', 'AТК')
LOOKALIKES = str.maketrans("АВЕКМНОРСТХаеорсухіІ", "ABEKMHOPCTXaeopcyxiI")


def find(texts, pred):
    return [t for t in texts if pred(t[4])]


# OCR sometimes reads a Latin letter as its Cyrillic or Greek twin ('нootHooT'): map them back before dropping non A-Z
LOOKALIKE = str.maketrans("АВСЕНІЈКМОРЅТХУаbesнікмопрѕтхуΑΒΕΗΙΚΜΝΟΡΤΧΥΖ",
                          "ABCEHIJKMOPSTXYabesнikmonpstxyABEHIKMNOPTXYZ".replace("н", "h"))


def norm(s):
    return re.sub(r"[^A-Z ]", "", s.translate(LOOKALIKE).upper()).strip()


def is_label(s, label):
    """OCR sometimes tacks a stray letter onto a bar label (Duskull's read 'Attack l'), or glues the cursor on ('Defensel')"""
    return re.fullmatch(re.escape(label) + r"( [A-Z]|[LI])?", norm(s)) is not None


# ---------- screen classification ----------

def classify(texts):
    words = [norm(t[4]) for t in texts]
    if "SEARCH" in {w.lstrip("Q ").strip() for w in words} and sum(bool(re.match(r"CP\s*\d", w.upper())) for w in [t[4] for t in texts]) >= 3:
        return "list"
    if any(w.startswith("SET NICKNAME") for w in words):  # a stray cursor can glue on: "Set Nicknamel"
        return "rename"
    if any(w.startswith("TAG") and "POK" in w for w in words) and "DONE" in words:
        return "tags"
    if any(is_label(w, "ATTACK") for w in words) and any(is_label(w, "DEFENSE") for w in words):
        return "appraisal"
    # the intro line wraps in different places ("...check out / your 67 d?"): CHECK OUT alone is enough
    if any("CHECK OUT" in w for w in words) or any(w.startswith("OUT YOUR") for w in words):
        return "appraise-intro"
    if any(w.startswith("APPRAISE") for w in words) and any(w.startswith("TRANSFER") for w in words):
        return "menu"
    if any(re.search(r"\d+\s*/\s*\d+\s*HP", t[4]) for t in texts):
        return "detail"
    if ("TAGS" in words or "EGGS" in words) and any("HAVE THIS TAG" in w for w in words) \
            or sum("HAVE THIS TAG" in w for w in words) >= 3:  # scrolled: header may be gone
        return "tag-tab"
    # a typed search with few (or no) results: the search bar ("Q 4&shadow") is still on top
    if search_box(texts) and not any(is_label(w, "ATTACK") for w in words):
        return "list"
    # list scrolled so the search bar is off screen (or a search is typed in): still a grid of CPs
    if sum(bool(re.fullmatch(r"CP\s*\d+", t[4].upper().replace(" ", ""))) for t in texts) >= 6:
        return "list"
    return "unknown"


def clean_name(s):
    """OCR sometimes reads the pencil icon after the name as ' /', a dot ('Shinx.') or a Cyrillic letter ('Raltsр').
    No species name ends in punctuation; done names keep their * and ^"""
    s = re.sub(r"[\u0400-\u04ff]+$", "", s)
    return re.sub(r"[\s/|\\.,:;'`’]+$", "", s).strip()


def tile_name(name):
    """a tile name without the tag icon in front, which OCR reads as •, $, or a 9 ('996 HD' is icon + '96 HD')"""
    n = re.sub(r"^[^\w(]+", "", (name or "").strip())
    lead = re.match(r"\d+", n)
    if lead and (int(lead.group()) > 100 or len(lead.group()) == 3 and lead.group()[0] == "0"):  # icon read as 0: "098"
        n = n[1:]
    n = re.sub(r"^(\d+(?:/\d+)?)\s*(?=[A-Za-z])", r"\1 ", n)  # OCR drops or keeps the space: '13h' is '13 h'
    return re.sub(r"\s+", " ", n)


def name_box(texts, hp_line):
    """nickname = the lowest text right above the HP line that spans its centre (not stray icons at the side)"""
    mid = hp_line[0] + hp_line[2] / 2
    above = [t for t in texts if t[1] < hp_line[1] and hp_line[1] - t[1] < 0.08 and t[0] < mid < t[0] + t[2]
             and not norm(t[4]).startswith("LUCKY POK")]  # lucky ones have a LUCKY POKÉMON line under the name
    return max(above, key=lambda t: t[1]) if above else None


def detail_info(texts):
    hp_line = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    hp = int(re.search(r"/\s*(\d+)\s*HP", hp_line[4]).group(1))
    cpt = next((t for t in texts if re.fullmatch(r"CP\s*\d+", t[4].replace(" ", ""))), None)
    cp = int(re.sub(r"\D", "", cpt[4])) if cpt else None
    box = name_box(texts, hp_line)
    name = clean_name(box[4]) if box else None
    tags = [t[4] for t in texts if hp_line[1] < t[1] < hp_line[1] + 0.06]
    return {"name": name, "cp": cp, "hp": hp, "tags": tags, "texts": [t[4] for t in texts]}


def tiles(texts):
    """Pokémon tiles in the list, in reading order: (name, cp, x, y) with x, y = middle of the tile image"""
    cps = [t for t in texts if re.fullmatch(r"CP\s*\d+", t[4].upper().replace(" ", ""))]
    out = []
    for c in cps:
        # under 0.9: lower down, the round buttons (+, X, A-Z) cover the names and read as 'L+', '2'
        below = [t for t in texts if 0.08 < t[1] - c[1] < 0.13 and abs((t[0] + t[2] / 2) - (c[0] + c[2] / 2)) < 0.1
                 and t[1] < 0.9]
        if below:
            n = below[0]
            out.append((n[4].lstrip("•· ").strip(), int(re.sub(r"\D", "", c[4])),
                        n[0] + n[2] / 2, (c[1] + c[3] + n[1]) / 2))
    return sorted(out, key=lambda t: (round(t[3] / 0.05), t[2]))


def nickname_field(texts):
    """the text box in the Set Nickname dialog (a stand-in box if it's empty)"""
    top = next(t for t in texts if norm(t[4]).startswith("SET NICKNAME"))
    ok = next(t for t in texts if norm(t[4]) == "OK")
    inside = [t for t in texts if top[1] < t[1] < ok[1]]
    if inside:
        return inside[0]
    return (0.2, (top[1] + ok[1]) / 2, 0.4, 0.02, "")


def ticked_tags(path, texts):
    """tag rows in the TAG dialog, and whether each has the green tick on the right"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    out = []
    for x, y, w, h, t in texts:
        n = norm(t)
        if not n or n.startswith(("TAG ", "DONE", "VISIBLE")) or y < 0.2 or y > 0.83:
            continue
        cy = int((y + h / 2) * H)
        green = sum(1 for yy in range(cy - 8, cy + 9) for xx in range(int(0.8 * W), int(0.95 * W))
                    if (lambda r, g, b: g > r + 40 and g > b + 10)(*im.getpixel((xx, yy))))
        out.append((t.lstrip("•· ").strip(), green > 5))
    return out


# ---------- species from name ----------

def species_for(name, texts):
    gm = json.load(open(os.path.join(HERE, "gamemaster.json")))
    words = {w for t in texts for w in norm(t).split()}  # the type line reads as one text: "DARK / NORMAL"
    cands = []
    for p in gm["pokemon"]:
        sid = p["speciesId"]
        if sid.endswith(("_shadow", "_mega", "_mega_x", "_mega_y", "_xs")) or "_primal" in sid:
            continue
        base = p["speciesName"].split(" (")[0]
        if base.lower() == (name or "").lower():
            cands.append(p)
    if (name or "").lower() == "pikachu":  # costumes all share Pikachu's base stats, so they rank the same
        return ["pikachu"]
    if len(cands) > 1:  # regional forms etc: keep those whose types match the type line
        typed = [p for p in cands if all(t.upper() in words or t == "none" for t in p["types"])]
        cands = typed or cands
    if len(cands) > 1:  # Rattata (Normal) vs Alolan (Dark/Normal): both pass above, the one using more shown types wins
        most = max(sum(t.upper() in words for t in p["types"]) for p in cands)
        cands = [p for p in cands if sum(t.upper() in words for t in p["types"]) == most]
    if len(cands) > 1:  # forms with the same stats down the whole family rank the same (Oricorio): any will do
        by_id = {p["speciesId"]: p for p in gm["pokemon"]}
        def stats(sid):
            p = by_id[sid]
            evos = sorted(stats(e) for e in p.get("family", {}).get("evolutions", []) if e in by_id)
            return (tuple(sorted(p["baseStats"].items())), tuple(evos))
        if len({stats(p["speciesId"]) for p in cands}) == 1:
            cands = cands[:1]
    return [p["speciesId"] for p in cands]


# ---------- appraisal bars ----------

def is_bar(px):
    # background is cream/white (max channel >= 240); bars are grey (~225) or coloured
    return max(px) < 240 or max(px) - min(px) > 50


def is_fill(px):
    return max(px) - min(px) > 50


def bars(path, texts):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    x0, x1 = int(0.10 * W), int(0.49 * W)
    ivs, raws = [], []
    for label in ("ATTACK", "DEFENSE", "HP"):
        lab = [t for t in texts if is_label(t[4], label) and t[0] < 0.35]
        if not lab:
            return None, f"no {label} label"
        lx, ly, lw, lh, _ = max(lab, key=lambda t: t[1])  # the appraisal one is lowest
        ys = range(int((ly + lh) * H), int((ly + lh + 0.04) * H))
        counts = {y: sum(is_bar(im.getpixel((x, y))) for x in range(x0, x1)) for y in ys}
        full = []  # first band of rows under the label that looks like a bar
        for y in ys:
            if counts[y] > 0.25 * (x1 - x0):
                full.append(y)
            elif full:
                break
        if not full:
            return None, f"{label}: no bar under the label"
        best = (None, full[len(full) // 2])  # middle row of the bar, away from blurry edges
        row = [im.getpixel((x, best[1])) for x in range(x0, x1)]
        on = [i for i, px in enumerate(row) if is_bar(px)]
        start, end = on[0], on[-1]
        if not 0.25 * W < end - start < 0.4 * W:
            return None, f"{label}: bar width {end - start}px looks wrong"
        filled = [i for i in range(start, end + 1) if is_fill(row[i])]
        raw = 15 * (filled[-1] - start + 1) / (end - start + 1) if filled else 0.0
        r, g, b = row[filled[-1] - 3] if filled else (0, 0, 0)
        if r > 200 and g < 140 and b > 100:  # a maxed stat shows as a red bar
            raw = 15.0
        raws.append(round(raw, 1))
        ivs.append(round(raw))
    return ivs, raws


def check_rows(species, cp, hp, ivs):
    out = sh(sys.executable, os.path.join(HERE, "pvp.py"), "check", species, str(cp), str(hp), "-1",
             "--near", "/".join(map(str, ivs)))
    return out.strip()


# ---------- icons (teal circles at the bottom) ----------

TEAL_TOL = 52 if ANDROID else 24  # the Pixel: (22, 112, 137) through scrcpy, (64, 131, 146) in its own screenshot


def circles(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    y0 = int(0.82 * H)
    mask = {(x, y) for y in range(y0, H) for x in range(W)
            if sum(abs(a - b) for a, b in zip(im.getpixel((x, y)), (32, 122, 141))) < TEAL_TOL}
    seen, out = set(), []
    for p in mask:
        if p in seen:
            continue
        stack, comp = [p], []
        seen.add(p)
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in mask and q not in seen:
                    seen.add(q)
                    stack.append(q)
        xs, ys = [c[0] for c in comp], [c[1] for c in comp]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if 0.06 * W < w < 0.25 * W and 0.7 < w / max(h, 1) < 1.4:
            c = ((min(xs) + max(xs)) / 2 / W, (min(ys) + max(ys)) / 2 / H, w / 2 / W)
            # ring and inner fill of the same button come out as separate pieces: keep the biggest
            same = [o for o in out if abs(o[0] - c[0]) < 0.02 and abs(o[1] - c[1]) < 0.02]
            if same and same[0][2] >= c[2]:
                continue
            out = [o for o in out if o not in same] + [c]
    return sorted(out)


# ---------- tapping ----------

def calib_scale():
    if not os.path.exists(CALIB):
        sys.exit("not calibrated: mouse_move to a spot in a fresh screenshot, then run: ui.py calib <x> <y>")
    return json.load(open(CALIB))["scale"]


def to_shot(fx, fy, bounds):
    x, y, w, h = bounds
    s = calib_scale()
    return round((x + fx * w) / s), round((y + fy * h) / s)


def safe(fx, fy, texts):
    for x, y, w, h, t in texts:
        if any(norm(t).startswith(z) for z in HAZARDS):
            m = HAZARD_MARGIN
            if x - m <= fx <= x + w + m and y - m <= fy <= y + h + m:
                return False
    return True


def fuzz_box(x, y, w, h, texts, frac=0.25):
    """random point in the middle of a box; frac = how far in from each edge"""
    for _ in range(50):
        fx = x + w * random.uniform(frac, 1 - frac)
        fy = y + h * random.uniform(0.3, 0.7)
        if safe(fx, fy, texts):
            return fx, fy
    raise Refused("REFUSED: every candidate spot was near a hazard button")


def fuzz_circle(cx, cy, r, texts, aspect):
    for _ in range(50):
        dx, dy = random.uniform(-0.3, 0.3) * r, random.uniform(-0.3, 0.3) * r * aspect
        if safe(cx + dx, cy + dy, texts):
            return cx + dx, cy + dy
    raise Refused("REFUSED: circle spot near a hazard button")


def search_box(texts):
    """the search bar at the top of the list: 'Search' (Q = the magnifier) or a typed search like '#IVC' / '4&shadow'"""
    # Q = the magnifier. '#Luckydex +' chips don't have it; 'Q (5)' under the POKÉMON tab is the result count
    hits = [t for t in texts if t[1] < 0.3 and re.match(r"(?:[<‹]\s*[Q9]|Q)[\s,.]+\S", t[4]) and not re.match(r"Q\s*\(\d+\)", t[4])]
    if not hits:  # the magnifier glued to the text ('Q4&shadow', '< 9113&!#Nope'): go by where the bar sits
        hits = [t for t in texts if 0.155 < t[1] < 0.2 and t[0] < 0.35 and t[4].strip() not in ("<", "‹", "Q", "9", "< 9", "‹ 9")]
    return hits[0] if len(hits) == 1 else None


def search_panel(texts):
    """the filter panel that opens (with the keyboard) when the search bar is tapped"""
    words = {norm(t[4]) for t in texts}
    cps = sum(bool(re.match(r"CP\s*\d", t[4].upper())) for t in texts)
    return bool(words & {"RECOMMENDED", "SEE MORE"}) and cps < 3


def search_text(box):
    """what's typed in the search bar, as OCR reads it ('' if it just says Search)"""
    t = re.sub(r"^(?:[<‹]\s*[Q9]|Q)[\s,.]+|^[<‹]\s*Q?|^Q(?=\d)", "", box[4]).strip()
    return "" if t.lower() in ("search", "9", "q") else t


def evo_box(texts):
    """the SHOW EVOLUTIONARY LINE tick circle under the search bar: (x, y) centre, or None"""
    t = [t for t in texts if t[1] < 0.4 and norm(t[4]) == "SHOW EVOLUTIONARY LINE"]
    return (t[0][0] - 0.052, t[0][1] + t[0][3] / 2) if len(t) == 1 else None


def evo_ticked(path, texts):
    """True if SHOW EVOLUTIONARY LINE is ticked (a tick inside the ring), None if it isn't on screen"""
    c = evo_box(texts)
    if not c:
        return None
    im = Image.open(path).convert("RGB")
    W, H = im.size
    cx, cy, r = int(c[0] * W), int(c[1] * H), int(0.014 * W)
    ink = sum(1 for x in range(cx - r, cx + r + 1) for y in range(cy - r, cy + r + 1)
              if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and (lambda R, G, B: R < 150 and G > 100)(*im.getpixel((x, y))))
    return ink > 6


def star_spot(texts):
    """favorite star: top right of the detail screen, level with the CP (the camera button sits below it)"""
    cpt = [t for t in texts if re.fullmatch(r"\S?P\s*\d{2,}", t[4].upper().replace(" ", "")) and t[1] < 0.2]  # the C can misread (S, G, &)
    if not cpt:  # 'CP' and the number read as two texts ('CP:', '957'): the number is level with the star
        cpt = [t for t in texts if re.fullmatch(r"\d{2,5}", t[4].strip()) and 0.06 < t[1] < 0.2 and t[0] < 0.75]
    if len(cpt) != 1:
        return ANDROID_STAR if ANDROID and unscrolled(texts) else None
    return 0.895, cpt[0][1] + cpt[0][3] / 2 + 0.004


ANDROID_STAR = (0.901, 0.104)  # the Pixel's star in the capture layout, for when a lucky's sparkles hide the CP


def unscrolled(texts):
    """the detail screen sits at the top: its HP line is where it always is"""
    hp = [t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4])]
    return len(hp) == 1 and 0.45 < hp[0][1] < 0.56


def star_filled(path, texts):
    """True if the star is filled in (favorite), False if just the outline, None if it can't tell"""
    spot = star_spot(texts)
    if not spot:
        return None
    im = Image.open(path).convert("RGB")
    W, H = im.size
    cx, cy = int(spot[0] * W), int(spot[1] * H)
    r = int(0.018 * W)
    px = [im.getpixel((x, y)) for x in range(cx - r, cx + r + 1) for y in range(cy - r, cy + r + 1)]
    gold = sum(1 for p, g, b in px if p > 200 and g > 140 and b < 90 and p - b > 120)
    if spot == ANDROID_STAR and gold <= len(px) * 0.15 and sum(1 for p in px if min(p) > 235) < len(px) * 0.03:
        return None  # no CP to go by, and neither a gold star nor a white outline where the star should be
    return gold > len(px) * 0.15


# confirm buttons only count on their own dialog, so a stray popup's OK is never tapped
CONFIRM_SCREENS = {"OK": ("rename",), "CANCEL": ("rename", "tags"), "DONE": ("tags",),
                   "PVPC": ("tags", "tag-tab"), "IVC": ("tags", "tag-tab"), "NOPE": ("tags",), "TAG": ("menu",), "TAGS": ("list",), "APPRAISE": ("menu",), "POKMON": ("tag-tab",)}


def locate(T, path, texts, screen, aspect):
    """-> (centre x, centre y, fuzz()) in window fractions, or exits with REFUSED"""
    if T in ("MENU", "CLOSE"):
        cs = circles(path)
        if T == "MENU" and screen == "detail":
            c = [c for c in cs if c[0] > 0.7]
        elif T == "CLOSE" and screen == "detail":
            c = [c for c in cs if 0.35 < c[0] < 0.65]
            menu = [m for m in cs if m[0] > 0.7]
            if not c and len(menu) == 1:  # the X is see-through and can vanish into the background:
                c = [(0.5, menu[0][1], menu[0][2] * 0.8)]  # it sits bottom centre, level with the menu button
        elif T == "CLOSE" and screen == "menu":
            c = [c for c in cs if c[0] > 0.7]
        else:
            raise Refused(f"REFUSED: no {T.lower()} button on screen '{screen}'")
        if len(c) != 1:
            raise Refused(f"REFUSED: found {len(c)} {T.lower()} buttons on '{screen}'")
        return c[0][0], c[0][1], lambda: fuzz_circle(*c[0], texts, aspect)
    if T == "DIALOG":
        if screen not in ("appraisal", "appraise-intro"):
            raise Refused(f"REFUSED: no appraisal dialog on screen '{screen}'")
        top = min(t[1] for t in texts if t[1] > 0.88)
        return 0.5, top, lambda: fuzz_box(0.2, top, 0.6, 0.03, texts, frac=0)
    if T.startswith("TILE "):
        ts = tiles(texts) if screen == "list" else []
        i = int(T.split()[1]) - 1
        if not 0 <= i < len(ts):
            raise Refused(f"REFUSED: no tile {i + 1} on screen '{screen}' ({len(ts)} tiles)")
        _, _, cx, cy = ts[i]
        return cx, cy, lambda: (cx + random.uniform(-0.04, 0.04), cy + random.uniform(-0.015, 0.015))
    if T == "FIELD":
        if screen != "rename":
            raise Refused(f"REFUSED: no nickname box on screen '{screen}'")
        box = nickname_field(texts)[:4]
        return box[0] + box[2] / 2, box[1], lambda: fuzz_box(*box, texts)
    if T == "PENCIL":
        if screen != "detail":
            raise Refused(f"REFUSED: not on detail screen ('{screen}')")
        hp_line = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
        name = name_box(texts, hp_line)
        if not name:
            raise Refused("REFUSED: can't find the name above HP")
        if clean_name(name[4]) != name[4].strip():  # pencil read as '/': it's the right end of the box
            cx = name[0] + name[2] - 0.015
        else:
            cx = name[0] + name[2] + 0.037
        cy = name[1] + name[3] / 2
        return cx, cy, lambda: (cx + random.uniform(-0.008, 0.008), cy + random.uniform(-0.004, 0.004))
    if T == "SEARCH":
        box = search_box(texts) if screen == "list" else None
        if not box:
            raise Refused(f"REFUSED: no search bar on screen '{screen}'")
        return box[0] + box[2] / 2, box[1], lambda: fuzz_box(*box[:4], texts)
    if T == "EVOLINE":
        c = evo_box(texts) if screen == "list" else None
        if not c:
            raise Refused(f"REFUSED: no SHOW EVOLUTIONARY LINE tick on screen '{screen}'")
        cx, cy = c
        return cx, cy, lambda: (cx + random.uniform(-0.006, 0.006), cy + random.uniform(-0.003, 0.003))
    if T == "STAR":
        hp = [t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4])]
        spot = star_spot(texts) if screen == "detail" and hp and hp[0][1] > 0.3 else None
        if not spot:
            raise Refused(f"REFUSED: no favorite star on screen '{screen}' (or detail scrolled)")
        cx, cy = spot
        return cx, cy, lambda: (cx + random.uniform(-0.01, 0.01), cy + random.uniform(-0.005, 0.005))
    if T not in CONFIRM_SCREENS:
        raise Refused(f"REFUSED: {T} is not an allowed target")
    if screen not in CONFIRM_SCREENS[T]:
        raise Refused(f"REFUSED: {T} only allowed on {CONFIRM_SCREENS[T]}, screen is '{screen}'")
    hits = [t for t in texts if norm(t[4]) == T or (norm(t[4]).startswith(T + " ") and len(norm(t[4])) <= len(T) + 2)]
    if ANDROID and screen == "rename" and T == "OK" and len(hits) == 2:
        # Android's keyboard brings its own text bar with an OK: that one keeps the typed text and hides the
        # keyboard (Back would throw the text away). The next OK tap then hits the dialog's own button.
        hits = [max(hits, key=lambda t: t[1])]
    if len(hits) != 1:
        raise Refused(f"REFUSED: found {len(hits)} matches for {T} on '{screen}': {[h[4] for h in hits]}")
    box = hits[0][:4]
    return box[0] + box[2] / 2, box[1], lambda: fuzz_box(*box, texts)


def plan(target):
    """-> (fx, fy, bounds, screen): a fuzzed spot in window fractions. Raises Refused / Moving."""
    T = target.upper()
    if any(T.startswith(z) for z in HAZARDS):
        raise Refused(f"REFUSED: {target} is on the never-tap list")
    spots = []
    prev = _seen if _seen and time.time() - _seen[0] < 1.5 else None  # a look from just now counts as the first
    if prev and _older and 0.3 < prev[0] - _older[0] < 1.5:  # and the one before it as well, if they agree
        try:
            pair = [(o[4], locate(T, o[1], o[2], o[4], o[3][2] / o[3][3])) for o in (_older, prev)]
        except Refused:  # the older one caught the screen mid-change: take a new look as usual
            pair = None
        if pair:
            (s1, (x1, y1, _)), (s2, (x2, y2, fuzz)) = pair
            if s1 == s2 and abs(x1 - x2) <= 0.01 and abs(y1 - y2) <= 0.01 and _older[3] == prev[3]:
                fx, fy = fuzz()
                return fx, fy, prev[3], s2
    for i in range(2):  # two looks 0.4s apart: refuse if the screen is still animating
        if not i and prev:
            _, path, texts, bounds, screen = prev
            spots.append((screen, locate(T, path, texts, screen, bounds[2] / bounds[3])))
            continue
        if i:
            time.sleep(max(0.0, 0.4 - (time.time() - prev[0])) if prev else 0.4)
        path, bounds = capture()
        texts = ocr(path)
        screen = classify(texts)
        spots.append((screen, locate(T, path, texts, screen, bounds[2] / bounds[3])))
    remember(path, texts, bounds)
    (s1, (x1, y1, _)), (s2, (x2, y2, fuzz)) = spots
    if s1 != s2 or abs(x1 - x2) > 0.01 or abs(y1 - y2) > 0.01:
        raise Moving("REFUSED: screen still moving, wait and try again")
    fx, fy = fuzz()
    return fx, fy, bounds, s2


def cmd_tap(target):
    fx, fy, bounds, _ = plan(target)
    print(*to_shot(fx, fy, bounds))


def cmd_press(target):
    fx, fy, bounds, _ = plan(target)
    x, y, w, h = bounds
    sh(HELPER, "click", f"{x + fx * w:.1f}", f"{y + fy * h:.1f}", str(random.randint(50, 100)))
    print(f"pressed {target}")


def cmd_read(path=None):
    bounds = None
    if not path:
        path, bounds = capture()
    texts = ocr(path)
    screen = classify(texts)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if screen == "detail":
        info = detail_info(texts)
        sp = species_for(info["name"], info["texts"])
        state = {k: info[k] for k in ("name", "cp", "hp")}
        state["species"] = sp
        json.dump(state, open(STATE, "w"))
        print(f"detail  name={info['name']}  CP={info['cp']}  HP={info['hp']}  tags={info['tags']}  species={sp or '?'}")
    elif screen == "appraisal":
        ivs, raws = bars(path, texts)
        if ivs is None:
            print(f"appraisal  BARS UNREADABLE: {raws}")
            return
        print(f"appraisal  bars={'/'.join(map(str, ivs))}  raw={raws}  (for {state.get('name')} CP{state.get('cp')} HP{state.get('hp')})")
        sp = state.get("species") or []
        if len(sp) == 1 and state.get("cp"):
            print(check_rows(sp[0], state["cp"], state["hp"], ivs))
        else:
            print(f"species unclear {sp}: run pvp.py check yourself")
    elif screen == "list":
        print("list  " + " | ".join(f"{i}:{n} CP{c}" for i, (n, c, _, _) in enumerate(tiles(texts), 1)))
    elif screen == "rename":
        print(f"rename  field={nickname_field(texts)[4]!r}")
    elif screen == "tags":
        print("tags  " + "  ".join(f"[{'x' if on else ' '}] {n}" for n, on in ticked_tags(path, texts)))
    elif screen == "unknown":
        print("unknown  " + " | ".join(t[4] for t in texts)[:400])
    else:
        print(screen)


def cmd_calib(sx, sy):
    ensure_helper()
    mx, my = map(float, sh(HELPER, "mouse").split())
    scale = (mx / sx + my / sy) / 2
    json.dump({"scale": scale}, open(CALIB, "w"))
    print(f"scale={scale:.4f}")


def main(a):
    if a[0] == "read":
        cmd_read(a[1] if len(a) > 1 else None)
    elif a[0] == "tap":
        cmd_tap(" ".join(a[1:]))
    elif a[0] == "press":
        if ANDROID:
            android.ready()
        cmd_press(" ".join(a[1:]))
    elif a[0] == "calib":
        cmd_calib(float(a[1]), float(a[2]))
    elif a[0] == "look":
        print(capture()[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    try:
        main(a)
    except Refused as e:
        sys.exit(str(e))
    except Exception as e:
        if ANDROID and isinstance(e, android.NotReady):
            sys.exit(f"NOT READY: {e}")
        raise
