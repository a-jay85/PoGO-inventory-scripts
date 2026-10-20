#!/usr/bin/env python3
"""Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer.

  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py [--limit N]
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py --look    only step 2, and it only reads: CANCEL every time

Start with Pokémon GO on the Pokémon screen. Three steps, always in this order:
 1. Shortcuts PvpC1 and PvpC2 -> tag PvpC. Shortcut IV Check -> tag IVC. A shortcut this account doesn't have is
    skipped. This goes first: Clean Trades only shows untagged ones (!#), so these drop out of it.
 2. Clean Trades + &countcandyxl0-359 (under 360 Candy XL). Each one is opened and POWER UP tapped once: the dialog's
    "CP a -> b" plus the max HP pin its exact level. At level 14, 19, 22 or 30 (or the half level after) it gets
    1-2 power-ups to reach 15, 20, 23 or 31: the next XL-on-transfer tier
    (~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md). Anything else: CANCEL. Never below 1,000,000 Stardust.
 3. Clean Trades -> tag Transfer.
Tagging: the shortcut's search + &!#<tag>, long press, SELECT ALL, TAG (n). n must equal the search's count, and
afterwards the same search must come back empty.
--limit N powers up at most N Pokémon (the tagging still runs). Log in runs/<time>/.
"""
import math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture, go, look, wait_for, front
import search
import pvp
from shadows import Pass, press, swipe_next, settled_tiles, exact, owned
from trades import sheet_rows, still_sheet

TAGGING = [("PvpC1", "PvpC"), ("PvpC2", "PvpC"), ("IV Check", "IVC")]
CLEAN, TRANSFER = "Clean Trades", "Transfer"
UNDER_360_XL = "&countcandyxl0-359"  # a count term eats what follows it: always last
DUST_FLOOR = 1_000_000
LOOK = False  # --look: read the levels, power up and tag nothing
PLAYS = {14: 15, 19: 20, 22: 23, 30: 31}  # level -> the tier it crosses into (2 taps, or 1 from the half level)
CANDY = {14: 2, 19: 2, 22: 3, 30: 4}  # candy per tap there (purified rounds up to the same)


def key(s):
    """'Clean Trades' / 'CleanTrades' / 'Clean' + 'Trades' -> 'cleantrades'. 'PvpC1' read as 'PvpCl' still matches"""
    return re.sub(r"[il1|]", "l", re.sub(r"[^a-z0-9|]", "", s.lower()))


def same_l(s):
    """OCR mixes up l, i, I, 1 and | ('countcandyx10-359')"""
    return re.sub(r"[il1|]", "l", re.sub(r"\s", "", s.lower()))


# ---------- the saved searches ----------

def panel():
    """the search panel with an empty bar and the shortcuts showing (Android: the keyboard put away) -> texts, bounds"""
    for attempt in range(3):
        if search.clear_search() == "list":
            search.open_panel(look()[3])
        for _ in range(8):
            time.sleep(0.3)
            path, bounds = ui.capture()
            texts = ui.ocr(path)
            if ui.ANDROID and any(t[4].strip() == "?123" and t[1] > 0.5 for t in texts):
                base.key("back")  # hides the keyboard only: the panel stays
                time.sleep(1.0)
                continue
            if any(ui.norm(t[4]) == "FAVORITE" for t in texts):
                return texts, bounds
    keep_capture("panel")
    raise Stop("the search panel with the saved shortcuts didn't show")


def labels(texts):
    """shortcut labels on the panel -> {key: (top line's box, count under it or None)}. A label can wrap ('Clean' /
    'Trades'), and the count sits under the last line"""
    fav = next(t[1] for t in texts if ui.norm(t[4]) == "FAVORITE")
    rec = min([t[1] for t in texts if ui.norm(t[4]) == "RECOMMENDED"] or [1.0])
    boxes = sorted((t for t in texts if fav + 0.03 < t[1] < rec), key=lambda t: t[1])
    mid = lambda t: t[0] + t[2] / 2
    under = lambda t, u: 0.005 < u[1] - t[1] < 0.04 and abs(mid(t) - mid(u)) < 0.05
    out, used = {}, set()
    for t in boxes:
        if id(t) in used or re.fullmatch(r"[\d,]+", t[4].strip()):
            continue
        lines = [t]
        while (nxt := next((u for u in boxes if under(lines[-1], u) and id(u) not in used
                            and not re.fullmatch(r"[\d,]+", u[4].strip())), None)):
            lines.append(nxt)
            used.add(id(nxt))
        n = next((u for u in boxes if under(lines[-1], u) and re.fullmatch(r"[\d,]+", u[4].strip())), None)
        out[key("".join(l[4] for l in lines))] = (t, int(n[4].replace(",", "")) if n else None)
    return out


def results():
    """the search ran: panel closed, list showing. -> its count (0 when no tiles)"""
    for _ in range(16):
        time.sleep(0.25)
        _, texts, _, _ = look()
        if not ui.search_panel(texts) and ui.classify(texts) == "list":
            n = search.result_count(texts)
            if n is not None:
                return n
            if not ui.tiles(texts) and n is None:
                if not settled_tiles():
                    return 0
    keep_capture("results")
    raise Stop("the search didn't come back with a count")


def run_shortcut(name, suffix=""):
    """tap a saved search, then add suffix to its end. -> the count, or None if this account has no such shortcut"""
    for attempt in range(3):
        texts, bounds = panel()
        lab = labels(texts).get(key(name))
        if not lab:
            log(f"no {name!r} shortcut on this account: {sorted(labels(texts))}")
            search.close_panel(bounds)
            return None
        t, n = lab
        if n == 0:  # (a suffix only narrows it)
            log(f"{name}: 0")
            search.close_panel(bounds)
            return 0
        search.click(t[0] + t[2] / 2, t[1] - 0.055, bounds)  # the round button above the label
        time.sleep(0.6)
        _, texts, _, bounds = look()
        if any("MANAGE FAVORITE" in ui.norm(u[4]) for u in texts):  # the tap landed as a long press
            log(f"{name}: the shortcut tap was a long press: again")
            search.click(0.5, 0.937, bounds)  # the box's X
            time.sleep(1.0)
            continue
        got = results()
        if not suffix:
            log(f"{name}: {got}")
            return got
        if append(suffix):
            got2 = results()
            log(f"{name} {suffix}: {got2} (of {got})")
            if got2 > got:
                raise Stop(f"{name}{suffix} shows {got2}, more than {name}'s {got}: the suffix didn't land as an AND")
            return got2
    keep_capture("shortcut")
    raise Stop(f"couldn't run the {name!r} shortcut{' + ' + suffix if suffix else ''}")


def append(suffix):
    """tap the filled bar, type suffix at the end, Return. False if the bar doesn't end with it (cleared after)"""
    bounds = look()[3]
    search.click(0.45, 0.183, bounds, gap=search.BAR_GAP)
    for _ in range(10):
        time.sleep(0.3)
        if ui.search_panel(ui.ocr(ui.capture()[0])):
            break
    else:
        return False
    if ui.ANDROID:
        ui.android.shell("input keyevent KEYCODE_MOVE_END")
    base.type_text(suffix)
    want = same_l(suffix)
    for i in range(6):
        time.sleep(0.3)
        texts = ui.ocr(ui.android.sharp()) if ui.ANDROID and i % 2 else ui.ocr(ui.capture()[0])
        if any(same_l(t[4]).endswith(want) for t in texts):
            base.key("return")
            return True
    keep_capture("append")
    log(f"the bar doesn't end with {suffix!r}: {[t[4] for t in texts if t[1] < 0.62 and '&' in t[4]]}")
    search.close_panel(bounds)
    return False


# ---------- tagging a whole search ----------

def tag_pile(name, tag):
    """tag everything in a shortcut's search (that doesn't have the tag yet)"""
    n = run_shortcut(name, f"&!#{tag}")
    if not n:
        return 0
    _, texts, _, bounds = look()
    first = ui.tiles(texts)[0]
    press((first[2] - 0.03, first[3] - 0.01, 0.06, 0.02, ""), bounds, hold=900)  # long press: multi-select
    for _ in range(20):
        time.sleep(0.15)
        _, texts, _, bounds = look()
        sel = exact(texts, "SELECT ALL")
        if sel and any(re.fullmatch(r"TAG \(\d+\)", t[4].strip()) for t in texts):
            break
    else:
        keep_capture("multiselect")
        raise Stop("long press didn't start multi-select")
    press(sel[0], bounds)
    for _ in range(20):
        time.sleep(0.15)
        _, texts, _, bounds = look()
        btn = [t for t in texts if re.fullmatch(r"TAG \((\d+)\)", t[4].strip())]
        got = int(re.search(r"\d+", btn[0][4]).group()) if btn else None
        if got == n:
            break
    if got != n:
        keep_capture("count")
        search.leave_multiselect(texts, bounds)
        raise Stop(f"{name}: SELECT ALL picked {got}, but the search shows {n}: nothing tagged")
    press(btn[0], bounds)
    wait_for("tags")
    texts, path, bounds = still_sheet()
    head = " ".join(t[4] for t in texts if t[1] < 0.15)
    if not re.search(rf"TAG {n} POK", ui.norm(head)):
        close_sheet(texts, bounds)
        raise Stop(f"the tag sheet says {head!r}, wanted {n}")
    T, same = tag.upper(), 0
    for _ in range(30):
        rows = sheet_rows(texts, path)
        if T in rows:
            box, ticked = rows[T]
            if ticked:  # none of these have it (the search said so): a tick here is a misread or a partial mark
                close_sheet(texts, bounds)
                raise Stop(f"{tag} already shows a tick for this lot: nothing tagged")
            press(box, bounds)
            for _ in range(20):
                time.sleep(0.15)
                _, t2, p2, _ = wait_for("tags")
                r = sheet_rows(t2, p2)
                if T in r and r[T][1]:
                    break
            else:
                keep_capture("tick")
                close_sheet(t2, bounds)
                raise Stop(f"tapped {tag} but its tick didn't come on")
            break
        before = [t[4] for t in texts]
        base.drag(0.3, 0.62, 0.3, 0.4, bounds)  # small steps: a big scroll skips rows
        if ui.ANDROID:
            ui.android.fresh()
        texts, path, bounds = still_sheet()
        same = same + 1 if [t[4] for t in texts] == before else 0
        if same >= 2:
            close_sheet(texts, bounds)
            raise Stop(f"no {tag} tag on this account: nothing tagged")
    else:
        close_sheet(texts, bounds)
        raise Stop(f"couldn't find {tag} in the tag sheet")
    texts, _, bounds = still_sheet()
    press(next(t for t in texts if ui.norm(t[4]) == "DONE"), bounds)
    wait_for("list", timeout=8)
    left = run_shortcut(name, f"&!#{tag}")
    if left:
        raise Stop(f"{name}: tagged {n} {tag}, but {left} still don't have it")
    log(f"{name}: tagged {n} {tag}")
    return n


def close_sheet(texts, bounds):
    """leave the tag sheet unsaved (Android: the X under DONE), then multi-select"""
    if not ui.ANDROID:
        go("CANCEL", "list")
    else:
        d = next(t for t in texts if ui.norm(t[4]) == "DONE")
        press((d[0] + d[2] / 2 - 0.03, d[1] + 0.075, 0.06, 0.03, ""), bounds)
    _, texts, _, bounds = wait_for("list")
    search.leave_multiselect(texts, bounds)


# ---------- powering up ----------

def candidates(species, hp, a, b):
    """every (species, IVs, level) with this max HP, CP a, and CP b one power-up later"""
    out = []
    for sid in species:
        st = pvp.SPECIES[sid]["baseStats"]
        for lv in pvp.LEVELS[:-1]:
            m, m2 = pvp.cpm(lv), pvp.cpm(lv + 0.5)
            for h in range(16):
                if max(10, math.floor((st["hp"] + h) * m)) != hp:
                    continue
                for at in range(16):
                    for d in range(16):
                        iv = (at, d, h)
                        if pvp.cp(st, iv, lv) == a and pvp.cp(st, iv, lv + 0.5) == b:
                            out.append((sid, iv, lv))
    return out


def cp_levels(species, hp, cp):
    """every level some IVs give this CP and max HP at: no tap needed"""
    out = set()
    for sid in species:
        st = pvp.SPECIES[sid]["baseStats"]
        for lv in pvp.LEVELS:
            m = pvp.cpm(lv)
            hs = [h for h in range(16) if max(10, math.floor((st["hp"] + h) * m)) == hp]
            if any(pvp.cp(st, (at, d, h), lv) == cp for h in hs for at in range(16) for d in range(16)):
                out.add(lv)
    return sorted(out)


def dialog(info):
    """tap POWER UP on the detail page. -> (CP now, CP after, dust cost, the dialog's POWER UP box, CANCEL box)"""
    _, texts, _, bounds = look()
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.6]
    if len(btn) != 1:
        raise Pass("can't find POWER UP")
    press(btn[0], bounds)
    for _ in range(25):
        time.sleep(0.12)
        _, texts, _, bounds = look()
        head = next((t[4] for t in texts if re.match(r"POWER UP\s*:", t[4].strip(), re.I)), None)
        cps = next((m for t in texts if (m := re.fullmatch(r"CP\s*(\d+)\D+(\d+)", t[4].strip()))), None)
        ok = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.75]
        cancel = exact(texts, "CANCEL")
        if head and cps and len(ok) == 1 and len(cancel) == 1 and int(cps.group(1)) == info["cp"]:
            break  # (its CP must be the page's: 'CP 372 →385' can read as 'CP3 →72')
    else:
        keep_capture("powerdialog")
        raise Stop("no power-up dialog after tapping POWER UP")
    if ui.letters(head.split(":", 1)[1]) != ui.letters(info["name"]):
        press(cancel[0], bounds)
        raise Stop(f"the power-up dialog names someone else: {head!r} (wanted {info['name']})")
    a, b = int(cps.group(1)), int(cps.group(2))
    dust = next((int(m.group().replace(",", "")) for t in texts if cps.string not in t[4]
                 and (m := re.search(r"\d{1,2},\d{3}", t[4]))), None)
    return a, b, dust, ok[0], cancel[0], bounds


def cancel(box, bounds):
    press(box, bounds)
    wait_for("detail")


def by_bars(cands):
    """appraise (and come back to the detail page): keep the candidates with the bars' IVs, else within 1 of them"""
    try:
        _, ivs, _, what = base.high_iv()
    except base.Skip as e:
        raise Pass(f"can't read its IV: {e}")
    log(f"  appraised {what}")
    exact_iv = [c for c in cands if c[1] == tuple(ivs)]
    return exact_iv or [c for c in cands if max(abs(x - y) for x, y in zip(c[1], ivs)) <= 1]


def power_up(info, texts):
    """1-2 power-ups if this one sits right under an XL tier. -> taps made. Raise Pass to leave it."""
    species = ui.species_for(info["name"], info["texts"])
    if not species:
        raise Pass(f"don't know the species of {info['name']!r}")
    lvs = cp_levels(species, info["hp"], info["cp"])
    if not any(math.floor(lv) in PLAYS for lv in lvs):  # its CP already rules out every play: no taps
        raise Pass(f"CP{info['cp']} HP{info['hp']} means level {lvs[0] if lvs else '?'}-{lvs[-1] if lvs else '?'}: "
                   f"none is {'/'.join(map(str, PLAYS))}")
    have_dust, have_candy = owned(texts)
    if have_dust < DUST_FLOOR:
        raise Stop(f"Stardust {have_dust:,} is under {DUST_FLOOR:,}: no more power-ups")
    taps, cands = 0, None
    while True:
        a, b, dust, ok, no, bounds = dialog(info)
        if cands is None:
            cands = candidates(species, info["hp"], a, b)
        else:  # one tap later: the CP must match, and the new 'after' narrows it again
            cands = [(s, iv, lv + 0.5) for s, iv, lv in cands]
            cands = [(s, iv, lv) for s, iv, lv in cands if pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv) == a
                     and pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv + 0.5) == b]
        lvs = sorted({lv for _, _, lv in cands})
        if not taps:
            goal = {PLAYS.get(math.floor(lv)) for lv in lvs}
            if len(goal) > 1 and goal - {None}:  # some of its possible levels are a play, some aren't: the bars decide
                cancel(no, bounds)
                cands = by_bars(cands)
                lvs = sorted({lv for _, _, lv in cands})
                goal = {PLAYS.get(math.floor(lv)) for lv in lvs}
                if not lvs or len(goal) != 1 or None in goal:  # (the dialog is closed already)
                    raise Pass(f"appraised: level {lvs or '?'} (CP{a}->{b}): no XL tier one or two taps away")
                a2, b2, dust, ok, no, bounds = dialog(info)
                if (a2, b2) != (a, b):
                    cancel(no, bounds)
                    raise Stop(f"the power-up dialog read CP{a}->{b}, now CP{a2}->{b2}")
            if not lvs or len(goal) != 1 or None in goal:
                cancel(no, bounds)
                raise Pass(f"level {lvs or '?'} (CP{a}->{b}): no XL tier one or two taps away")
            target = goal.pop()
            need = sum(CANDY[math.floor(lv)] for lv in (min(lvs), min(lvs) + 0.5) if lv < target)
            if have_candy < need:
                cancel(no, bounds)
                raise Pass(f"level {lvs}: needs {need} candy, has {have_candy}")
            if have_dust - 2 * (dust or 10000) < DUST_FLOOR:
                cancel(no, bounds)
                raise Stop(f"Stardust {have_dust:,} would drop under {DUST_FLOOR:,}: no more power-ups")
            log(f"  level {lvs} -> {target}  (CP{a}->{b}, {dust} dust a tap)")
            if LOOK:
                cancel(no, bounds)
                raise Pass(f"--look: would power up level {lvs} to {target}")
        if lvs and all(lv >= target for lv in lvs):  # crossed: this dialog was only the check
            cancel(no, bounds)
            return taps
        if taps >= 2:  # never a 3rd
            cancel(no, bounds)
            raise Stop(f"2 taps and the level reads {lvs}, still not {target}")
        if any(lv >= target for lv in lvs) or not lvs:
            cancel(no, bounds)
            raise Pass(f"after {taps} tap(s) the level reads {lvs}: can't tell if it crossed {target}")
        press(ok, bounds)
        end = time.time() + 15
        while time.time() < end:  # done = dialog gone, the detail shows the new CP
            time.sleep(0.15)
            screen, t2, _, _ = look()
            if screen == "detail" and not any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in t2) \
                    and ui.detail_info(t2)["cp"] == b:
                break
        else:
            keep_capture("powerup")
            raise Stop(f"the power-up to CP{b} didn't show in 15s")
        taps += 1
        info = {**info, "cp": b}


def power_walk(limit):
    """open each Clean Trades one with under 360 XL and power up those right under a tier. -> how many got it"""
    if not run_shortcut(CLEAN, UNDER_360_XL):
        log("no Clean Trades ones under 360 XL")
        return 0
    go("tile 1", "detail")
    seen, done, passed, t_start = set(), 0, 0, time.time()
    while True:
        t0 = time.time()
        _, texts, _, _ = wait_for("detail")
        info = ui.detail_info(texts)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:
            log("swiped back onto one already seen: end of the list")
            break
        seen.add(me)
        if done >= limit:
            log(f"--limit {limit} reached")
            break
        try:
            taps = power_up(info, texts)
        except Pass as e:
            passed += 1
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        else:
            done += 1
            info2 = ui.detail_info(wait_for("detail")[1])
            seen.add((info2["name"], info2["cp"], info2["hp"]))
            log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {taps} tap(s)  ({time.time() - t0:.1f}s)")
        moved = False
        for attempt in range(2):  # next one; a swipe that does nothing twice = end of the list
            swipe_next(look()[3])
            for _ in range(10):
                time.sleep(0.12)
                screen, texts, _, _ = look()
                if screen == "detail":
                    n = ui.detail_info(texts)
                    if (n["name"], n["cp"], n["hp"]) not in seen:
                        moved = True
                        break
            if moved:
                break
        if not moved:
            break
    log(f"powered up {done}, passed {passed}, {time.time() - t_start:.0f}s")
    go("close", "list")
    return done


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x not in ("--limit", "--look") and not x.isdigit() for x in a):
        sys.exit(__doc__)
    LOOK = "--look" in a
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    base.new_run_dir(os.path.join(HERE, "runs"))
    try:
        front()
        search.to_search_list()  # (from the map too)
        if LOOK:
            power_walk(limit)
            sys.exit(0)
        for name, tag in TAGGING:  # first: Clean Trades (!#) must only see what's left untagged after these
            tag_pile(name, tag)
        try:
            power_walk(limit)
        except Stop as e:
            if "Stardust" not in str(e):
                raise
            log(f"stopped powering up: {e}")
            if look()[0] != "list":
                go("close", "list")
        tag_pile(CLEAN, TRANSFER)
    except Stop as e:
        log(f"STOP: {e}")
        sys.exit(1)
    finally:
        log(f"run folder: {base.RUN_DIR}")
