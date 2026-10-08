#!/usr/bin/env python3
"""PvP stat-product rank helper for the /pvpc skill.

  pvp.py check <species> <cp> <hp> <stars> [--near a/d/h]
        -> every IV/level combo matching CP+HP+stars (-1 = unknown), best ranks, the name, and a VERDICT line.
           --near keeps only combos within 1 of the bar reading on each stat.
  pvp.py rank <species> <atk> <def> <hp>     -> ranks in LC/GL/UL for the species and each evolution
  pvp.py name <species> <atk> <def> <hp>     -> the nickname (or NOPE)
  pvp.py slots <species> "<Pvp name>"         -> the (league, form) ranks a name shows, for the fallen-out check
  pvp.py test                                -> names read back into the slots they came from
  pvp.py update                              -> re-download PvPoke game data
"""
import json, math, os, re, sys, urllib.request
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
GM_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster.json"
JS_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/js/pokemon/Pokemon.js"
MAX_LEVEL = 50
LEAGUES = [("L", 500), ("G", 1500), ("U", 2500)]
STAR_RANGES = {0: (0, 22), 1: (23, 29), 2: (30, 36), 3: (37, 44), 4: (45, 45)}
TOP = 100
NAME_LEN = 12


def update():
    urllib.request.urlretrieve(GM_URL, os.path.join(HERE, "gamemaster.json"))
    urllib.request.urlretrieve(JS_URL, os.path.join(HERE, "Pokemon.js"))


if len(sys.argv) > 1 and sys.argv[1] == "update":
    update()
    print("updated")
    sys.exit()

GM = json.load(open(os.path.join(HERE, "gamemaster.json")))
SPECIES = {p["speciesId"]: p for p in GM["pokemon"]}
CPMS = [float(x) for x in re.search(r"var cpms = \[([^\]]*)\]", open(os.path.join(HERE, "Pokemon.js")).read()).group(1).split(",")]
LEVELS = [1 + i * 0.5 for i in range(int((MAX_LEVEL - 1) * 2) + 1)]


def cpm(level):
    return CPMS[int((level - 1) * 2)]


def cp(base, ivs, level):
    a, d, h = (base["atk"] + ivs[0], base["def"] + ivs[1], base["hp"] + ivs[2])
    m = cpm(level)
    return max(10, math.floor(a * math.sqrt(d) * math.sqrt(h) * m * m / 10))


def hp(base, ivs, level):
    return max(10, math.floor((base["hp"] + ivs[2]) * cpm(level)))


def stat_product(base, ivs, cap):
    best = None
    for lv in LEVELS:
        if cp(base, ivs, lv) <= cap:
            best = lv
        else:
            break
    if best is None:
        return 0, None
    m = cpm(best)
    return (base["atk"] + ivs[0]) * m * (base["def"] + ivs[1]) * m * hp(base, ivs, best), best


@lru_cache(None)
def table(species, cap):
    base = SPECIES[species]["baseStats"]
    rows = [(*stat_product(base, (a, d, h), cap), (a, d, h)) for a in range(16) for d in range(16) for h in range(16)]
    rows.sort(key=lambda r: -r[0])
    return rows


def rank(species, ivs, cap):
    rows = table(species, cap)
    sp = next(r[0] for r in rows if r[2] == ivs)
    return 1 + sum(1 for r in rows if r[0] > sp + 1e-9)  # ties share the better rank


def evolutions(species):
    return [e for e in SPECIES[species].get("family", {}).get("evolutions", []) if e in SPECIES]


def family(species):
    """species plus every evolution reachable from it."""
    out, stack = [], [species]
    while stack:
        s = stack.pop()
        out.append(s)
        stack.extend(evolutions(s))
    return out


def tops(species):
    """final evolutions reachable from species (itself if final)."""
    return [s for s in family(species) if not evolutions(s)]


def lc_eligible(species):
    fam = SPECIES[species].get("family", {})
    return "parent" not in fam and bool(evolutions(species))


def all_ranks(species, ivs):
    """[(league, rank, form)] for every eligible form/league."""
    out = []
    for s in family(species):
        for tag, cap in LEAGUES:
            if tag == "L" and not (s == species and lc_eligible(s)):
                continue
            out.append((tag, rank(s, ivs, cap), s))
    return out


def display(s):
    return SPECIES[s]["speciesName"].split(" (")[0]


def form_letter(form, top):
    a, b = display(form).lower(), display(top).lower()
    for i, ch in enumerate(a):
        if i >= len(b) or ch != b[i]:
            return ch
    return ""


# Eevee branches eight ways, so every form gets its own letter and the name lists every top-100 entry
EEVEE_LETTERS = {"eevee": "N", "vaporeon": "v", "jolteon": "j", "flareon": "f", "espeon": "e",
                 "umbreon": "u", "leafeon": "l", "glaceon": "g", "sylveon": "s"}


def fits(ps, plus):
    """ps = list of league texts; the name with the fewest spaces dropped that fits, or None"""
    suffix = "+" if plus else ""
    for sep, head in ((" ", "Pvp "), ("", "Pvp "), ("", "Pvp")):
        n = head + sep.join(ps) + suffix
        if len(n) <= NAME_LEN:
            return n
    return None


def eevee_name(ranks):
    """every top-100 (league, form), best rank first whatever the league; ties go L, G, U.
    As many as fit, written in league order; if some don't fit, the last one that fit makes way for a +"""
    order = [t for t, _ in LEAGUES]
    hits = sorted(((tag, r, s) for tag, r, s in ranks if r <= TOP), key=lambda x: (x[1], order.index(x[0])))
    text = lambda tag, r, s: f"{tag}{'' if tag == 'L' else EEVEE_LETTERS[s]}{r}"
    if not hits:
        return None, []
    for k in range(len(hits), 0, -1):
        shown = sorted(hits[:k], key=lambda x: (order.index(x[0]), x[1]))
        n = fits([text(*h) for h in shown], k < len(hits))
        if n:
            return n, [f"left out {', '.join(text(*h) for h in hits[k:])}"] if k < len(hits) else []


def make_name(species, ivs):
    """Returns (name or None, notes)."""
    ranks = all_ranks(species, ivs)
    if species == "eevee":
        return eevee_name(ranks)
    notes = []
    best = {}
    for tag, r, s in ranks:
        if tag not in best or r < best[tag][0]:
            best[tag] = (r, s)
    parts = []  # (rank, text)
    for tag, _ in LEAGUES:
        if tag in best and best[tag][0] <= TOP:
            r, s = best[tag]
            letter = ""
            if tag != "L" and evolutions(s):
                t = tops(s)
                if len(t) > 1:
                    notes.append(f"{tag}: {display(s)} branches into {', '.join(map(display, t))}; letter picked vs {display(t[0])}, confirm with user")
                letter = form_letter(s, t[0])
            parts.append((r, f"{tag}{letter}{r}"))
    if not parts:
        return None, notes
    shown = {(tag, best[tag][1]) for tag in best if best[tag][0] <= TOP}
    plus = any(r <= TOP and evolutions(s) and (tag, s) not in shown and tag != "L" for tag, r, s in ranks)
    if plus:
        notes.append("+ because another lower evolution also makes top 100")

    while True:
        n = fits([t for _, t in parts], plus)
        if n:
            return n, notes
        worst = max(parts, key=lambda p: p[0])
        parts.remove(worst)
        notes.append(f"dropped {worst[1]} to fit")
        plus = True


# ---------- owned Pokémon: forms, lines and in-game searches (shared with /ivcsort) ----------

REGIONS = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
NOT_NOPE = "!#Nope"  # Pokémon already Noped keep their names until transferred: never count them
PARENT_FIX = {"raticate": "rattata", "darmanitan_galarian_standard": "darumaka_galarian",  # game data points
              "darmanitan_galarian_zen": "darumaka_galarian"}  # these at the wrong region's pre-evolution


def plain(sid):
    """one entry per real Pokémon: no shadow / mega / primal / XL-only duplicates"""
    return not (sid.endswith(("_shadow", "_xs", "_xl")) or "_mega" in sid or "_primal" in sid)


PLAIN = {s: p for s, p in SPECIES.items() if plain(s)}


def base_name(sid):
    return PLAIN[sid]["speciesName"].split(" (")[0].lower()


def region(sid):
    return next((REGIONS[t] for t in PLAIN[sid].get("tags") or [] if t in REGIONS), None)


def parent(sid):
    par = PARENT_FIX.get(sid) or (PLAIN[sid].get("family") or {}).get("parent")
    return par if par in PLAIN else None


def children(sid):
    return [e for e in (PLAIN[sid].get("family") or {}).get("evolutions") or [] if e in PLAIN]


def search(sid, pool):
    """the in-game search for one species form in one pool. pool: shadow, plain, lucky, dmax, gym"""
    p = PLAIN[sid]
    s = str(p["dex"])
    others = sorted({region(o) for o in PLAIN if PLAIN[o]["dex"] == p["dex"] and region(o)})  # regional forms of this dex
    if pool != "gym" and (region(sid) or others):  # gym defenders: all of that dex number, any form
        s += "&" + (region(sid) or "&".join("!" + r for r in others))
    s += "&" + NOT_NOPE
    return s + {"shadow": "&shadow", "plain": "&!shadow", "lucky": "&lucky", "dmax": "&dynamax,gigantamax",
                "gym": ""}[pool]


def line_searches(line, pool):
    """the searches for a whole evolution line in one pool: dex numbers OR'd with commas ('258,259,260&!#Nope&shadow').
    Species that need a different region filter get their own search."""
    groups = {}
    for s in line:
        d = str(PLAIN[s]["dex"])
        groups.setdefault(search(s, pool)[len(d):], []).append(d)
    return [",".join(dict.fromkeys(ds)) + rest for rest, ds in groups.items()]


# ---------- fallen out: best owned per league and form ----------
# A slot is (league, form): Great League as Charmeleon, Ultra League as Charizard, Little Cup as Charmander.
# Per slot only the best one owned keeps its place (ties keep). One that's beaten in every top-100 slot it has
# has fallen out. A name shows only the best form per league, so the other Pokémon's names can only make them look
# weaker than they are (safe: fewer fall). The one that falls is appraised again first, for all its slots.

def root(sid):
    while parent(sid):
        sid = parent(sid)
    return sid


def tree(sid):
    """every plain species from the line's first stage down, branches included"""
    return [s for s in family(root(sid)) if s in PLAIN]


def letters(first):
    """{form: the letter a Pvp name gives it in G and U} for the tree from first. None for a tree that branches
    (Eevee aside): there the letter was picked by hand against one of the finals, so it can't be read back."""
    t = tree(first)
    if first == "eevee":
        return {s: EEVEE_LETTERS[s] for s in t if s in EEVEE_LETTERS}
    if len([s for s in t if not evolutions(s)]) != 1:
        return None
    return {s: form_letter(s, tops(s)[0]) if evolutions(s) else "" for s in t}


PVP_NAME = re.compile(r"P\S?p ?((?:[LGU][a-zN]?\d{1,3} ?)+)\+?")


def name_slots(name, first):
    """{(league, form): rank} a Pvp name shows, for the tree from first. None if it isn't a clean Pvp name
    (OCR garble, a rank over 100, a letter no form in the tree has). Two forms can share a letter (Charmander and
    Charmeleon are both m): then the form is a tuple of both, and it never matches a real slot."""
    m = PVP_NAME.fullmatch((name or "").strip())
    lets = letters(first)
    if not m or lets is None:
        return None
    out = {}
    for tag, letter, r in re.findall(r"([LGU])([a-zN]?)(\d{1,3})", m.group(1)):
        r = int(r)
        if tag == "L":
            form = first if not letter else None
        else:
            forms = tuple(sorted(f for f, l in lets.items() if l == letter))
            form = forms[0] if len(forms) == 1 else forms or None
        if form is None or not 1 <= r <= TOP or (tag, form) in out:
            return None
        out[(tag, form)] = r
    return out or None


def iv_slots(species, ivs):
    """{(league, form): rank} for every top-100 slot of an appraised Pokémon"""
    out = {}
    for tag, r, s in all_ranks(species, tuple(ivs)):
        if r <= TOP and s in PLAIN:
            out[(tag, s)] = min(r, out.get((tag, s), r))
    return out


def slots_name(first, slots):
    """the Pvp name for {(league, form): rank}, same rules as make_name. Used for a name that only shows the slots
    a Pokémon is still best in. None if slots is empty or the tree branches (Eevee aside)."""
    order = {s: i for i, s in enumerate(family(first))}
    ranks = [(tag, r, s) for (tag, s), r in sorted(slots.items(), key=lambda kv: order.get(kv[0][1], 99))]
    if not ranks or letters(first) is None:
        return None
    if first == "eevee":
        return eevee_name(ranks)[0]
    best = {}
    for tag, r, s in ranks:
        if tag not in best or r < best[tag][0]:
            best[tag] = (r, s)
    parts = [(best[tag][0], f"{tag}{'' if tag == 'L' else letters(first)[best[tag][1]]}{best[tag][0]}")
             for tag, _ in LEAGUES if tag in best]
    plus = any(evolutions(s) and (tag, s) != (tag, best[tag][1]) and tag != "L" for tag, r, s in ranks)
    while True:
        n = fits([t for _, t in parts], plus)
        if n:
            return n
        parts.remove(max(parts, key=lambda p: p[0]))
        plus = True


def kept(mine, others):
    """the slots of mine nobody in others beats (ties keep). A slot whose form can't be told (a tuple) always keeps"""
    return {slot: r for slot, r in mine.items()
            if isinstance(slot[1], tuple) or not any(slot in o and o[slot] < r for _, o in others)}


def plan_pool(members, first, same=lambda a, b: a == b, twins=lambda i, j: False):
    """members: [(name, slots, known)], slots {(league, form): rank}: the real ones if known (appraised), else what
    the name shows. -> one action per member:
      ("keep",)           nothing it shows is beaten
      ("check", why, all) unknown, and something it shows is beaten (all: everything it shows): appraise it
      ("rename", new)     known, still best somewhere, but the name should show different slots
      ("fallen", why)     known, beaten everywhere
    Others' slots all count, also the ones their own names drop: whoever beat those beats the same ones.
    twins(i, j): j may be i read another way (OCR), so it doesn't count against i."""
    out = []
    for i, (name, slots, known) in enumerate(members):
        others = [(n, s) for j, (n, s, _) in enumerate(members) if j != i and not twins(i, j)]
        k = kept(slots, others)
        beaten = [f"{slot_text(sl, r, first)} beaten by "
                  f"{min((o[sl], n) for n, o in others if sl in o)[1]!r}" for sl, r in slots.items() if sl not in k]
        if not known:
            out.append(("check", beaten, len(k) == 0) if beaten else ("keep",))
        elif not k:
            out.append(("fallen", beaten))
        else:
            new = slots_name(first, k)
            out.append(("keep",) if new is None or same(name, new) else ("rename", new))
    return out


def slot_text(slot, r, first):
    tag, form = slot
    forms = form if isinstance(form, tuple) else (form,)
    return f"{tag}{'' if tag == 'L' else (letters(first) or {}).get(forms[0], '?')}{r} ({' or '.join(map(display, forms))})"


def fallen(mine, others, first):
    """mine: {slot: rank}. others: [(name, {slot: rank})] of everything else owned in the pool.
    -> (fallen?, why). Fallen when every slot of mine has someone strictly better."""
    if not mine:
        return False, ["no top-100 slot"]
    why = []
    for slot, r in sorted(mine.items(), key=lambda kv: kv[1]):
        if isinstance(slot[1], tuple):
            return False, [f"{slot_text(slot, r, first)}: can't tell which form"]
        better = sorted((o[slot], n) for n, o in others if slot in o and o[slot] < r)
        if not better:
            return False, [f"best owned for {slot_text(slot, r, first)}"]
        why.append(f"{slot_text(slot, r, first)} beaten by {better[0][1]!r}")
    return True, why


def fmt_ranks(species, ivs):
    return " ".join(f"{t}{r}({display(s)})" for t, r, s in all_ranks(species, ivs) if r <= 500)


def cmd_check(species, cpv, hpv, stars, near=None):
    """stars -1 = any. near = (a, d, h) from the bars: keep combos within 1 of it on every stat."""
    base = SPECIES[species]["baseStats"]
    lo, hi = STAR_RANGES.get(stars, (0, 45))
    rows = []
    for lv in LEVELS:
        for a in range(16):
            for d in range(16):
                for h in range(16):
                    if near and max(abs(x - y) for x, y in zip((a, d, h), near)) > 1:
                        continue
                    if lo <= a + d + h <= hi and cp(base, (a, d, h), lv) == cpv and hp(base, (a, d, h), lv) == hpv:
                        n, notes = make_name(species, (a, d, h))
                        exact = near == (a, d, h)
                        rows.append((n or "NOPE", exact))
                        print(f"L{lv:<5} {a:>2}/{d:>2}/{h:>2}{' *' if exact else '  '} {n or 'NOPE':<13} {fmt_ranks(species, (a, d, h))}  {'; '.join(notes)}")
    outcomes = sorted({r[0] for r in rows})
    exact = [r[0] for r in rows if r[1]]
    if not rows:
        print("VERDICT: NO MATCH (misread CP, HP, stars, bars or species)")
    elif len(outcomes) == 1:
        print(f"VERDICT: {outcomes[0]} (every candidate agrees)")
    elif len(exact) == 1:
        print(f"VERDICT: {exact[0]} (bar reading * picks it; neighbours differ: {outcomes})")
    else:
        print(f"VERDICT: NEED BARS (outcomes differ: {outcomes})")


def cascade(first, owned):
    """plays plan_pool to the end like act-fallen does: owned = {name: its real slots}. Checks get appraised,
    renames get done, again until nothing changes. -> {first name: final name or 'fallen'}"""
    names, known, gone = {n: n for n in owned}, set(), set()
    for _ in range(10):
        live = [n for n in owned if n not in gone]
        acts = plan_pool([(names[n], owned[n] if n in known else name_slots(names[n], first), n in known)
                          for n in live], first)
        if all(a[0] == "keep" for a in acts):
            break
        for n, a in zip(live, acts):
            if a[0] == "check":
                known.add(n)
            elif a[0] == "rename":
                names[n] = a[1]
            elif a[0] == "fallen":
                names[n] = "fallen"
    return names


# magnemite line: magneton is t, magnemite m
MT = lambda **kw: {({"L": ("L", "magnemite"), "Gt": ("G", "magneton"), "Gm": ("G", "magnemite"),
                     "U": ("U", "magnezone")}[k]): r for k, r in kw.items()}
CASCADES = [
    # the new Gt3 beats A's Gt17. A's name had no room for U99; now it does, and U99 beats B's U100.
    # B's Gt50 was beaten by the new one already, so B has nothing left.
    ("magnemite", {"PvpL15Gt17+": MT(L=15, Gt=17, U=99), "Pvp Gt50 U100": MT(Gt=50, U=100), "Pvp Gt3": MT(Gt=3)},
     {"PvpL15Gt17+": "Pvp L15 U99", "Pvp Gt50 U100": "fallen", "Pvp Gt3": "Pvp Gt3"}),
    # nobody beats anybody: nothing changes
    ("magnemite", {"Pvp L4": MT(L=4), "Pvp Gt9": MT(Gt=9), "Pvp U2": MT(U=2)},
     {"Pvp L4": "Pvp L4", "Pvp Gt9": "Pvp Gt9", "Pvp U2": "Pvp U2"}),
    # the new one is beaten in G by an older one: the new one gets trimmed too. Ties keep.
    ("magnemite", {"Pvp Gt5 U40": MT(Gt=5, U=40), "Pvp Gt3": MT(Gt=3), "Pvp U40": MT(U=40)},
     {"Pvp Gt5 U40": "Pvp U40", "Pvp Gt3": "Pvp Gt3", "Pvp U40": "Pvp U40"}),
]


def test():
    """every name make_name gives must read back (name_slots) as the ranks it was made from"""
    import random
    rnd, bad, n = random.Random(1), 0, 0
    for sp in ("charmander", "charmeleon", "magnemite", "eevee", "vulpix_alolan", "rattata", "rattata_alolan",
               "bulbasaur", "azurill", "marill", "dratini", "oddish", "medicham", "registeel"):
        for _ in range(150):
            ivs = tuple(rnd.randint(0, 15) for _ in range(3))
            name, _ = make_name(sp, ivs)
            if not name:
                continue
            got, full = name_slots(name, root(sp)), iv_slots(sp, ivs)
            if letters(root(sp)) is None:
                ok = got is None
            else:  # a shared letter (Charmander/Charmeleon m) must hold the rank of one of its forms
                ok = got is not None and all(any(full.get((k[0], f)) == r for f in k[1]) if isinstance(k[1], tuple)
                                             else full.get(k) == r for k, r in got.items())
            n += 1
            if not ok:
                bad += 1
                print(f"BAD {sp} {ivs} {name!r}: read {got}, ranks {full}")
            if letters(root(sp)) is not None and slots_name(root(sp), iv_slots(sp, ivs)) != name:
                bad += 1
                print(f"BAD {sp} {ivs}: make_name {name!r}, slots_name {slots_name(root(sp), iv_slots(sp, ivs))!r}")
    checks = [(name_slots("Pvp G9", "rattata"), {("G", "raticate"): 9}),
              (name_slots("Pvp L5Gm15U35", "charmander"), {("L", "charmander"): 5, ("G", ("charmander", "charmeleon")): 15,
                                                           ("U", "charizard"): 35}),
              (name_slots("Pvp Gt15", "magnemite"), {("G", "magneton"): 15}),
              (fallen({("G", ("charmander", "charmeleon")): 5}, [("Pvp G1", {("G", ("charmander", "charmeleon")): 1})],
                      "charmander")[0], False),
              (name_slots("Pvp G150", "charmander"), None), (name_slots("Pvp Gq5", "charmander"), None),
              (name_slots("Pvp G5", "oddish"), None), (name_slots("PvpGN45Uu28+", "eevee"),
                                                       {("G", "eevee"): 45, ("U", "umbreon"): 28}),
              (fallen({("G", "charizard"): 5}, [("Pvp G5", {("G", "charizard"): 5})], "charmander")[0], False),
              (fallen({("G", "charizard"): 5}, [("Pvp G4", {("G", "charizard"): 4})], "charmander")[0], True),
              (fallen({("G", "charizard"): 5, ("U", "charizard"): 2}, [("Pvp G4", {("G", "charizard"): 4})],
                      "charmander")[0], False)]
    checks += [(cascade(*c[:2]), c[2]) for c in CASCADES]
    for i, (got, want) in enumerate(checks):
        if got != want:
            bad += 1
            print(f"BAD check {i}: {got!r}, wanted {want!r}")
    print(f"{n} names read back, {len(checks)} checks, {bad} bad")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        test()
    cmd, sp = sys.argv[1], sys.argv[2]
    if sp not in SPECIES:
        sys.exit(f"unknown species {sp!r}; close matches: {[s for s in SPECIES if sp.split('_')[0] in s][:10]}")
    near = None
    if "--near" in sys.argv:
        i = sys.argv.index("--near")
        near = tuple(int(x) for x in sys.argv[i + 1].split("/"))
        del sys.argv[i:i + 2]
    if cmd == "slots":
        print(name_slots(sys.argv[3], root(sp)))
        sys.exit()
    nums = [int(x) for x in sys.argv[3:]]
    if cmd == "check":
        cmd_check(sp, *nums, near=near)
    elif cmd == "rank":
        for s in family(sp):
            print(display(s), [(t, r) for t, r, f in all_ranks(sp, tuple(nums)) if f == s])
    elif cmd == "name":
        n, notes = make_name(sp, tuple(nums))
        print(n or "NOPE", *notes, sep="\n  ")
