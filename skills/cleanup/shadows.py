#!/usr/bin/env python3
"""Cleanup: purify every shadow Pokémon tagged Nope, then transfer them all in one go.

  caffeinate -dimsu python3 shadows.py [--limit N]     purify (at most N), then bulk-transfer what this run purified
  caffeinate -dimsu python3 shadows.py transfer <run dir>   only the bulk transfer, for a run that stopped before it
  POGO_PHONE=android caffeinate -dimsu python3 shadows.py ...   (Android phone over USB)

Start with Pokémon GO on the Pokémon screen. Searches #Nope&shadow&!shiny&!costume, opens the first one and
swipes through them. Each one is purified only if: its only tag is Nope, no star, no XXL/XXS in the name, not
legendary or mythical (by its candy), and there's enough candy and Stardust. Anything else is passed over.
Then it searches #Nope&purified, taps SELECT ALL, and transfers only if the count is exactly what this run purified.
Before starting it checks that #Nope&purified is empty, so it can never transfer an older purified one.
Log, timings and purified.json go in runs/<time>/.
"""
import json, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture, go, look, wait_for, front, save, load, candy
import search

SHADOWS = "#Nope&shadow&!shiny&!costume"
PURIFIED = "#Nope&purified"
GM = json.load(open(os.path.join(HERE, "..", "pvpc", "gamemaster.json")))
SPECIAL = {p["speciesName"].split(" (")[0].upper() for p in GM["pokemon"]
           if {"legendary", "mythical", "ultrabeast"} & set(p.get("tags", []))}


class Pass(Exception):
    """leave this one alone"""


class Again(Exception):
    """the screen was still settling: read it again"""


# ---------- tapping ----------

def press(t, bounds, hold=None):
    """one tap in the middle of an OCR box (never go(): a 2nd tap after PURIFY lands on POWER UP)"""
    fx = t[0] + t[2] * random.uniform(0.35, 0.65)
    fy = t[1] + t[3] * random.uniform(0.35, 0.65)
    if hold is None:
        search.click(fx, fy, bounds)
        return
    front()
    x, y = base.to_points(fx, fy, bounds)
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(hold))
    base.last_tap = time.time()


def exact(texts, word):
    """boxes whose text is exactly this word, case and all ('TRANSFER' button, not the 'transfer.' line)"""
    return [t for t in texts if t[4].strip() == word]


def swipe_next(bounds):
    """swipe left across the Pokémon's picture: the next one in the list opens"""
    front()
    y = 0.33 + random.uniform(-0.02, 0.02)
    if ui.ANDROID:  # a quick plain swipe: android.drag's pause before lifting kills the fling
        W, H = ui.android.size()
        ui.android.shell(f"input swipe {int(W * 0.87)} {int(H * y)} {int(W * 0.1)} {int(H * y)} 150")
    else:
        x1, y1 = base.to_points(0.85, y, bounds)
        x2, y2 = base.to_points(0.12, y, bounds)
        ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", "180")
    base.ui._seen = base.ui._older = None


# ---------- search ----------

def search_exact(q):
    """type q and make sure the bar holds exactly q. One lost '!' would turn '!shiny' into 'shiny'."""
    for attempt in range(3):
        path, texts, bounds = search.start_search(q)
        sharp = ui.ocr(ui.android.sharp()) if ui.ANDROID else texts
        box = ui.search_box(sharp)
        got = re.sub(r"\s", "", ui.search_text(box)) if box else ""
        got = re.sub(r"^[<‹]?[Q9]?(?=#)", "", got)  # the magnifier glued on
        if got == q:
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
    dust_l = [t for t in texts if ui.norm(t[4]) == "STARDUST"]
    if len(row) < 2 or len(dust_l) != 1:
        raise Pass(f"can't read the purify cost row: {[t[4] for t in row]}")
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
    mid = up
    have_dust, have_candy = num(dust_n[4]), num(mid[0][4])
    dust, cnd = num(row[0][4]), num(row[-1][4])
    if dust and cnd and dust != cnd * 1000 and str(dust).endswith(str(cnd * 1000)):
        dust = cnd * 1000  # the Stardust icon read as a 1 ('15,000' for 5,000): purify costs 1000 dust per candy
    if None in (have_dust, have_candy, dust, cnd) or not (1000 <= dust <= 20000 and dust % 1000 == 0) \
            or not 1 <= cnd <= 20:
        raise Pass(f"purify cost reads odd: dust {row[0][4]!r} candy {row[-1][4]!r}")
    return have_dust, have_candy, dust, cnd


def check(info, texts, path):
    """raise Pass if this one should be left alone"""
    if not exact(texts, "PURIFY"):
        raise Pass("not a shadow (no PURIFY)")
    tags = [ui.norm(t) for t in info["tags"]]
    if tags != ["NOPE"]:
        raise Pass(f"tags {info['tags']}: not just Nope")
    if re.search(r"xx[ls]", info["name"] or "", re.I):
        raise Pass("XXL/XXS in the name")
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
            # it no longer fits the search, and the swipe stops working: back to the list, open the top one again
            t1 = time.time()
            texts = go("close", "list")[1]
            if not ui.tiles(texts):
                time.sleep(0.4)
                if not settled_tiles():
                    break
            go("tile 1", "detail")
            seen = set()
            log(f"  timing: reopen {time.time() - t1:.1f}s")
            continue
        moved = False
        for attempt in range(2):  # next one; a swipe that does nothing twice = end of the list
            t1 = time.time()
            _, _, _, bounds = look()
            swipe_next(bounds)
            for _ in range(10):
                time.sleep(0.12)
                screen, texts, _, _ = look()
                if screen == "detail":
                    n = ui.detail_info(texts)
                    if (n["name"], n["cp"], n["hp"]) != me:
                        moved = True
                        break
            if moved:
                log(f"  timing: swipe {time.time() - t1:.1f}s")
                break
        if not moved:
            break
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
    _, texts, path, bounds = look()
    first = ui.tiles(texts)[0]
    press((first[2] - 0.03, first[3] - 0.01, 0.06, 0.02, ""), bounds, hold=900)  # long press: multi-select
    for _ in range(20):
        time.sleep(0.15)
        _, texts, _, bounds = look()
        sel = exact(texts, "SELECT ALL")
        if sel and any(re.fullmatch(r"TRANSFER \(\d+\)", t[4].strip()) for t in texts):
            break
    else:
        keep_capture("multiselect")
        raise Stop("long press didn't start multi-select")
    press(sel[0], bounds)
    got = None
    for _ in range(20):
        time.sleep(0.15)
        _, texts, _, bounds = look()
        btn = [t for t in texts if re.fullmatch(r"TRANSFER \((\d+)\)", t[4].strip())]
        got = int(re.search(r"\d+", btn[0][4]).group()) if btn else None
        if got == n:
            break
    if got != n:
        keep_capture("count")
        search.leave_multiselect(texts, bounds) or press((0.08, 0.08, 0.04, 0.025, ""), bounds)
        raise Stop(f"SELECT ALL picked {got}, but this run purified {n}: nothing transferred")
    press(btn[0], bounds)
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


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    runs = os.path.join(HERE, "runs")
    if a[:1] == ["transfer"] and len(a) > 1:
        base.new_run_dir(runs, os.path.abspath(a[1]))
    elif a and a[0] != "--limit":
        sys.exit(__doc__)
    else:
        base.new_run_dir(runs)
    try:
        front()
        if a[:1] != ["transfer"]:
            purify_all(limit)
        transfer_all()
    except Stop as e:
        log(f"STOP: {e}")
        sys.exit(1)
    finally:
        log(f"run folder: {base.RUN_DIR}")
