#!/usr/bin/env python3
"""Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer.

  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py [--limit N]
  caffeinate -dimsu python3 cleantrades.py [--limit N]    the iPhone, through iPhone Mirroring
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py --look    only step 2, and it only reads: CANCEL every time

Start with Pokémon GO on the Pokémon screen. Three steps, always in this order:
 1. Shortcuts PvpC1 and PvpC2 -> tag PvpC. Shortcut IV Check -> tag IVC. A shortcut this account doesn't have is
    skipped. This goes first: Clean Trades only shows untagged ones (!#), so these drop out of it.
 2. Clean Trades + &countcandyxl0-359 (under 360 Candy XL). Each one is opened and POWER UP tapped: the dialog's
    "CP a -> b" and Stardust cost narrow its level. Each + (one more power-up) shows new totals that narrow it
    more. At level 14, 19, 22 or 30 (or the half level after) it gets 1-2 power-ups in one go, to reach 15, 20, 23
    or 31: the next XL-on-transfer tier
    (~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md). Anything else: CANCEL. Never below 1,000,000 Stardust.
 3. Clean Trades -> tag Transfer.
Tagging: the shortcut's search + &!#<tag> (PvpC1 and PvpC2 as they are: they already exclude tagged ones), long press, SELECT ALL, TAG (n). n must equal the search's count, and
afterwards the same search must come back empty.
--limit N powers up at most N Pokémon (the tagging still runs). Log in runs/<time>/.
"""
import math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture, go, look, wait_for
import search
import pvp
from shadows import Pass, press, swipe_next, settled_tiles, exact, owned
from trades import sheet_rows, still_sheet


class Unsure(Pass):
    """left because something couldn't be read: it may still want a power-up, so it isn't done with"""

TAGGING = [("PvpC1", "PvpC"), ("PvpC2", "PvpC"), ("IV Check", "IVC")]
UNTAGGED_ONLY = {"PvpC1", "PvpC2"}  # their own search already has !#, and on the Pixel the bar is too full to add to
CLEAN, TRANSFER = "Clean Trades", "Transfer"
UNDER_360_XL = "&countcandyxl0-359"  # a count term eats what follows it: always last
DUST_FLOOR = 1_000_000
LOOK = False  # --look: read the levels, power up and tag nothing
PLAYS = {14: 15, 19: 20, 22: 23, 30: 31}  # level -> the tier it crosses into (2 taps, or 1 from the half level)
CANDY = {14: 2, 19: 2, 22: 3, 30: 4}  # candy per tap there (purified rounds up to the same)
DUST = [(1, 200), (3, 400), (5, 600), (7, 800), (9, 1000), (11, 1300), (13, 1600), (15, 1900), (17, 2200),
        (19, 2500), (21, 3000), (23, 3500), (25, 4000), (27, 4500), (29, 5000), (31, 6000), (33, 7000),
        (35, 8000), (37, 9000), (39, 10000)]  # (from level, Stardust a power-up)
DUST_RATE = (1, 0.5, 0.9, 0.45)  # normal, lucky, purified, both
PURIFIED_AT = 25  # purifying sets the level to 25
MAX_PLUS = 4  # + taps to find the level: from 19 the cost only jumps on the 5th power-up (at 21)


def key(s):
    """'Clean Trades' / 'CleanTrades' / 'Clean' + 'Trades' -> 'cleantrades'. 'PvpC1' read as 'PvpCl' still matches"""
    return re.sub(r"[il1|]", "l", re.sub(r"[^a-z0-9|]", "", s.lower()))


def same_l(s):
    """OCR mixes up l, i, I, 1 and | ('countcandyx10-359'), and reads '!' as ':'"""
    return re.sub(r"[il1|!:]", "l", re.sub(r"\s", "", s.lower()))


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
    else:
        base.key("right", cmd=True)
    base.type_text(suffix)
    want = same_l(suffix)
    if len(want) > 24:  # a long one doesn't fit in the bar: only its end shows
        want = want[-24:]
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

def tag_pile(name, tag, suffix=None):
    """tag everything in a shortcut's search + suffix (default: the ones that don't have the tag yet). The suffix must
    leave out the tag itself: afterwards the same search has to come back empty"""
    if suffix is None:
        suffix = "" if name in UNTAGGED_ONLY else f"&!#{tag}"
    n = run_shortcut(name, suffix)
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
    if not re.search(rf"TAG\s*{n}\s*POK", head.upper()):  # (ui.norm drops digits)
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
    left = run_shortcut(name, suffix)
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


def dust_at(lv):
    """Stardust for one power-up from this level (before the lucky / purified discount)"""
    return next(c for first, c in reversed(DUST) if lv >= first)


def page_cost(texts):
    """the Stardust next to POWER UP on the detail page, or None if it can't be read"""
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[0] < 0.4 and t[1] > 0.6]
    if len(btn) != 1:
        return None
    got = [int(re.sub(r"\D", "", m.group(1))) for t in texts if abs(t[1] - btn[0][1]) < 0.02 and 0.4 < t[0] < 0.7
           and (m := re.fullmatch(r"(?:\S\s+|\D{0,3}?)(\d{1,2}[,.]\d{3}|\d{2,3})", t[4].strip()))]  # icon: '1 7,000'
    return got[0] if len(got) == 1 else None


def cost_levels(texts):
    """-> (cost, every level the detail page's power-up cost fits). Lucky shows on the page. A purified one is always
    level 25 (3,600, or 1,800 lucky): purifying puts it there and it's transferred from there. No levels = a cost no
    table has"""
    cost = page_cost(texts)
    if cost is None:
        return None, []
    lucky = any(ui.norm(t[4]).startswith("LUCKY POK") for t in texts)
    rate, purified = DUST_RATE[1::2] if lucky else DUST_RATE[0::2]
    if cost == round(dust_at(PURIFIED_AT) * purified):
        return cost, [PURIFIED_AT]
    if cost > round(DUST[-1][1] * rate):  # past the table: an XL Candy power-up, level 40+
        return cost, [lv / 2 for lv in range(80, 100)]
    lvs = set()
    for i, (first, c) in enumerate(DUST):
        last = DUST[i + 1][0] if i + 1 < len(DUST) else 50
        if round(c * rate) == cost:
            lvs.update(first + k / 2 for k in range(int((last - first) * 2)))
    return cost, sorted(lvs)


def read_dialog(cp, after=None):
    """the open power-up dialog. Wait until its first CP is the page's and (after a +) its 'after' CP has moved.
    -> (CP after, total dust, POWER UP box, CANCEL box, + box, bounds, title)"""
    for _ in range(25):
        time.sleep(0.12)
        _, texts, _, bounds = look()
        head = next((t for t in texts if re.match(r"POWER UP\s*:", t[4].strip(), re.I)), None)
        line = next((t for t in texts if re.fullmatch(r"CP\s*(\d+)\D+(\d+)", t[4].strip())), None)
        ok = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.75]
        no = exact(texts, "CANCEL")
        if not (head and line and len(ok) == 1 and len(no) == 1):
            continue
        a, b = map(int, re.fullmatch(r"CP\s*(\d+)\D+(\d+)", line[4].strip()).groups())
        if a != cp or b == after:  # (its CP must be the page's: 'CP 372 →385' can read as 'CP3 →72')
            continue
        dust = next((int(m.group(1).replace(",", "")) for t in texts if line[1] + 0.02 < t[1] < line[1] + 0.075
                     and (m := re.fullmatch(r"\D{0,3}?(\d{1,2},\d{3}|\d{3})", t[4].strip()))), None)
        plus = [t for t in texts if t[4].strip() == "+" and t[0] > 0.6 and line[1] < t[1] < ok[0][1]]
        if not plus and ui.ANDROID:  # the thin + on its pale ring mostly goes unread: it sits right of the cost.
            plus = [(0.723, line[1] + 0.058, 0.073, 0.04, "+?")]  # more() checks the CP moved
        return b, dust, ok[0], no[0], plus[0] if plus else None, bounds, head[4]
    keep_capture("powerdialog")
    raise Stop("no power-up dialog, or its CP didn't move after +")


def dialog(info):
    """tap POWER UP on the detail page. -> read_dialog() without the title"""
    _, texts, _, bounds = look()
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.6]
    if len(btn) != 1:
        raise Pass("can't find POWER UP")
    press(btn[0], bounds)
    *got, head = read_dialog(info["cp"])
    if ui.letters(head.split(":", 1)[1]) != ui.letters(info["name"]):
        press(got[3], got[5])
        raise Stop(f"the power-up dialog names someone else: {head!r} (wanted {info['name']})")
    return got


def more(cp, d):
    """tap + in the dialog: one more power-up. -> read_dialog() with the new totals"""
    if not d[4]:
        cancel(d[3], d[5])
        raise Unsure("no + in the power-up dialog")
    press(d[4], d[5])
    try:
        return read_dialog(cp, after=d[0])[:-1]
    except Stop:
        if d[4][4] != "+?":
            raise
        cancel(d[3], d[5])
        raise Unsure("tapped where + sits, but the dialog's CP didn't move")


def cancel(box, bounds):
    press(box, bounds)
    for _ in range(20):  # the detail shows through the dialog as it fades: wait for its title to go, or X can't be found
        texts = wait_for("detail")[1]
        if not any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in texts):
            return
        time.sleep(0.15)


def fits(c, rows):
    """does this (species, IVs, level) give every dialog row (n power-ups, CP after, total dust)?"""
    sid, iv, lv = c
    st = pvp.SPECIES[sid]["baseStats"]
    if any(pvp.cp(st, iv, lv + 0.5 * n) != b for n, b, _ in rows):
        return False
    return any(all(t is None or t == sum(round(m * dust_at(lv + 0.5 * k)) for k in range(n)) for n, _, t in rows)
               for m in DUST_RATE)


def steps(cands):
    """power-ups each possible level needs to reach its XL tier (None: not a play)"""
    return {int((PLAYS[math.floor(lv)] - lv) * 2) if math.floor(lv) in PLAYS else None for _, _, lv in cands}


def power_up(info, texts):
    """1-2 power-ups if this one sits right under an XL tier. -> power-ups made. Raise Pass to leave it.
    Its level comes from the dialog: + adds a power-up, and each total (CP after, Stardust) rules levels out."""
    cost, lvs = cost_levels(texts)
    if not lvs:
        raise Unsure(f"can't read the power-up cost ({cost})")
    if not any(math.floor(lv) in PLAYS for lv in lvs):  # the cost rules out every play: no taps
        raise Pass(f"{cost} dust a power-up means level {lvs[0]}-{lvs[-1]}: none is {'/'.join(map(str, PLAYS))}")
    species = ui.species_for(info["name"], info["texts"])
    if not species:
        raise Unsure(f"{cost} dust: don't know the species of {info['name']!r}")
    if info["cp"] is None:
        raise Unsure(f"{cost} dust: can't read its CP")
    have_dust, have_candy = owned(texts)
    if have_dust < DUST_FLOOR:
        raise Stop(f"Stardust {have_dust:,} is under {DUST_FLOOR:,}: no more power-ups")
    cp = info["cp"]
    d = dialog(info)
    rows = [(1, d[0], d[1])]
    cands = [c for c in candidates(species, info["hp"], cp, d[0]) if fits(c, rows)]
    while len(steps(cands)) > 1 and len(rows) < MAX_PLUS + 1:  # a play for some levels only: one more +
        d = more(cp, d)
        rows.append((len(rows) + 1, d[0], d[1]))
        cands = [c for c in cands if fits(c, rows)]
    lvs = sorted({lv for _, _, lv in cands})
    need = steps(cands)
    say = f"level {lvs or '?'} (CP{cp} -> " + ", ".join(f"{n}x: CP{b} {t} dust" for n, b, t in rows) + ")"
    if len(need) != 1 or None in need:
        cancel(d[3], d[5])
        raise Pass(f"{say}: no XL tier one or two power-ups away")
    n = need.pop()
    target = PLAYS[math.floor(lvs[0])]
    if n != len(rows):  # the dialog shows more power-ups than it needs: open it again and count up
        cancel(d[3], d[5])
        d = dialog(info)
        for _ in range(n - 1):
            d = more(cp, d)
    after, total = d[0], d[1]
    want = {pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv + 0.5 * n) for s, iv, lv in cands}
    if want != {after}:
        cancel(d[3], d[5])
        raise Stop(f"{n} power-up(s) should give CP{sorted(want)}, the dialog says CP{after}")
    candy = sum(CANDY[math.floor(lvs[0])] for _ in range(n))
    if have_candy < candy:
        cancel(d[3], d[5])
        raise Pass(f"{say}: needs {candy} candy, has {have_candy}")
    if total is None or have_dust - total < DUST_FLOOR:
        cancel(d[3], d[5])
        raise Stop(f"Stardust {have_dust:,} - {total} would drop under {DUST_FLOOR:,}: no more power-ups")
    log(f"  {say} -> {target}: {n} power-up(s), CP{after}, {total:,} dust")
    if LOOK:
        cancel(d[3], d[5])
        raise Pass(f"--look: would power up level {lvs} to {target}")
    press(d[2], d[5])
    end, sure = time.time() + 15, False
    while time.time() < end:  # done = dialog gone, the detail shows the new CP
        time.sleep(0.15)
        screen, t2, _, b2 = look()
        no = exact(t2, "NO")
        if not sure and len(no) == 1 and any("really want to power up" in t[4] for t in t2):
            press((no[0][0], no[0][1] - 0.078, no[0][2], no[0][3], "YES"), b2)  # (YES is white on green: OCR misses it)
            sure = True
            continue
        if screen == "detail" and not any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in t2) \
                and ui.detail_info(t2)["cp"] == after:
            return n
    keep_capture("powerup")
    raise Stop(f"the power-up to CP{after} didn't show in 15s")


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
            return None  # (the rest weren't checked)
        try:
            taps = power_up(info, texts)
        except Pass as e:
            passed += 1
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        else:
            done += 1
            info2 = ui.detail_info(wait_for("detail")[1])
            seen.add((info2["name"], info2["cp"], info2["hp"]))
            log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {taps} power-up(s)  ({time.time() - t0:.1f}s)")
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
        base.start()  # from anywhere, Pokémon GO closed too
        search.to_search_list()
        if LOOK:
            power_walk(limit)
            sys.exit(0)
        for name, tag in TAGGING:  # first: Clean Trades (!#) must only see what's left untagged after these
            tag_pile(name, tag)
        try:
            if power_walk(limit) is None:
                log(f"--limit {limit}: the rest weren't checked, so Clean Trades isn't tagged Transfer")
                sys.exit(0)
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
