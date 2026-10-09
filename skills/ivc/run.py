#!/usr/bin/env python3
"""Unattended /ivc: works through the IVC-tagged list in iPhone Mirroring with no Claude.

  caffeinate -dimsu python3 run.py [--limit N] [--dry-run]

Start with Pokémon GO open. Pokémon still named after their species get appraised and renamed by IV%
(see ivc.py), or retagged IVC -> Nope when there's nothing to put in the name. --dry-run does the
reading and appraising but changes nothing: it logs the name each one would get.
Anything the script isn't sure about is skipped and written to runs/<time>/log.txt with a capture.
Anything unexpected stops the run. Screen reading, tapping and timing come from the /pvpc skill.
"""
import json, os, random, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui, pvp
import run as base
from run import Stop, Skip, log, keep_capture, go, wait_for, appraise, think, back_to_list, scroll, front, settle, \
    extras, drag, open_tile, exact_ivs, do_rename
import ivc

base.RUN_DIR = os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S"))
MAX_SKIPS_IN_A_ROW = 5
END_AFTER_STALE = 3
TAG = "IVC"
GM = json.load(open(os.path.join(HERE, "..", "pvpc", "gamemaster.json")))
DONE_LOOK = re.compile(r"\s*(\d|\*|[A-Z]{1,4}\*|xx[sl]\b|\^)", re.I)  # 87/96 A*, FP*, xxs, XXL
odd = set()  # odd tile names already logged
SPECIES_NAMES = {p["speciesName"].split(" (")[0].lower() for p in GM["pokemon"]}


# ---------- what's on the detail screen ----------

def untouched(name):
    """still named after its species, so not done yet. Done names (87/96 A*, FP*, xxs) never match."""
    n = re.sub(r"[.…]+$", "", (name or "").strip().replace("’", "'")).lower()
    return n in SPECIES_NAMES or (len(n) >= 6 and any(s.startswith(n) for s in SPECIES_NAMES))


SCROLL_FROM = re.compile(r"WEIGHT|HEIGHT|STARDUST|CANDY|ENERGY|CAUGHT|HATCHED|THIS POK|BECOME|CAN FUSE|CAN USE")
MOVE_STOPS = ("NEW ATTACK", "CAUGHT", "HATCHED", "RECEIVED", "TRADED", "OBTAINED", "PURIFIED", "RAID", "RESEARCH")


def moves_on(texts):
    """the moves under the GYMS & RAIDS / TRAINER BATTLES tabs, or None if the list isn't all on screen yet"""
    tabs = [t[1] for t in texts if " ".join(ui.norm(t[4]).split()) in ("GYMS RAIDS", "TRAINER BATTLES")]
    if not tabs:
        return None
    top = max(tabs)
    stops = [t[1] for t in texts if t[1] > top and ui.norm(t[4]).startswith(MOVE_STOPS)]
    if not stops and top > 0.6:  # tabs low on the screen, nothing after them: the moves run off the bottom
        return None
    end = min(stops) if stops else 0.92
    moves = [re.sub(r"^[^A-Za-z]+", "", t[4]).strip() for t in texts if top < t[1] < end and t[0] < 0.45]
    return [m for m in moves if m and not ui.norm(m).endswith("BONUS")]  # SHADOW / WEATHER BONUS labels


def label_spot(texts, lo, hi, lowest):
    """the middle of a label between lo and hi (window fractions) that is never a button and isn't near one"""
    spots = [(t[0] + t[2] / 2, t[1] + t[3] / 2) for t in texts if SCROLL_FROM.search(ui.norm(t[4]))]
    spots = sorted((p for p in spots if lo < p[1] < hi and ui.safe(p[0], p[1], texts)), key=lambda p: p[1])
    return (spots[-1] if lowest else spots[0]) if spots else None


def read_moves():
    """scroll the detail screen up to the moves, read them, scroll back. The drag starts on the weight
    (no button there) and the way back starts where the weight ended up, so neither touches a button.
    Kyurem's fusion section pushes the moves farther down: then more drags, each from a label like the
    fusion line or the energy counts (never a button), and the same back down."""
    _, texts, _, bounds = wait_for("detail")
    kg = [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
    if len(kg) != 1:
        raise Skip(f"can't find the weight to scroll from: {[t[4] for t in kg]}")
    fx, fy = kg[0][0] + kg[0][2] / 2, kg[0][1] + kg[0][3] / 2
    ty = fy - random.uniform(0.36, 0.40)
    drag(fx, fy, fx, ty, bounds)
    extra = 0
    try:
        for _ in range(3):
            # look, not wait_for: farther down the HP line is gone, and wait_for would pull the page back up
            _, texts, _, _ = base.look()
            moves = moves_on(texts)
            if moves is not None or extra == 2:
                break
            spot = label_spot(texts, 0.45, 0.88, lowest=True)
            if not spot:
                break
            x, y = spot
            drag(x, y, x, max(y - random.uniform(0.36, 0.40), 0.15), bounds)
            extra += 1
        if moves is None:
            keep_capture("moves")
            raise Skip("moves section not on screen after scrolling")
        if len(moves) < 2:
            keep_capture("moves")
    finally:
        for _ in range(extra + 2 if extra else 0):  # back up to where the first drag left it: the HP line shows
            _, texts, _, _ = base.look()
            if any(re.search(r"\d+\s*/\s*\d+\s*HP", t[4]) for t in texts):
                break
            spot = label_spot(texts, 0.12, 0.55, lowest=False)
            if not spot:
                break
            x, y = spot
            drag(x, y, x, min(y + random.uniform(0.36, 0.40), 0.85), bounds)
        drag(fx, ty, fx, fy, bounds)
    def weight():
        _, texts, _, _ = wait_for("detail")
        return [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
    # the way back can fall short (the page's resting spot shifts a little): nudge it down from the weight
    # until the name and HP sit where the later taps expect them
    home = lambda k: len(k) == 1 and k[0][1] + k[0][3] / 2 > fy - 0.04
    for _ in range(3):
        kg = settle(weight, home, timeout=2)
        if home(kg) or len(kg) != 1 or not 0.1 < kg[0][1] < fy:
            break
        x = kg[0][0] + kg[0][2] / 2
        drag(x, kg[0][1] + kg[0][3] / 2, x, fy + 0.01, bounds)
    else:
        kg = weight()
    _, texts, _, _ = wait_for("detail")
    hp_line = [t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4])]
    if not home(kg) or not hp_line or hp_line[0][1] < 0.3:
        keep_capture("scroll-back")
        raise Stop("detail screen didn't scroll back to where it was")
    if len(moves) < 2:
        raise Skip(f"read fewer than 2 moves: {moves}")
    return moves


def knows(moves, move):
    """move shows in the move list read off the screen"""
    w = " ".join(ui.norm(move).split())
    # the bullet before a move can read as a letter ("O Body Slam"), so a match may have one stray word in front
    return any(g == w or re.fullmatch(r"\S{1,2} " + re.escape(w), g) for g in (" ".join(ui.norm(m).split()) for m in moves))


def elite_on(sp, moves):
    """the species' Elite TM moves that show in its move list"""
    return sorted(m for m in {m for s in sp for m in ivc.elite_moves(s)} if knows(moves, m))


MOVE_NAMES = {m["moveId"]: m["name"] for m in GM["moves"]}


def forms_by_moves(sp, moves):
    """forms with the same name (Kyurem, Black and White Kyurem) told apart by a move only one of them learns.
    No such move read: all of them stay, and CP and HP decide"""
    pool = {s: {MOVE_NAMES.get(m, m) for m in pvp.SPECIES[s]["fastMoves"] + pvp.SPECIES[s]["chargedMoves"]}
            for s in sp}
    own = lambda s: pool[s] - set().union(*(pool[o] for o in sp if o != s))
    return [s for s in sp if any(knows(moves, m) for m in own(s))] or sp


def is_legendary(sp):
    """legendary, mythical or ultra beast anywhere in the family (Cosmog has no tag, Solgaleo does)"""
    tags = {t for s in sp for f in pvp.family(s) for t in pvp.SPECIES[f].get("tags", [])}
    return bool(tags & {"legendary", "mythical", "ultrabeast"})


def pvp_candidate(sp, ivs):
    """the /pvpc test: top 100 stat product in Little, Great or Ultra League for some form in the family"""
    return any(r <= pvp.TOP for s in sp for _, r, _ in pvp.all_ranks(s, tuple(ivs)))


# ---------- IVs ----------

# ---------- changing things ----------

def same_name(got, want):
    """OCR drops or swaps * ^ and spaces, and mixes case (xXS): compare letters, digits and / only"""
    k = lambda s: re.sub(r"[^a-z0-9/]", "", (s or "").lower())
    g, w = k(got), k(want)
    # the text cursor or pencil icon after the name sometimes reads as a trailing l or I ('40 al')
    return g == w or (g[:-1] == w and g[-1:] in ("l", "i"))


def retag(new):
    """untick IVC, tick the new tag (Nope or PvpC). Other tags the user put on (Old, ...) stay"""
    base.set_tags(on=[new], off=[TAG])


# ---------- one Pokémon ----------

def process(i, tile_name, tile_cp, dry):
    open_tile(i)
    info, texts, _ = base.steady_detail()
    cp = info["cp"] or tile_cp
    if not base.opened_right(info, tile_name, tile_cp):
        raise Skip(f"opened {info['name']!r} but tile said {tile_name!r}")
    if not any(ui.norm(t) == TAG for t in info["tags"]):
        raise Skip(f"no {TAG} tag on detail: {info['tags']}")
    sp = ui.species_for(info["name"], info["texts"])
    if not sp:
        raise Skip("species unclear: ?")
    shadow, lucky, size = extras(texts)
    moves = []
    if any(ivc.elite_moves(s) for s in sp):
        seen = read_moves()
        log(f"  moves read: {seen}")
        if len(sp) > 1:
            sp = forms_by_moves(sp, seen)
            log(f"  forms the moves allow: {sp}")
        moves = elite_on(sp, seen)
    base.open_appraisal()
    bars, raws = appraise()
    ivs = exact_ivs(sp, cp, info["hp"], bars, raws)
    legendary = is_legendary(sp)
    gym = any(s in ivc.GYM_DEFENDERS for s in sp)
    name = ivc.make_name(ivs, shadow=shadow, size=size, moves=moves, lucky=lucky, legendary=legendary, gym=gym)
    # IV too low to show but good for PvP: hand it to /pvpc instead (it'll get a Pvp name there)
    if not ivc.shows_iv(ivs, shadow, lucky, legendary, gym) and pvp_candidate(sp, ivs):
        name = "->PvpC"
    flags = [f for f, on in (("shadow", shadow), ("lucky", lucky), ("legendary", legendary), ("gym", gym)) if on]
    what = (f"{tile_name} CP{cp} {'/'.join(map(str, ivs))}{''.join(' ' + f for f in flags)}"
            f"{' ' + size if size else ''}{' ' + ','.join(moves) if moves else ''} -> {name or '->Nope'}")
    think()
    go("dialog", "detail")
    if dry:
        log(f"DRY {what}")
    elif name is None:
        base.nope(TAG, info["tags"], only=False, ivs=ivs, raws=raws)
    elif name == "->PvpC":
        retag("PvpC")
    else:
        do_rename(name, same_name)
    if not dry:
        log(f"DONE {what}")
    go("close", "list")
    return name


# ---------- the list ----------

def pick(ts, passed):
    """first tile still named after its species, passing over ones skipped (or dry-run) earlier"""
    seen = Counter()
    for i, (n, c, _, _) in enumerate(ts, 1):
        if not untouched(n):
            if not DONE_LOOK.match(n) and (n, c) not in odd:
                odd.add((n, c))
                log(f"  passing over {n!r} CP{c}: not a species name or a done name (OCR garble?)")
            continue
        seen[(n, c)] += 1
        if seen[(n, c)] > passed[(n, c)]:
            return i, n, c
    return None


def to_top():
    base.to_top(TAG)


def main(limit, dry):
    front()
    to_top()
    passed, counts = Counter(), Counter()
    skips_in_a_row, stale, seen = 0, 0, set()
    scroll_how = "drag"
    log(f"start{' (dry run)' if dry else ''}, log in {base.RUN_DIR}")
    while counts["done"] + counts["skip"] < limit:
        _, texts, _, bounds = wait_for("list")
        ts = ui.tiles(texts)
        seen.update(t[1] for t in ts)
        p = pick(ts, passed)
        if not p:
            before = [t[:2] for t in ts]
            fresh = False
            for how in ([scroll_how] + [h for h in ("wheel", "drag") if h != scroll_how]):
                scroll(bounds, how)
                _, texts, _, bounds = wait_for("list")
                now = ui.tiles(texts)
                if {t[1] for t in now} - seen:
                    scroll_how, fresh = how, True
                    break
                if [t[:2] for t in now] == before:
                    continue
                break
            stale = 0 if fresh else stale + 1
            if stale >= END_AFTER_STALE:
                log("no new Pokémon after scrolling: end of list")
                counts["end"] = 1
                break
            continue
        i, n, c = p
        log(f"tile {i}: {n} CP{c}")
        try:
            result = process(i, n, c, dry)
            counts["nope" if result is None else "pvpc" if result == "->PvpC" else "renamed"] += 1
            counts["done"] += 1
            if dry:
                passed[(n, c)] += 1
            skips_in_a_row = stale = 0
        except (Skip, base.Lost) as e:
            if isinstance(e, base.Lost):
                base.recover(e, f"{n} CP{c}")
            else:
                keep_capture(f"skip-{n}")
                log(f"SKIP {n} CP{c}: {e}")
            passed[(n, c)] += 1
            counts["skip"] += 1
            skips_in_a_row += 1
            if skips_in_a_row >= MAX_SKIPS_IN_A_ROW:
                raise Stop(f"{skips_in_a_row} skips in a row, something's off")
            back_to_list()
    return counts


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    dry = "--dry-run" in a
    code = 0
    try:
        counts = main(limit, dry)
        counts.pop("end", 0)
        log(f"finished: {dict(counts)}")
    except Stop as e:
        keep_capture("stop")
        log(f"STOPPED: {e}")
        code = 1
    except KeyboardInterrupt:
        log("interrupted")
        code = 130
    except Exception as e:
        keep_capture("crash")
        log(f"CRASHED: {type(e).__name__}: {e}")
        code = 2
    sys.exit(code)
