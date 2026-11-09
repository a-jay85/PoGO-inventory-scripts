#!/usr/bin/env python3
"""Powering one Pokémon up: its level from the page and the dialog, and the cheap jumps to the next Candy XL tier."""
import math, os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import ui
import base
from base import Stop, Skip, log, keep_capture, go, look, wait_for
import search
import pvp
from taps import Pass, press, exact, owned


class Unsure(Pass):
    """left because something couldn't be read: it may still want a power-up, so it isn't done with"""

DUST_FLOOR = 1_000_000
LOOK = False  # --look: read the levels, power up and tag nothing
XL_ODDS = [(1, 25), (15, 125), (20, 250), (23, 400), (26, 500), (31, 750)]  # (from level, Candy XL on transfer, per mille)
PLAY_DUST = 40_000  # Stardust per Candy XL gained, at most: the dearest of the normal plays (19, 22 and 30 each cost it)
DUST = [(1, 200), (3, 400), (5, 600), (7, 800), (9, 1000), (11, 1300), (13, 1600), (15, 1900), (17, 2200),
        (19, 2500), (21, 3000), (23, 3500), (25, 4000), (27, 4500), (29, 5000), (31, 6000), (33, 7000),
        (35, 8000), (37, 9000), (39, 10000)]  # (from level, Stardust a power-up)
DUST_RATE = (1, 0.5, 0.9, 0.45)  # normal, lucky, purified, both


def dust_at(lv):
    """Stardust for one power-up from this level (before the lucky / purified discount)"""
    return next(c for first, c in reversed(DUST) if lv >= first)


def xl_odds(lv):
    return next(p for first, p in reversed(XL_ODDS) if lv >= first)


def plays_for(rate):
    """level -> the next Candy XL tier on transfer, where reaching it costs at most PLAY_DUST Stardust per Candy XL
    gained (~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md). Candy isn't counted: it's plentiful. The next
    tier only: a step past it is scored on its own, and none passes"""
    out = {}
    for lv in range(1, XL_ODDS[-1][0]):
        to = next(first for first, _ in XL_ODDS if first > lv)
        dust = sum(round(dust_at(lv + k / 2) * rate) for k in range((to - lv) * 2))
        if dust * 1000 <= PLAY_DUST * (xl_odds(to) - xl_odds(lv)):
            out[lv] = to
    return out


PLAYS = plays_for(DUST_RATE[0])  # {14: 15, 19: 20, 22: 23, 30: 31}: 2 taps (1 from the half level)
# lucky, half the Stardust: a level 2 back costs the same per Candy XL (4 taps), and 25 -> 26 sits right on PLAY_DUST
LUCKY_PLAYS = plays_for(DUST_RATE[1])  # {13: 15, 14: 15, 18: 20, 19: 20, 21: 23, 22: 23, 25: 26, 29: 31, 30: 31}
PURIFIED_AT = 25  # purifying sets the level to 25
MAX_PLUS = 4  # + taps to find the level: from 19 the cost only jumps on the 5th power-up (at 21)


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


def nickname_species(info, texts):
    """a nickname ('96 HA') names no species: the candy line and types (no taps), else the appraisal's 'This Gible
    was caught' line. Back on the detail page after. -> species, or [] if neither tells"""
    try:
        return base.species_from_candy(texts, info["cp"], info["hp"])
    except Skip as e:
        log(f"  {e}: asking the appraisal")
    base.open_appraisal()
    try:
        sp = base.appraisal_species(info["texts"])
        base.appraise()  # (the bars filled in: one tap closes it)
    except Skip as e:
        log(f"  {e}")
        sp = []
    go("dialog", "detail")
    return sp


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


def page_cost(texts):
    """the Stardust next to POWER UP on the detail page, or None if it can't be read"""
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[0] < 0.4 and t[1] > 0.6]
    if len(btn) != 1:
        return None
    got = [int(re.sub(r"\D", "", m.group(1))) for t in texts if abs(t[1] - btn[0][1]) < 0.02 and 0.4 < t[0] < 0.7
           and (m := re.fullmatch(r"(?:\S\s+|\D{0,3}?)(\d{1,2}[,.]\d{3}|\d{2,3})", t[4].strip()))]  # icon: '1 7,000'
    if len(got) != 1:
        return None
    if got[0] > 10_000 and got[0] % 1000:  # the icon read as a 1 with no space ('12,200'): XL costs are whole thousands
        return got[0] - 10_000
    return got[0]


def page_candy(texts):
    """the Candy next to the Stardust on the detail page's POWER UP row, or None if it can't be read (it often can't)"""
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[0] < 0.4 and t[1] > 0.6]
    got = [int(t[4].strip()) for t in texts if btn and abs(t[1] - btn[0][1]) < 0.02 and t[0] > 0.68
           and re.fullmatch(r"\d{1,2}", t[4].strip())]
    return got[0] if len(got) == 1 else None


def candy_at(lv):
    """Candy for one power-up from this level, under 40 (a purified one's rounds up to the same)"""
    return next(c for first, c in ((39, 15), (37, 12), (35, 10), (33, 8), (31, 6), (26, 4), (21, 3), (11, 2), (1, 1))
                if lv >= first)


def cost_levels(texts, cp):
    """-> (cost, every level the detail page's power-up cost fits). Lucky shows on the page. A purified one is always
    level 25 (3,600, or 1,800 lucky): purifying puts it there and it's transferred from there. No levels = a cost no
    table has, or no two looks in a row agreed on it"""
    cost = page_cost(texts)
    for _ in range(6):  # right after a swipe the page still slides: a cost read then can be another's (2,200 read as
        _, texts, _, _ = look()  # level 40+, 2026-10-23). Two looks in a row on this CP must agree
        again = page_cost(texts)
        if again == cost and ui.detail_info(texts)["cp"] == cp:
            break
        cost = again
    else:
        cost = None
    if cost is None:
        return None, []
    rate, purified = DUST_RATE[1::2] if is_lucky(texts) else DUST_RATE[0::2]
    if cost == round(dust_at(PURIFIED_AT) * purified):
        return cost, [PURIFIED_AT]
    if cost > round(DUST[-1][1] * rate):  # past the table: an XL Candy power-up, level 40+
        return cost, [lv / 2 for lv in range(80, 100)]
    lvs = set()
    for i, (first, c) in enumerate(DUST):
        last = DUST[i + 1][0] if i + 1 < len(DUST) else 50
        if round(c * rate) == cost:
            lvs.update(first + k / 2 for k in range(int((last - first) * 2)))
    candy = page_candy(texts)  # splits a cost that spans a candy step: 4,000 is 3 Candy at 25-25.5, 4 at 26-26.5
    if candy is None and ui.ANDROID and len({candy_at(lv) for lv in lvs if lv < 40}) > 1:
        candy = page_candy(ui.ocr(ui.android.sharp()))  # the small digit mostly reads only at full size
    if candy and {lv for lv in lvs if candy_at(lv) == candy}:
        lvs = {lv for lv in lvs if candy_at(lv) == candy}
    return cost, sorted(lvs)


def read_dialog(cp, after=None):
    """the open power-up dialog. Wait until its first CP is the page's and (after a +) its 'after' CP has moved.
    -> (CP after, total dust, POWER UP box, CANCEL box, + box, bounds, title)"""
    for _ in range(25):
        time.sleep(search.POLL)
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
        if not plus:  # the thin + on its pale ring mostly goes unread: it sits right of the cost.
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


def is_lucky(texts):
    return any(ui.norm(t[4]).startswith("LUCKY POK") for t in texts)


def steps(cands, plays=PLAYS):
    """power-ups each possible level needs to reach its XL tier (None: not a play)"""
    return {int((plays[math.floor(lv)] - lv) * 2) if math.floor(lv) in plays else None for _, _, lv in cands}


def power_up(info, texts, levels=None):
    """1-2 power-ups (up to 4 for a lucky one) if this one sits right under an XL tier (PLAYS, LUCKY_PLAYS). -> power-ups made. Raise Pass to leave it.
    Its level comes from the dialog: + adds a power-up, and each total (CP after, Stardust) rules levels out.
    levels: the caller's (its IVs, CP and HP can name the one level): narrows the cost's, or stands in when it doesn't read"""
    cost, lvs = cost_levels(texts, info["cp"])
    lvs = sorted(set(lvs) & set(levels or ())) or lvs or sorted(levels or ())
    if not lvs:
        raise Unsure(f"can't read the power-up cost ({cost})")
    plays = LUCKY_PLAYS if is_lucky(texts) else PLAYS  # (lucky: half the Stardust, more plays)
    if not any(math.floor(lv) in plays for lv in lvs):  # the cost rules out every play: no taps
        raise Pass(f"{cost} dust a power-up means level {lvs[0]}-{lvs[-1]}: none is {'/'.join(map(str, plays))}")
    species = ui.species_for(info["name"], info["texts"]) or nickname_species(info, texts)
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
    cands = [c for c in cands if c[2] in lvs] or cands  # (a level already known needs no + to find it)
    while len(steps(cands, plays)) > 1 and len(rows) < MAX_PLUS + 1:  # a play for some levels only: one more +
        d = more(cp, d)
        rows.append((len(rows) + 1, d[0], d[1]))
        cands = [c for c in cands if fits(c, rows)]
    lvs = sorted({lv for _, _, lv in cands})
    need = steps(cands, plays)
    say = f"level {lvs or '?'} (CP{cp} -> " + ", ".join(f"{n}x: CP{b} {t} dust" for n, b, t in rows) + ")"
    if len(need) != 1 or None in need:
        cancel(d[3], d[5])
        raise Pass(f"{say}: no XL tier a cheap jump away")
    n = need.pop()
    target = plays[math.floor(lvs[0])]
    if n != len(rows):  # the dialog shows more power-ups than it needs: open it again and count up
        cancel(d[3], d[5])
        d = dialog(info)
        for _ in range(n - 1):
            d = more(cp, d)
    after, total = d[0], d[1]
    want = {pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv + 0.5 * n) for s, iv, lv in cands}
    if after not in want:  # (IVs that fit can still part ways on the CP n power-ups later: the level is the same)
        cancel(d[3], d[5])
        raise Stop(f"{n} power-up(s) should give CP{sorted(want)}, the dialog says CP{after}")
    candy = sum(candy_at(lvs[0] + 0.5 * k) for k in range(n))  # (25.5 -> 26 is still 3)
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
    end, tapped = time.time() + 30, time.time()
    while time.time() < end:  # done = dialog gone, the detail shows the new CP
        time.sleep(search.POLL)
        screen, t2, _, b2 = look()
        again = time.time() - tapped > 3  # a tap can miss: tap again while the same box is still up
        no = exact(t2, "NO")
        if len(no) == 1 and any("really want to power up" in t[4] for t in t2):
            if again:
                yes = exact(t2, "YES")  # (YES is white on green: OCR mostly misses it)
                press(yes[0] if len(yes) == 1 else (no[0][0], no[0][1] - 0.078, no[0][2], no[0][3], "YES"), b2)
                tapped = time.time()
            continue
        head = any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in t2)
        if head:  # still the power-up box: retap POWER UP only while it shows this same power-up
            same = any((m := re.fullmatch(r"CP\s*(\d+)\D+(\d+)", t[4].strip())) and m.groups() == (str(cp), str(after))
                       for t in t2)
            ok = [t for t in t2 if ui.norm(t[4]) == "POWER UP" and t[1] > 0.75]
            if again and same and len(ok) == 1:
                log(f"  the POWER UP tap didn't take: again")
                press(ok[0], b2)
                tapped = time.time()
            continue
        if screen == "detail" and ui.detail_info(t2)["cp"] == after:
            return n
    keep_capture("powerup")
    raise Stop(f"the power-up to CP{after} didn't show in 30s")
