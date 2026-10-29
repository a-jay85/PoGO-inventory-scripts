#!/usr/bin/env python3
"""Cleanup: purify every shadow Pokémon tagged Nope, then transfer them all in one go.

  caffeinate -dimsu python3 shadows.py [--limit N]     purify (at most N), then bulk-transfer what this run purified
  caffeinate -dimsu python3 shadows.py transfer <run dir>   only the bulk transfer, for a run that stopped before it
  POGO_PHONE=android caffeinate -dimsu python3 shadows.py ...   (Android phone over USB)

Start with Pokémon GO on the Pokémon screen. Searches #Nope&shadow&!shiny&!costume&!xxl&!xxs, opens the first one and
swipes through them. Each one is purified only if: its only tag is Nope, no star, no XXL/XXS in the name, not
legendary or mythical (by its candy), and there's enough candy and Stardust. Anything else is passed over.
Then it searches #Nope&purified, taps SELECT ALL, and transfers only if the count is exactly what this run purified.
Before starting it checks that #Nope&purified is empty, so it can never transfer an older purified one.
Log, timings and purified.json go in runs/<time>/.
"""
import json, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import run as base
from run import Stop, log, keep_capture, go, look, wait_for, front, save, load, candy
import search, session

SHADOWS = "#Nope&shadow&!shiny&!costume&!xxl&!xxs"  # (sizes.py renames those and tags them IVC)
PURIFIED = "#Nope&purified"
GM = json.load(open(os.path.join(HERE, "..", "shared", "gamemaster.json")))
SPECIAL = {p["speciesName"].split(" (")[0].upper() for p in GM["pokemon"]
           if {"legendary", "mythical", "ultrabeast"} & set(p.get("tags", []))}


class Pass(Exception):
    """leave this one alone"""


def not_high_iv():
    """on the detail screen: raise Pass if it's 98%+ (a shadow: once purified), or its IV can't be read.
    A wrong name can land a 98% one in Nope: those never get purified, transferred or traded away."""
    try:
        keep, _, _, what = base.high_iv()
    except base.Skip as e:
        raise Pass(f"can't read its IV: {e}")
    if keep:
        raise Pass(f"appraised {what}: 98%+ (or purifies to it), never transferred or traded")


class Again(Exception):
    """the screen was still settling: read it again"""


# ---------- tapping ----------

def press(t, bounds, hold=None):
    """one tap in the middle of an OCR box (never go(): a 2nd tap after PURIFY lands on POWER UP).
    hold: ms, a long press"""
    if hold is None:
        base.tap_box(t, bounds, spread=0.15)
    else:
        base.tap_box(t, bounds, spread=0.15, ms=hold)


def exact(texts, word):
    """boxes whose text is exactly this word, case and all ('TRANSFER' button, not the 'transfer.' line)"""
    return [t for t in texts if t[4].strip() == word]


def swipe_next(bounds):
    """swipe left across the Pokémon's picture: the next one in the list opens"""
    front()
    y = 0.33 + random.uniform(-0.02, 0.02)
    if ui.ANDROID:  # a quick plain swipe: android.drag's pause before lifting kills the fling
        W, H = ui.android.size()
        x1, x2, y2 = W * random.uniform(0.85, 0.89), W * random.uniform(0.08, 0.12), y + random.uniform(-0.01, 0.01)
        ui.android.shell(f"input swipe {int(x1)} {int(H * y)} {int(x2)} {int(H * y2)} {random.randint(130, 175)}")
    else:
        x1, y1 = base.to_points(0.85, y, bounds)
        x2, y2 = base.to_points(0.12, y, bounds)
        ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", "180")
    base.ui._seen = base.ui._older = None


def next_one(bounds, moved, poll=0.12):
    """swipe on to the next Pokémon: True once a detail page shows one moved(texts) says is another. A swipe that does
    nothing twice = the end of the list. bounds None: read them before each swipe"""
    for attempt in range(2):
        swipe_next(bounds or look()[3])
        for _ in range(10):
            time.sleep(poll)
            screen, texts, _, _ = look()
            if screen == "detail" and moved(texts):
                return True
    return False


def reopen_top():
    """one that was changed drops out of the search, and the swipe stops working: back to the list, open the top one
    again. False when the list is empty now"""
    texts = go("close", "list")[1]
    if not ui.tiles(texts):
        time.sleep(0.4)
        if not settled_tiles():
            return False
    go("tile 1", "detail")
    return True


def select_all(button, n, poll=0.15):
    """long press the first tile (multi-select), then SELECT ALL, and wait for '<button> (n)'.
    -> (that button or None, the count it shows, texts, bounds): the caller backs out when the count is off"""
    _, texts, _, bounds = look()
    first = ui.tiles(texts)[0]
    press((first[2] - 0.03, first[3] - 0.01, 0.06, 0.02, ""), bounds, hold=900)  # long press: multi-select
    pat = rf"{button} \((\d+)\)"
    for _ in range(20):
        time.sleep(poll)
        _, texts, _, bounds = look()
        sel = exact(texts, "SELECT ALL")
        if sel and any(re.fullmatch(pat, t[4].strip()) for t in texts):
            break
    else:
        keep_capture("multiselect")
        raise Stop("long press didn't start multi-select")
    press(sel[0], bounds)
    btn = got = None
    for _ in range(20):
        time.sleep(poll)
        _, texts, _, bounds = look()
        btn = next((t for t in texts if re.fullmatch(pat, t[4].strip())), None)
        got = int(re.search(r"\d+", btn[4]).group()) if btn else None
        if got == n:
            break
    return btn, got, texts, bounds


# ---------- search ----------

def search_exact(q):
    """type q and make sure the bar holds exactly q. One lost '!' would turn '!shiny' into 'shiny'."""
    for attempt in range(3):
        path, texts, bounds = search.start_search(q)
        sharp = ui.ocr(ui.android.sharp()) if ui.ANDROID else texts
        box = ui.search_box(sharp)
        got = re.sub(r"\s", "", ui.search_text(box)) if box else ""
        got = re.sub(r"^[<‹]?[Q9]?(?=#)", "", got)  # the magnifier glued on
        if ":" not in q:  # the iPhone's small picture reads '!' as ':' (and nothing types a ':' we didn't ask for)
            got = got.replace(":", "!")
        # the Pixel's bar shows only the first ~30 characters of a long search: the rest is cut off, not lost
        clipped = ui.ANDROID and len(got) >= 28 and q.startswith(got)
        if got == q or clipped:
            return path, texts, bounds
        log(f"search bar reads {got!r}, wanted exactly {q!r}: typing it again")
    keep_capture("search")
    raise Stop(f"couldn't get exactly {q!r} in the search bar")


def result_tiles(q):
    """search, wait for the list to settle. -> tiles on the first screen ([] if none)"""
    search_exact(q)
    return settled_tiles()


def settled_tiles():
    last = None
    for _ in range(12):
        time.sleep(0.25)
        screen, texts, path, bounds = look()
        ts = [(ui.tile_name(n), c) for n, c, _, _ in ui.tiles(texts)] if screen == "list" else None
        if ts is not None and ts == last:
            return ts
        last = ts
    return last or []


# ---------- one Pokémon ----------

def num(s):
    d = re.sub(r"[^\d]", "", s)
    return int(d) if d else None


def costs(texts):
    """-> (stardust owned, candy owned, purify dust cost, purify candy cost) off the detail page"""
    pur = exact(texts, "PURIFY")[0]
    row = sorted((t for t in texts if abs(t[1] - pur[1]) < 0.02 and t[0] > pur[0] + pur[2]), key=lambda t: t[0])
    if len(row) < 2:
        raise Pass(f"can't read the purify cost row: {[t[4] for t in row]}")
    have_dust, have_candy = owned(texts)
    dust, cnd = num(row[0][4]), num(row[-1][4])
    if dust and cnd and dust != cnd * 1000 and str(dust).endswith(str(cnd * 1000)):
        dust = cnd * 1000  # the Stardust icon read as a 1 ('15,000' for 5,000): purify costs 1000 dust per candy
    if None in (dust, cnd) or not (1000 <= dust <= 20000 and dust % 1000 == 0) or not 1 <= cnd <= 20:
        raise Pass(f"purify cost reads odd: dust {row[0][4]!r} candy {row[-1][4]!r}")
    return have_dust, have_candy, dust, cnd


def owned(texts):
    """-> (stardust owned, candy owned) off the detail page"""
    dust_l = [t for t in texts if ui.norm(t[4]) == "STARDUST"]
    if len(dust_l) != 1:
        raise Pass("can't find the STARDUST label")
    x, y, w, _ = dust_l[0][:4]
    up = [t for t in texts if 0 < y - t[1] < 0.045 and t[0] < x + w and x < t[0] + t[2]]
    if not up:
        raise Pass("can't read the Stardust owned")
    dust_n = max(up, key=lambda t: t[1])
    # candy owned: the number above the 'X CANDY' label. The label can wrap ('PHANTUMP' / 'CANDY'), and a family
    # that can mega evolve puts candy top right, with Candy XL and mega energy in a second row
    xl = lambda l: any(ui.norm(u[4]) == "XL" and 0 < u[1] - l[1] < 0.025 and u[0] < l[0] + l[2] and l[0] < u[0] + u[2]
                       for u in texts)  # 'SNORLAX CANDY' / 'XL' wrapped: that's Candy XL
    labs = [t for t in texts if re.search(r"(^|\s)CANDY$", ui.norm(t[4])) and t[1] < 0.8 and not xl(t)]
    labs = [max((u for u in texts if 0 < l[1] - u[1] < 0.025 and u[0] < l[0] + l[2] and l[0] < u[0] + u[2]),
                key=lambda u: u[1], default=l) if ui.norm(l[4]) == "CANDY" else l for l in labs]
    labs = sorted(set(labs), key=lambda t: (round(t[1], 2), t[0]))[:1]  # the candy row is above the XL / mega energy row
    up = [t for l in labs for t in texts if 0 < l[1] - t[1] < 0.045 and t[0] < l[0] + l[2] and l[0] < t[0] + t[2]
          and re.fullmatch(r"[\d,.]+", t[4].strip())]
    if len(up) != 1:
        raise Pass(f"can't read the candy owned: {[t[4] for t in up]}")
    have_dust, have_candy = num(dust_n[4]), num(up[0][4])
    if None in (have_dust, have_candy):
        raise Pass(f"can't read the Stardust or candy owned: {dust_n[4]!r} {up[0][4]!r}")
    return have_dust, have_candy


def check(info, texts, path):
    """raise Pass if this one should be left alone"""
    if not exact(texts, "PURIFY"):
        raise Pass("not a shadow (no PURIFY)")
    tags = [ui.norm(t) for t in info["tags"]]
    if tags != ["NOPE"]:
        raise Pass(f"tags {info['tags']}: not just Nope")
    try:
        sized = re.search(r"xx[ls]", info["name"] or "", re.I) or base.extras(texts)[2]
    except base.Skip as e:  # both badges read
        raise Pass(str(e))
    if sized:
        raise Pass("XXL/XXS: sizes.py's")
    star = ui.star_filled(path, texts)
    if star is None and ui.ANDROID:
        sp = ui.android.sharp()
        star = ui.star_filled(sp, ui.ocr(sp))
    if star is not False:
        raise Pass("favorite" if star else "can't see the star")
    c = candy(texts)
    if not c:
        raise Pass("can't read the candy name")
    if c in SPECIAL:
        raise Pass(f"{c.title()}: legendary/mythical")
    for attempt in range(3):  # a label can misread for a moment: look again, then off the phone's own screenshot
        try:
            have_dust, have_candy, dust, cnd = costs(texts)
            break
        except Pass:
            if attempt == 2:
                raise
            texts = ui.ocr(ui.android.sharp()) if ui.ANDROID and attempt else look()[1]
    if have_candy < cnd or have_dust < dust:
        raise Pass(f"not enough: needs {cnd} candy + {dust} dust, has {have_candy} + {have_dust}")
    not_high_iv()


def purify(info):
    """PURIFY once, YES once, wait for the animation to finish. -> the new CP"""
    t0 = time.time()
    _, texts, _, bounds = look()
    now = ui.detail_info(texts) if ui.classify(texts) == "detail" else {}
    pur = exact(texts, "PURIFY")
    flat = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    if not info["cp"] or (flat(now.get("name")), now.get("cp")) != (flat(info["name"]), info["cp"]) or len(pur) != 1:
        raise Again(f"{info['name']} CP{info['cp']} then {now.get('name')} CP{now.get('cp')}")
    press(pur[0], bounds)
    for _ in range(25):  # the YES/NO dialog
        time.sleep(0.12)
        _, texts, _, bounds = look()
        ask = " ".join(t[4] for t in texts if "purify" in t[4].lower() or t[4].strip().endswith("?"))
        yes = exact(texts, "YES")
        if "want to purify" in ask and yes:
            break
    else:
        keep_capture("nopurifydialog")
        raise Stop("no purify YES/NO after tapping PURIFY")
    t1 = time.time()
    if flat(info["name"]) not in flat(ask):
        no = exact(texts, "NO")
        if len(no) == 1:
            press(no[0], bounds)
        raise Stop(f"the purify dialog names someone else: {ask!r} (wanted {info['name']})")
    press(yes[0], bounds)
    end = time.time() + 40
    while time.time() < end:  # done = no PURIFY, POWER UP back, CP changed (the first frame after YES is stale)
        time.sleep(0.15)
        try:
            screen, texts, _, _ = look()
        except ui.Refused:
            continue
        if screen == "detail" and not exact(texts, "PURIFY") and any(ui.norm(t[4]) == "POWER UP" for t in texts):
            cp = ui.detail_info(texts)["cp"]
            if cp and cp != info["cp"]:
                log(f"  timing: to dialog {t1 - t0:.1f}s, animation {time.time() - t1:.1f}s")
                return cp
    keep_capture("purify")
    raise Stop("purify didn't finish in 40s")


# ---------- the runs ----------

def purify_all(limit):
    front()
    done = load("purified.json", [])
    if result_tiles(PURIFIED):
        keep_capture("purified")
        raise Stop(f"{PURIFIED} isn't empty: older purified Nope ones would get transferred too. Sort those first.")
    if not result_tiles(SHADOWS):
        log("no shadows to purify")
        return done
    go("tile 1", "detail")
    seen, passed, t_start, agains = set(), {}, time.time(), 0
    while True:
        t0 = time.time()
        _, texts, path, _ = wait_for("detail")  # one look: purify() looks again before tapping
        info = ui.detail_info(texts)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:
            log("swiped back onto one already seen: end of the list")
            break
        seen.add(me)
        try:
            if me in passed:
                raise Pass(passed[me])
            check(info, texts, path)
        except Pass as e:
            if me not in passed:
                log(f"pass {info['name']} CP{info['cp']}: {e}")
            passed[me] = str(e)
        else:
            if len(done) >= limit:
                log(f"--limit {limit} reached")
                break
            try:
                cp = purify(info)
            except Again as e:
                agains += 1
                if agains > 5:
                    raise Stop(f"the screen won't hold still: {e}")
                log(f"  read again: {e}")
                seen.discard(me)
                continue
            agains = 0
            done.append({"name": info["name"], "cp_before": info["cp"], "cp": cp, "transferred": False})
            save("purified.json", done)
            log(f"purified {info['name']} CP{info['cp']} -> CP{cp}  ({time.time() - t0:.1f}s, #{len(done)})")
            t1 = time.time()
            if not reopen_top():
                break
            seen = set()
            log(f"  timing: reopen {time.time() - t1:.1f}s")
            continue
        t1 = time.time()
        if not next_one(None, lambda t: (lambda n: (n["name"], n["cp"], n["hp"]))(ui.detail_info(t)) != me):
            break
        log(f"  timing: swipe {time.time() - t1:.1f}s")
    log(f"purified {len(done)}, passed over {len(passed)}, {time.time() - t_start:.0f}s")
    if look()[0] != "list":  # the last purify already went back to an empty list
        go("close", "list")
    return done


def transfer_all():
    done = load("purified.json", [])
    want = [d for d in done if not d["transferred"]]
    if not want:
        log("nothing to transfer")
        return
    n = len(want)
    ts = result_tiles(PURIFIED)
    if not ts:
        raise Stop(f"{PURIFIED} shows nothing, but this run purified {n}")
    btn, got, texts, bounds = select_all("TRANSFER", n)
    if got != n:
        keep_capture("count")
        search.leave_multiselect(texts, bounds) or press((0.08, 0.08, 0.04, 0.025, ""), bounds)
        raise Stop(f"SELECT ALL picked {got}, but this run purified {n}: nothing transferred")
    press(btn, bounds)
    for _ in range(25):
        time.sleep(0.12)
        _, texts, _, bounds = look()
        line = " ".join(t[4] for t in texts)
        m = re.search(r"want to transfer (\d+)", line)
        ok = [t for t in exact(texts, "TRANSFER") if t[1] > 0.45]
        if m and len(ok) == 1:
            break
    else:
        keep_capture("transferdialog")
        raise Stop("no transfer dialog")
    if int(m.group(1)) != n or "Pokémon to the professor" not in line.replace("Pokemon", "Pokémon"):
        cancel = exact(texts, "CANCEL")
        if len(cancel) == 1:
            press(cancel[0], bounds)
        raise Stop(f"the dialog says {line!r}, wanted {n}: cancelled")
    t0 = time.time()
    press(ok[0], bounds)
    for _ in range(60):
        time.sleep(0.2)
        screen, texts, _, _ = look()
        if screen == "list" and not ui.tiles(texts) and not exact(texts, "TRANSFER"):
            break
    else:
        keep_capture("aftertransfer")
        raise Stop("the list didn't empty after the transfer: check by hand")
    for d in want:
        d["transferred"] = True
    save("purified.json", done)
    log(f"transferred {n} ({time.time() - t0:.1f}s)")


def script(a):
    base.start()
    if a[:1] != ["transfer"]:
        purify_all(session.limit(a))
    transfer_all()


if __name__ == "__main__":
    a = sys.argv[1:]
    runs = os.path.join(HERE, "runs")
    if a[:1] == ["transfer"] and len(a) > 1:
        base.new_run_dir(runs, os.path.abspath(a[1]))
    elif a and a[0] != "--limit":
        sys.exit(__doc__)
    else:
        base.new_run_dir(runs)
    session.main(script, a)
