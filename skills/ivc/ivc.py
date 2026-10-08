#!/usr/bin/env python3
"""IV% nickname maker for the /ivc skill.

  ivc.py name <a/d/h> [--shadow] [--lucky] [--legendary] [--gym] [--size XXL|XXS] [--move "Frenzy Plant" ...]  -> the nickname (or NOPE)
  ivc.py elite <species>                                                     -> its Elite TM moves
  ivc.py test                                                                -> run the examples

Name = IV%, then /purified IV% (shadow, 84+), then H A D for each stat at 15 (or the lowercase
leader(s) if none is 15), then Elite TM move initials + *, then XXL / xxs. Anything not shadow, lucky or
legendary/mythical/ultra beast/gym defender under 93% gets only the move and size parts, and NOPE if there are none. Max 12 characters. To fit: drop spaces from the right, then size -> ^,
then initials -> * on the stat letters, then the space after the IV.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GM_PATH = os.path.join(HERE, "..", "pvpc", "gamemaster.json")
NAME_LEN = 12
SHOW_FROM = 93  # below this IV% (rounded) only shadows, luckies and legendaries show IV and stat letters
PURIFY_FROM = 84  # shadow IV% (rounded) at which the purified IV% is shown
STAT_COMBOS = {"H", "A", "D", "HA", "HD", "AD", "HAD"}  # move initials that would read as stat letters
# gym defenders always show their IV, so /ivcsort can rank them (top 5/6 IV or top 20 CP). User's Pokebattler top 6.
GYM_DEFENDERS = {"blissey", "chansey", "snorlax", "slaking", "wobbuffet", "dondozo"}


def pct(ivs):
    # sum/45 never lands on .5, so plain round() is exact
    return round(sum(ivs) * 100 / 45)


def purified(ivs):
    return tuple(min(15, v + 2) for v in ivs)


def stat_letters(ivs):
    """capitals for every 15; if none, the lowercase leader(s); nothing when all three tie (or 100%)"""
    a, d, h = ivs
    order = (("H", h), ("A", a), ("D", d))
    caps = "".join(l for l, v in order if v == 15)
    if caps:
        return "" if caps == "HAD" else caps
    leads = "".join(l.lower() for l, v in order if v == max(ivs))
    return "" if len(leads) == 3 else leads


def initials(move):
    move = re.sub(r"\s*\(.*\)", "", move)  # Weather Ball (Fire) -> Weather Ball
    return "".join(w[0].upper() for w in re.split(r"[\s_-]+", move) if w)


def shows_iv(ivs, shadow=False, lucky=False, legendary=False, gym=False):
    return shadow or lucky or legendary or gym or pct(ivs) >= SHOW_FROM


def candidates(ivs, shadow=False, size=None, moves=(), lucky=False, legendary=False, gym=False):
    """every form of the name, best first"""
    p = pct(ivs)
    show = shows_iv(ivs, shadow, lucky, legendary, gym)
    iv = str(p) if show else ""
    if show and shadow and PURIFY_FROM <= p < 100:
        iv += f"/{pct(purified(ivs))}"
    stats = stat_letters(ivs) if show else ""
    ini = "".join(initials(m) for m in moves)
    if ini in STAT_COMBOS:
        ini = ""
    size = {"XXL": "XXL", "XXS": "xxs"}.get((size or "").upper(), "")

    def forms(ini, size, caret, close_iv=False):
        """spacings for one set of parts: all spaces, then drop them from the right.
        The space after the IV only goes when close_iv is set."""
        if moves and not ini:  # bare * sticks to the stat letters (or the IV if there are none)
            parts = [iv, stats + "*"] if stats else [iv + "*"]
        else:
            parts = [iv, stats, ini + "*" if ini else ""]
        parts = [x for x in parts + [size] if x]
        if not parts:
            return []
        out = []
        last = len(parts) if close_iv or not iv else len(parts) - 1
        for joined in range(max(last, 1)):  # how many gaps from the right are closed
            s = parts[0]
            for i, part in enumerate(parts[1:], 1):
                s += ("" if i >= len(parts) - joined else " ") + part
            out.append(s + caret)
        return out

    caret = "^" if size else ""
    out = (forms(ini, size, "") if size else []) + forms(ini, "", caret) + forms("", "", caret, close_iv=True)
    seen = []
    for s in out:
        if s not in seen:
            seen.append(s)
    return seen


def make_name(ivs, shadow=False, size=None, moves=(), lucky=False, legendary=False, gym=False):
    """the nickname, or None when there's nothing to say (-> Nope tag)"""
    cands = candidates(ivs, shadow, size, moves, lucky, legendary, gym)
    if not cands:
        return None
    for s in cands:
        if len(s) <= NAME_LEN:
            return s
    raise ValueError(f"nothing fits: {cands}")


def elite_moves(species):
    gm = json.load(open(GM_PATH))
    by_id = {p["speciesId"]: p for p in gm["pokemon"]}
    names = {m["moveId"]: m["name"] for m in gm["moves"]}
    p = by_id.get(species) or by_id.get(re.sub(r"_shadow$", "", species))
    return [names.get(m, m) for m in (p or {}).get("eliteMoves") or []]


EXAMPLES = [  # (a, d, h), shadow, size, moves, name
    ((15, 15, 15), False, None, [], "100"),
    ((15, 14, 14), False, None, [], "96 A"),
    ((10, 15, 15), False, None, [], None),
    ((15, 10, 15), False, None, ["Frenzy Plant"], "FP*"),
    ((15, 12, 12), True, "XXL", ["Aeroblast"], "87/96 A* XXL"),
    ((13, 13, 13), True, None, ["Synchronoise"], "87/100 S*"),
    ((15, 10, 10), True, None, ["Synchronoise"], "78 A S*"),
    ((13, 13, 13), True, "XXL", ["Synchronoise"], "87/100 S*XXL"),
    ((14, 13, 13), True, "XXL", ["Synchronoise"], "89/100 a S*^"),
    ((15, 15, 15), True, None, [], "100"),
    ((12, 13, 13), True, None, [], "84/98 hd"),
    ((12, 12, 13), True, None, [], "82 h"),
    ((15, 14, 15), False, "XXS", ["Hydro Cannon"], "98 HA HC*xxs"),
    ((15, 14, 15), True, "XXL", ["Hydro Cannon"], "98/100 HA*^"),
    ((15, 13, 15), True, "XXL", ["Hydro Cannon"], "96/100 HA*^"),
    ((10, 10, 10), False, None, ["Draco Meteor"], "DM*"),
    ((10, 10, 10), False, None, ["Aeroblast"], "*"),
    ((10, 10, 10), True, None, ["Aeroblast"], "67*"),
    ((8, 13, 9), True, None, [], "67 d"),
    ((12, 12, 9), True, None, [], "73 ad"),
    ((9, 12, 12), True, None, [], "73 hd"),
    ((12, 12, 9), False, None, [], None),
    ((12, 12, 9), False, "XXS", [], "xxs"),
    ((12, 12, 9), False, "XXL", ["Frenzy Plant"], "FP* XXL"),
    ((14, 14, 14), False, None, [], "93"),
    ((14, 13, 15), False, None, [], "93 H"),
    ((14, 14, 13), False, None, [], None),
    ((12, 15, 11), False, None, [], "84 D", "legendary"),
    ((12, 15, 14), False, None, [], "91 D", "lucky"),
    ((2, 10, 14), False, None, [], "58 h", "gym"),
    ((12, 12, 9), False, "XXL", [], "73 ad XXL", "gym"),
]


def test():
    bad = 0
    for ivs, shadow, size, moves, want, *flag in EXAMPLES:
        got = make_name(ivs, shadow, size, moves, lucky="lucky" in flag, legendary="legendary" in flag,
                        gym="gym" in flag)
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {'/'.join(map(str, ivs)):9} {'shadow ' if shadow else ''.join(flag)[:6]:7}{size or '':4} "
              f"{','.join(moves):13} -> {got or 'NOPE'!r}" + ("" if ok else f"  wanted {want!r}"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "test":
        test()
    elif a[0] == "elite":
        print(elite_moves(a[1]))
    elif a[0] == "name":
        ivs = tuple(int(x) for x in a[1].split("/"))
        size = a[a.index("--size") + 1] if "--size" in a else None
        moves = [a[i + 1] for i, x in enumerate(a) if x == "--move"]
        print(make_name(ivs, "--shadow" in a, size, moves, "--lucky" in a, "--legendary" in a, "--gym" in a) or "NOPE")
    else:
        sys.exit(__doc__)
