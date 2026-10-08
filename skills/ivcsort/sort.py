#!/usr/bin/env python3
"""Rules for /ivcsort: which IVC Pokémon to keep (favorite + untag) and which to Nope.

  sort.py name <nickname>            -> what the script reads from a nickname (IV sum, purified, size, ...)
  sort.py lines <species_id>         -> its family: lines, spots and the searches each pool uses
  sort.py megas                      -> every species line counted as mega-capable
  sort.py test                       -> run the rule examples

A Pokémon's IV comes from its /ivc nickname (first number = IV%, which gives the exact IV sum).
Pools are everything the user owns in the line, found with in-game searches by dex number, minus Nope-tagged.
Spots: each final evolution of the family has spots per pool. Fill them best IV first, each Pokémon in one spot
only. One that could become two finals (Eevee, Kirlia) takes whichever has room, so it never counts twice.
Gender decides what it can become (only males make Gallade, only females Froslass; a male Combee makes nothing).
Keep if ANY of these passes (ties with the last place keep):
  shadow      a shadow spot: top 5 per final (shadows can't mega)
  not shadow  a non-shadow spot: top N per final (normal, lucky, purified, Dynamax all together)
  purified    a shadow with no shadow spot, whose purified IV (84/96 -> 96) gets a non-shadow spot
  lucky       a lucky spot: 1 per final
  Dynamax     a Dynamax/Gigantamax spot: 3 per final
  gym         top 20 CP among all of that species (GYM_DEFENDERS)
N = 6 if any species in that final's line can mega evolve (released in GO or not), else 5.
Always keep: 98% or 100% (a shadow's own IV, or its purified IV). Armored Mewtwo (no search can split it out).
Weak lines (no species, mega or shadow form of the line reaches STRONG_AT% on DialgaDex for any type):
  1 spot per final (ties keep); lucky/Dynamax extras still apply; an Elite TM name (*) keeps.
  Never weak: gym defenders, COLLECT, legendary/mythical/Ultra Beast, unrated megas, species not on DialgaDex.
  meta-overrides.txt can mark a species strong or weak by hand.
COLLECT lines (Vivillon patterns): a NOPE becomes LEAVE so the user picks.
Fails: XXL/xxs in the name -> leave for the user. Otherwise -> Nope. No IV and no size (FP*, *) -> Nope.
"""
import json, os, re, sys
from collections import Counter, namedtuple
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.insert(0, os.path.join(HERE, "..", "ivc"))
import pvp
from pvp import REGIONS, NOT_NOPE, base_name, region, parent, children, search
from ui import tile_name as clean_name
from ivc import GYM_DEFENDERS

TOP, TOP_MEGA, TOP_LUCKY, TOP_DMAX, TOP_GYM_CP = 5, 6, 1, 3, 20
ALWAYS = 44  # IV sum of 98%: 98% and 100% always keep
STRONG_AT = 90  # DialgaDex % (vs its budget pick for the type) a line needs somewhere to keep top 5/6
WEAK_EXTRAS = True  # weak lines: also keep the best lucky / top 3 Dynamax (user: yes, as before)
COLLECT = {"scatterbug", "spewpa", "vivillon"}  # pattern collections: the user picks by hand
OWN_FORM = {"mewtwo_armored"}  # a form the searches can't split from the rest of its dex number

# Megas not in PvPoke's game data yet (Legends: Z-A + Mega Dimension, checked 2026-10-07 on game8 and
# hundo-hunter). The game data's own *_mega / *_primal entries are added on top.
MEGA_EXTRA = """meganium typhlosion feraligatr emboar clefable starmie skarmory chesnaught delphox greninja hawlucha
dragalge barbaracle pyroar scolipede excadrill chandelure eelektross scrafty froslass drampa zygarde floette
raichu chimecho absol staraptor garchomp lucario golurk meowstic crabominable golisopod magearna scovillain
glimmora tatsugiri baxcalibur heatran darkrai zeraora""".split()

NO_REGION = "&".join("!" + r for r in REGIONS.values())

GM = pvp.GM
BY_ID = {p["speciesId"]: p for p in GM["pokemon"]}
SPECIES = pvp.PLAIN


# ---------- nicknames ----------

Name = namedtuple("Name", "iv purified size pvp")  # IV sums (0-45) or None


def iv_sum(p):
    s = round(p * 45 / 100)
    return s if 0 <= s <= 45 and round(s * 100 / 45) == p else None


def parse_name(name):
    """what a nickname says. IV-less names (FP*, xxs) give iv=None. Pvp names and species names count as nothing."""
    n = clean_name(name)
    pvpname = bool(re.match(r"P\S?p(?=[ LGU+]|$)", n))
    size = bool(re.search(r"xx[sl]|\^", n, re.I))
    m = re.match(r"(\d{1,3})(?:\s*/\s*(\d{1,3}))?", n)
    iv = iv_sum(int(m.group(1))) if m else None
    pur = iv_sum(int(m.group(2))) if m and m.group(2) else None
    return Name(iv, pur, size, pvpname)


def value(name, shadow):
    """the IV sum that ranks: a shadow's own IV; a purified one (name like 87/96, not shadow any more) uses the 2nd"""
    p = parse_name(name)
    if p.iv is None:
        return None
    return p.iv if shadow or p.purified is None else p.purified


# ---------- lines ----------

# a final that only one gender can become (or a form only one gender has). The game data doesn't say.
GENDER = {"gallade": "male", "froslass": "female", "vespiquen": "female", "salazzle": "female",
          "wormadam_plant": "female", "wormadam_sandy": "female", "wormadam_trash": "female", "mothim": "male",
          "meowstic": "male", "meowstic_female": "female", "oinkologne": "male", "oinkologne_female": "female",
          "basculegion_male": "male", "basculegion_female": "female",
          "indeedee_male": "male", "indeedee_female": "female"}
CHILD_FIX = {"espurr": ["meowstic", "meowstic_female"],  # game data lists the male form twice
             "lechonk": ["oinkologne", "oinkologne_female"]}
POOLS = ("plain", "shadow", "lucky", "dmax")


def kids(sid):
    return list(dict.fromkeys(k for k in CHILD_FIX.get(sid) or children(sid) if k in SPECIES))


def lines_of(sid):
    """every evolution path (first stage -> a final) through this species. Branches are separate lines,
    pre-evolutions count toward each; regional forms are their own species ids so they split naturally."""
    up = [sid]
    while parent(up[0]):
        up.insert(0, parent(up[0]))

    def down(s):
        ks = kids(s)
        return [[s]] if not ks else [[s] + rest for k in ks for rest in down(k)]

    return [tuple(up[:-1] + path) for path in down(sid)]


@lru_cache(None)
def family(sid):
    """every line that shares a Pokémon with this species' lines (Gallade -> the Gallade and Gardevoir lines)"""
    out, todo = [], list(lines_of(sid))
    while todo:
        line = todo.pop(0)
        if line not in out:
            out.append(line)
            todo += [l for s in line for l in lines_of(s)]
    return tuple(out)


def finals(sid):
    ks = kids(sid)
    return [sid] if not ks else list(dict.fromkeys(f for k in ks for f in finals(k)))


def gender_term(sid):
    """'male'/'female' when the search must split this species from another form with the same dex number"""
    g = GENDER.get(sid)
    if g and any(SPECIES[o]["dex"] == SPECIES[sid]["dex"] and GENDER.get(o) != g for o in SPECIES if o != sid):
        return g
    return None


def with_gender(q, g):
    return q.replace("&" + NOT_NOPE, f"&{g}&{NOT_NOPE}", 1) if g else q


def slot(f):
    """a final's id. Forms no search can split (Wormadam cloaks, Urshifu styles) share one."""
    return with_gender(search(f, "plain"), gender_term(f))


def reach(sid, g):
    """the finals this species can still become, for gender g (None: either)"""
    if not kids(sid):
        return frozenset([slot(sid)])
    return frozenset(slot(f) for f in finals(sid) if g is None or GENDER.get(f) in (None, g))


def genders(sid):
    """[None], or ['male', 'female'] when the two genders can become different things (Kirlia, Snorunt, Combee)"""
    return ["male", "female"] if reach(sid, "male") != reach(sid, "female") else [None]


@lru_cache(None)
def groups(sid, pool):
    """the searches for this species' whole family in one pool -> ((search, finals it can become, species), ...).
    Pokémon in one search can all become the same finals, so a search never mixes Eevee with Vaporeon,
    or a male Kirlia with a female one."""
    out = {}
    for line in family(sid):
        for s in line:
            for g in genders(s):
                d = str(SPECIES[s]["dex"])
                q = with_gender(search(s, pool), g or gender_term(s))
                key = (q[len(d):], reach(s, g))
                if s not in out.setdefault(key, []):
                    out[key].append(s)
    return tuple((",".join(dict.fromkeys(str(SPECIES[s]["dex"]) for s in ss)) + rest, r, tuple(ss))
                 for (rest, r), ss in out.items())


MEGA = {s for s in BY_ID if "_mega" in s or "_primal" in s}
MEGA_BASES = {BY_ID[s]["speciesName"].split(" (")[0].lower() for s in MEGA} | set(MEGA_EXTRA)


def can_mega(sid):
    return base_name(sid) in MEGA_BASES and region(sid) is None  # Mega Raichu is Kanto Raichu, not Alolan


def top_n(line):
    return TOP_MEGA if any(can_mega(s) for s in line) else TOP


# ---------- strong lines (DialgaDex) ----------

DGX_FORMS = {"Alola": "alola", "Galarian": "galar", "Hisuian": "hisui", "Paldea": "paldea"}


def load_meta():
    """(dex, region) -> (best %, what) over every type list, megas and shadows included; and the hand overrides"""
    best = {}
    with open(os.path.join(HERE, "dialgadex-20261007.json")) as f:
        for t, rows in json.load(f).items():
            for e in rows:
                reg = next((v for k, v in DGX_FORMS.items() if e["form"].startswith(k)), None)
                k = (e["id"], reg)
                if e["cls"]:  # legendary, mythical, Ultra Beast
                    best.setdefault(("legend", e["id"]), True)
                if e["form"].startswith("Mega"):
                    best.setdefault(("mega", e["id"]), True)
                if e["pct"] > best.get(k, (0,))[0]:
                    best[k] = (e["pct"], f"{'Shadow ' if e['shadow'] else ''}{e['name']} {t} {e['pct']}%")
    over = {}
    path = os.path.join(HERE, "meta-overrides.txt")
    if os.path.exists(path):
        for row in open(path):
            w = row.split("#")[0].split()
            if len(w) == 2 and w[0] in ("strong", "weak"):
                over[w[1]] = w[0] == "strong"
    return best, over


META, META_OVER = load_meta()


def meta_score(sid):
    """DialgaDex best for one species, or None if it isn't there"""
    return META.get((SPECIES[sid]["dex"], region(sid)))


def strong(line):
    """-> (strong?, why). Not found on DialgaDex counts as strong: a missing match must never Nope things."""
    for s in line:
        if s in META_OVER:
            return META_OVER[s], f"{s} marked {'strong' if META_OVER[s] else 'weak'} by hand"
    for s in line:
        if s in GYM_DEFENDERS:
            return True, f"{s} is a gym defender"
        if any(s.startswith(c) for c in COLLECT):
            return True, "pattern collection"
        if ("legend", SPECIES[s]["dex"]) in META:
            return True, f"{s} is legendary/mythical/Ultra Beast"
        if meta_score(s) is None:
            return True, f"{s} not on DialgaDex"
        if can_mega(s) and not any(("mega", SPECIES[x]["dex"]) in META for x in line):
            return True, f"Mega {base_name(s).title()} not rated on DialgaDex yet"
    best = max(meta_score(s) for s in line)
    return best[0] >= STRONG_AT, best[1]


# ---------- which species it is ----------

def identify(candy, type_words, cp, hp, iv):
    """renamed Pokémon: candidates from the candy's family, then the type line, then which ones CP and HP fit
    with that IV sum. -> list of species ids (one if sure)."""
    candy = (candy or "").strip().lower()
    fam = lambda s: (SPECIES[s].get("family") or {}).get("id") or "solo " + base_name(s)  # legendaries: no family
    fams = {fam(s) for s in SPECIES if base_name(s) == candy}
    cands = [s for s in SPECIES if fam(s) in fams]
    typed = [s for s in cands if all(t.upper() in type_words for t in SPECIES[s]["types"] if t != "none")]
    if typed:
        most = max(sum(t.upper() in type_words for t in SPECIES[s]["types"]) for s in typed)
        cands = [s for s in typed if sum(t.upper() in type_words for t in SPECIES[s]["types"]) == most]
    if iv is None:
        return cands
    fit = []
    for s in cands:
        b = SPECIES[s]["baseStats"]
        if any(pvp.cp(b, (a, d, iv - a - d), lv) == cp and pvp.hp(b, (a, d, iv - a - d), lv) == hp
               for lv in pvp.LEVELS for a in range(16) for d in range(16) if 0 <= iv - a - d <= 15):
            fit.append(s)
    if len(fit) > 1:  # forms with the same stats (Oricorio, costumes) share a dex number: any will do
        if len({(SPECIES[s]["dex"], region(s)) for s in fit}) == 1:
            fit = fit[:1]
    return fit


# ---------- the decision ----------

def beaten(mine, others, n):
    """keep when fewer than n others are strictly better (so a tie with last place keeps)"""
    better = sorted((o for o in others if o[0] > mine), reverse=True)
    return len(better) < n, better


def pool_values(entries, shadow):
    """(value, name, cp) for every tile in a search that has an IV name.
    One tile read two ways while scrolling ('98 HD MM*X' and '98 HDMM*X', same CP) is one Pokémon:
    keep the spelling seen most. The exact same name twice is two tiles seen side by side."""
    counts = Counter(map(tuple, entries))
    best = {}
    for (name, cp), k in counts.items():
        key = (re.sub(r"[^a-z0-9]", "", name.lower()), cp)
        if cp and (key not in best or k > counts[best[key]]):
            best[key] = (name, cp)
    entries = [e for e in map(tuple, entries) if not e[1] or best[(re.sub(r"[^a-z0-9]", "", e[0].lower()), e[1])] == e]
    out = []
    for name, cp in entries:
        v = value(name, shadow)
        if v is not None and not parse_name(name).pvp:
            out.append((v, name, cp))
    return out


def without_me(vals, mine, cp):
    """the member shows up in its own pool: take one matching tile out (same value and CP)"""
    vals = list(vals)
    for i, (v, _, c) in enumerate(vals):
        if v == mine and c == cp:
            return vals[:i] + vals[i + 1:], True
    for i, (v, _, c) in enumerate(vals):  # a top-row tile whose CP was hidden reads as CP 0
        if v == mine and c == 0:
            return vals[:i] + vals[i + 1:], True
    return vals, False


def pct(v):
    return f"{round(v * 100 / 45)}%"


def spots(sid, pool):
    """final -> (how many of them to keep, its name, weak-line note) for this species' family"""
    out = {}
    for line in family(sid):
        f = line[-1]
        big, meta = strong(line)
        n = {"plain": top_n(line) if big else 1, "shadow": TOP if big else 1,  # shadows can't mega: top 5
             "lucky": TOP_LUCKY if big or WEAK_EXTRAS else 0, "dmax": TOP_DMAX if big or WEAK_EXTRAS else 0}[pool]
        name = base_name(f).title() + (f" ({region(f)})" if region(f) else "") + \
            (f" {GENDER[f]}" if gender_term(f) else "")
        old = out.get(slot(f))
        if not old or n > old[0]:
            out[slot(f)] = (n, name, "" if big else f" (weak line, best: {meta})")
    return out


def fill(order, caps):
    """order: finals each Pokémon can become, best first. Each takes a spot if everyone placed so far can still
    be fitted (one that can become two finals moves to make room). -> (placed?, final -> indexes in its spots)"""
    held = {k: [] for k in caps}

    def place(i, seen):
        for k in order[i]:
            if k in seen or not caps.get(k):
                continue
            seen.add(k)
            if len(held[k]) < caps[k]:
                held[k].append(i)
                return True
            for j in list(held[k]):
                if place(j, seen):
                    held[k].remove(j)
                    held[k].append(i)
                    return True
        return False

    return [place(i, set()) for i in range(len(order))], held


def fits(others, caps, mine, my_reach):
    """others: (value, finals it can become, tile). Fill each final's spots best first, each Pokémon in one spot
    only; one that can become two finals goes wherever there's room (spare males fill Gardevoir spots).
    Ties with me go after me. -> (did I get a spot, final I got or None, final -> tiles in its spots)"""
    ahead = sorted((o for o in others if o[0] > mine), key=lambda o: -o[0])
    tiles = [(v, t) for v, _, t in ahead] + [(mine, None)]
    ok, held = fill([r for _, r, _ in ahead] + [my_reach], caps)
    me = len(tiles) - 1
    got = next((k for k, ii in held.items() if me in ii), None)
    return ok[me], got, {k: sorted((tiles[i] for i in ii if tiles[i][1]), key=lambda x: -x[0]) for k, ii in held.items()}


def spotless_shadows(sid, results, me):
    """the family's other shadows that get no shadow spot, at their purified IV (84/96 -> 96): they could be
    purified too, so a shadow kept for its purified IV competes with them"""
    items, _ = pool_items(sid, "shadow", results, True, me)
    items.sort(key=lambda o: -o[0])
    caps = {k: c[0] for k, c in spots(sid, "shadow").items()}
    ok, _ = fill([r for _, r, _ in items], caps)
    return [(parse_name(t[0]).purified, r, t) for (v, r, t), got in zip(items, ok)
            if not got and parse_name(t[0]).purified is not None]


def pool_items(sid, pool, results, shadow, me=None):
    """every tile in the family's searches for one pool as (value, finals, (name, cp)).
    me = (value, cp): take my own tile out (from the first search of my species that has it). -> (items, found)"""
    items, found = [], me is None
    for q, r, ss in groups(sid, pool):
        vals = pool_values(results[q], shadow)
        if not found and sid in ss:
            vals, found = without_me(vals, *me)
        items += [(v, r, (n, c)) for v, n, c in vals]
    return items, found


def my_reach(m, mine, results, pool):
    """the finals this member can become. A gender split shows in which search its tile turns up;
    not found in one of them: either (the safe side, it keeps more)."""
    sid = m["species"]
    gs = [(q, r) for q, r, ss in groups(sid, pool) if sid in ss]
    if len(gs) > 1:
        seen = [r for q, r in gs if without_me(pool_values(results[q], m["shadow"]), mine, m["cp"])[1]]
        if len(seen) == 1:
            return seen[0]
    return frozenset().union(*(r for _, r in gs))


def judge_pool(m, results, pool, what, mine, r, me_in_pool=True, extra=()):
    """-> (keep?, reason, notes)"""
    sid = m["species"]
    caps = spots(sid, pool)
    shadow = m["shadow"] and pool == "shadow"
    items, found = pool_items(sid, pool, results, shadow, (mine, m["cp"]) if me_in_pool else None)
    items += extra
    ok, got, held = fits(items, {k: c[0] for k, c in caps.items()}, mine, r)
    total = f"{len(items) + 1} in the {' / '.join(dict.fromkeys(c[1] for c in caps.values()))} family"
    notes = [] if found else [f"not seen in its own {what} search"]
    if ok:
        n, name, weak = caps[got]
        also = [caps[k][1] for k in r if k != got and caps.get(k)]
        return True, f"{what}: {pct(mine)} gets a top {n} {name} spot{weak}, of {total}" + \
            (f" (could also be {', '.join(also)})" if also else ""), notes
    full = []
    for k in r:
        if not caps.get(k):
            continue
        n, name, weak = caps[k]
        full.append(f"{name} top {n}{weak} full: " + ", ".join(f"{t[0]!r} CP{t[1]}" for _, t in held[k][:3]) +
                    (" ..." if len(held[k]) > 3 else ""))
    return False, f"{what}: no spot, of {total}. " + ("; ".join(full) or "nothing it can become"), notes

def decide(m, results):
    """m: dict species, cp, name, shadow, lucky, dynamax. results: search string -> [(tile name, cp)].
    -> (KEEP | NOPE | LEAVE, [reasons])"""
    p = parse_name(m["name"])
    sized = p.size or bool(m.get("size"))  # the XXL/XXS badge read on the detail screen counts too
    why, notes = [], []
    gym_unsure = False
    sid = m["species"]
    if sid in GYM_DEFENDERS:
        tiles = list(results[search(sid, "gym")])
        me = next((i for i, (n, c) in enumerate(tiles) if c == m["cp"]), None)
        if me is None:  # its own tile may be a top-row one with the CP hidden
            me = next((i for i, (n, c) in enumerate(tiles) if c == 0 and n == m["name"]), None)
        if me is not None:
            tiles.pop(me)
        cps = [(c, n, c) for n, c in tiles if c]
        hidden = len(tiles) - len(cps)  # CP unreadable: could be above or below
        ok, better = beaten(m["cp"], cps, TOP_GYM_CP)
        if ok and len(better) + hidden < TOP_GYM_CP:
            return "KEEP", [f"gym: CP{m['cp']} is top {TOP_GYM_CP} of {len(tiles) + 1} {base_name(sid).title()}"]
        if ok:
            gym_unsure = True
            why.append(f"gym: {len(better)} with more CP, {hidden} with the CP hidden")
        else:
            why.append(f"gym: {len(better)} with more CP (20th: CP{better[TOP_GYM_CP - 1][0]})")
    mine = value(m["name"], m["shadow"])
    if mine is None:
        return ("LEAVE" if sized or gym_unsure else "NOPE"), why + [f"no IV in the name {m['name']!r}"]
    if mine >= ALWAYS:
        return "KEEP", [f"{pct(mine)} always keeps"]
    if m["shadow"] and p.purified is not None and p.purified >= ALWAYS:
        return "KEEP", [f"purifies to {pct(p.purified)}, always keeps"]
    if sid in OWN_FORM:
        return "KEEP", [f"{sid} is its own form"]
    if "*" in m["name"] and not all(strong(line)[0] for line in lines_of(sid)):
        return "KEEP", [f"weak line, but {m['name']!r} has an Elite TM move"]
    main = "shadow" if m["shadow"] else "plain"
    r = my_reach(m, mine, results, main)
    if not r:
        why.append(f"a {base_name(sid).title()} that can't evolve into anything (wrong gender): no spot")
    checks = [(main, "shadow" if m["shadow"] else "not shadow")] + \
        ([("lucky", "lucky")] if m["lucky"] else []) + ([("dmax", "Dynamax")] if m["dynamax"] else [])
    for pool, what in checks if r else []:
        ok, reason, more = judge_pool(m, results, pool, what, mine, r)
        notes += more
        if ok:
            return "KEEP", [reason] + notes
        why.append(reason)
    if r and m["shadow"] and p.purified is not None:  # a shadow out of the shadow spots may still fit once purified
        ok, reason, _ = judge_pool(m, results, "plain", f"purified ({pct(p.purified)})", p.purified, r, False,
                                   spotless_shadows(sid, results, (mine, m["cp"])))
        if ok:
            return "KEEP", [reason] + notes
        why.append(reason)
    if not (sized or gym_unsure) and any(s.startswith(c) for line in lines_of(sid) for s in line for c in COLLECT):
        return "LEAVE", ["pattern collection: yours to pick"] + why + notes
    return ("LEAVE" if sized or gym_unsure else "NOPE"), why + notes


def pick_species(options):
    """one species from the CP/HP guesses. Guesses that share every line (tentacool or tentacruel) sort the same,
    so any of them will do. Gym defenders count CP per species, so those must be exact."""
    if len(options) == 1:
        return options[0]
    if options and not set(options) & GYM_DEFENDERS and \
            all(sorted(lines_of(o)) == sorted(lines_of(options[0])) for o in options):
        return options[0]
    return None


def searches_for(m):
    """every search decide() needs for this member"""
    sid, out = m["species"], []
    if sid in GYM_DEFENDERS:
        out.append(search(sid, "gym"))
    p = parse_name(m["name"])
    if value(m["name"], m["shadow"]) is None:
        return out
    pools = (["shadow"] + (["plain"] if p.purified is not None else [])) if m["shadow"] else \
        ["plain"] + (["lucky"] if m["lucky"] else []) + (["dmax"] if m["dynamax"] else [])
    out += [q for pool in pools for q, _, _ in groups(sid, pool)]
    return list(dict.fromkeys(out))


# ---------- tests ----------

def test():
    bad = 0

    def check(what, got, want):
        nonlocal bad
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {what}: {got!r}" + ("" if ok else f"  wanted {want!r}"))

    check("name 96 A", parse_name("96 A"), Name(43, None, False, False))
    check("name 87/96 A* XXL", parse_name("87/96 A* XXL"), Name(39, 43, True, False))
    check("name xxs", parse_name("xxs"), Name(None, None, True, False))
    check("name FP*", parse_name("FP*"), Name(None, None, False, False))
    check("name Pvp G12", parse_name("Pvp G12").pvp, True)
    check("name 89/100 a S*^", parse_name("89/100 a S*^"), Name(40, 45, True, False))
    check("all IV% map back", all(iv_sum(round(s * 100 / 45)) == s for s in range(46)), True)
    check("purified value", value("87/96 A", shadow=False), 43)
    check("shadow value", value("87/96 A", shadow=True), 39)
    check("eevee lines", len(lines_of("eevee")), 8)
    check("vaporeon line", lines_of("vaporeon"), [("eevee", "vaporeon")])
    check("same-line guesses", pick_species(["tentacool", "tentacruel"]), "tentacool")
    check("guesses on two lines", pick_species(["kirlia", "gallade"]), None)
    check("gym guesses", pick_species(["chansey", "blissey"]), None)
    check("ralts lines", sorted(lines_of("kirlia")), [("ralts", "kirlia", "gallade"), ("ralts", "kirlia", "gardevoir")])
    b = lambda sid: SPECIES[sid]["baseStats"]
    cz = (pvp.cp(b("charizard"), (15, 14, 13), 30), pvp.hp(b("charizard"), (15, 14, 13), 30))
    check("identify charizard", identify("CHARMANDER", {"FIRE", "FLYING"}, *cz, 42), ["charizard"])
    cm = (pvp.cp(b("charmeleon"), (15, 14, 13), 30), pvp.hp(b("charmeleon"), (15, 14, 13), 30))
    check("identify charmeleon", identify("CHARMANDER", {"FIRE"}, *cm, 42), ["charmeleon"])
    av = (pvp.cp(b("vulpix_alolan"), (10, 14, 13), 20), pvp.hp(b("vulpix_alolan"), (10, 14, 13), 20))
    check("identify articuno (no family)", identify("ARTICUNO", {"ICE", "FLYING"}, 1715, 130, 40), ["articuno"])
    check("identify alolan vulpix", identify("VULPIX", {"ICE"}, *av, 37), ["vulpix_alolan"])
    check("charmander top", top_n(lines_of("charmander")[0]), 6)
    check("meganium top (Z-A)", top_n(lines_of("chikorita")[0]), 6)
    check("pikachu->raichu top", top_n(("pichu", "pikachu", "raichu")), 6)
    check("alolan raichu top", top_n(("pichu", "pikachu", "raichu_alolan")), 5)
    check("rattata top", top_n(lines_of("rattata")[0]), 5)
    check("search", search("vulpix_alolan", "shadow"), "37&alola&!#Nope&shadow")
    check("search plain", search("charmander", "plain"), "4&!#Nope&!shadow")
    check("search gym", search("blissey", "gym"), "242&!#Nope")
    ty = lines_of("typhlosion_hisuian")
    check("hisui typhlosion line", ty, [("cyndaquil", "quilava", "typhlosion_hisuian")])
    check("no regional forms, no region filter", search("cyndaquil", "plain"), "155&!#Nope&!shadow")
    check("regional dex filters out its forms", search("typhlosion", "plain"), "157&!hisui&!#Nope&!shadow")

    S = lambda s, pool: search(s, pool)

    def by_fam(per, sid="charizard"):
        """tiles per species search ('4&!#Nope&!shadow', or with &male& for a gender split) -> the family searches
        decide() reads (gym searches stay as they are)"""
        r = {q: v for q, v in per.items() if q.endswith(NOT_NOPE)}
        for pool in POOLS:
            for q, _, ss in groups(sid, pool):
                g = next((x for x in ("male", "female") if f"&{x}&" in q), None)
                r[q] = [t for x in ss for t in per.get(with_gender(search(x, pool), g), [])]
        return r

    def resf(sid, **kw):
        """kirlia__plain__male=[tiles]: tiles per species, pool and (for a gender split) gender"""
        per = {}
        for k, v in kw.items():
            x, pool, g = (k.split("__") + [None])[:3]
            per[with_gender(search(x, pool), g)] = v
        return by_fam(per, sid)

    res = lambda **kw: resf("charizard", **kw)

    me = {"species": "charizard", "cp": 2000, "name": "93", "shadow": False, "lucky": False, "dynamax": False}
    six_better = [(f"{p}", 1500 + p) for p in (100, 98, 98, 96, 96, 96)]
    check("7th of 7 -> NOPE", decide(me, res(charizard__plain=six_better + [("93", 2000)]))[0], "NOPE")
    check("tie with 6th keeps", decide(me, res(charizard__plain=six_better[:5] + [("93", 1)] + [("93", 2000)]))[0], "KEEP")
    check("pool across line", decide(me, res(charmander__plain=six_better, charizard__plain=[("93", 2000)]))[0], "NOPE")
    check("species names don't count",
          decide(me, res(charmander__plain=[("Charmander", 500)] * 9, charizard__plain=[("93", 2000)]))[0], "KEEP")
    check("XXL badge, name lost it -> LEAVE", decide(dict(me, size="XXL"), res(charizard__plain=six_better))[0], "LEAVE")
    check("XXL fails -> LEAVE", decide(dict(me, name="93 XXL"), res(charizard__plain=six_better))[0], "LEAVE")
    check("move only -> NOPE", decide(dict(me, name="FP*"), res())[0], "NOPE")
    check("xxs only -> LEAVE", decide(dict(me, name="xxs"), res())[0], "LEAVE")
    sh = dict(me, shadow=True, name="80/93 a")
    check("shadow vs shadows only", decide(sh, res(charizard__plain=six_better, charizard__shadow=[("80/93 a", 2000)]))[0], "KEEP")
    check("shadow beaten", decide(sh, res(charizard__shadow=[("82/96", 1)] * 6, charizard__plain=six_better))[0], "NOPE")
    check("shadow top 5 in a mega line", decide(sh, res(charizard__shadow=[("82/96", 1)] * 5, charizard__plain=six_better))[0], "NOPE")
    check("shadow 5th keeps", decide(sh, res(charizard__shadow=[("82/96", 1)] * 4, charizard__plain=six_better))[0], "KEEP")
    check("spotless shadows purify too: only the best keeps", [decide(dict(sh, name=n, cp=c), res(
          charizard__shadow=[("82/96", 1)] * 5 + [("80/93 a", 2000), ("78/91 a", 2001)],
          charizard__plain=six_better[:5]))[0] for n, c in (("80/93 a", 2000), ("78/91 a", 2001))], ["KEEP", "NOPE"])
    check("shadow out of shadow spots, top 6 once purified", decide(sh, res(charizard__shadow=[("82/89", 1)] * 6,
          charizard__plain=six_better[:5] + [("91", 1)]))[0], "KEEP")
    check("purified ranks by 2nd number",
          decide(me, res(charizard__plain=[("87/100", 1)] * 6 + [("93", 2000)]))[0], "NOPE")
    lk = dict(me, lucky=True)
    check("best lucky keeps", decide(lk, res(charizard__plain=six_better, charizard__lucky=[("93", 2000), ("91", 5)]))[0], "KEEP")
    check("2nd lucky nopes", decide(lk, res(charizard__plain=six_better, charizard__lucky=[("96", 5)]))[0], "NOPE")
    dm = dict(me, dynamax=True)
    check("top 3 dmax keeps", decide(dm, res(charizard__plain=six_better, charizard__dmax=[("96", 1), ("96", 2)]))[0], "KEEP")
    check("4th dmax nopes", decide(dm, res(charizard__plain=six_better, charizard__dmax=[("96", 1)] * 3))[0], "NOPE")
    bl = {"species": "blissey", "cp": 3000, "name": "40 h", "shadow": False, "lucky": False, "dynamax": False}
    gym = {S("blissey", "gym"): [("Blissey", 3500)] * 19 + [("40 h", 3000)],
           S("chansey", "plain"): [], S("blissey", "plain"): [("100", 1000)] * 5,
           S("happiny", "plain"): []}
    check("gym 20th by CP keeps", decide(bl, by_fam(gym, "blissey"))[0], "KEEP")
    gym[S("blissey", "gym")] = [("Blissey", 3500)] * 20
    check("gym 21st by CP, low IV nopes", decide(bl, by_fam(gym, "blissey"))[0], "NOPE")
    check("gym IV still counts", decide(dict(bl, name="100"), by_fam(gym, "blissey"))[0], "KEEP")
    gym[S("blissey", "gym")] = [("Blissey", 3500)] * 18 + [("Blissey", 0)] * 3
    check("gym hidden CPs could push it out: leave", decide(bl, by_fam(gym, "blissey"))[0], "LEAVE")
    gym[S("blissey", "gym")] = [("Blissey", 3500)] * 10 + [("Blissey", 0)] * 3 + [("40 h", 0)]
    check("gym own tile CP hidden, still top 20", decide(bl, by_fam(gym, "blissey"))[0], "KEEP")
    check("own top-row tile (CP hidden) taken out of its pool",
          decide(me, res(charizard__plain=[("93", 0)] + [("100", 5)] * 5))[0], "KEEP")
    many = [(f"{p}", 1500 + p) for p in (100, 100, 100, 98, 98, 98, 98)]
    check("98 past top 6 keeps", decide(dict(me, name="98"), res(charizard__plain=many + [("98", 2000)]))[0], "KEEP")
    check("shadow purifying to 98 keeps", decide(dict(sh, name="84/98"), res(charizard__shadow=[("100", 1)] * 6))[0], "KEEP")
    kl = {"species": "kirlia", "cp": 800, "name": "93", "shadow": False, "lucky": False, "dynamax": False}
    rk = lambda **kw: resf("kirlia", **kw)
    check("ralts searches", sorted(q for q, _, _ in groups("gallade", "plain")),
          ["280,281&!#Nope&!shadow".replace("&!#", "&female&!#"), "280,281&male&!#Nope&!shadow",
           "282&!#Nope&!shadow", "475&!#Nope&!shadow"])
    check("7th male kirlia keeps for gardevoir", decide(kl, rk(kirlia__plain__male=six_better + [("93", 800)]))[0], "KEEP")
    check("7th male kirlia, gardevoir full too", decide(kl, rk(kirlia__plain__male=six_better + [("93", 800)],
          gardevoir__plain=six_better))[0], "NOPE")
    check("13th male kirlia nopes", decide(kl, rk(kirlia__plain__male=six_better * 2 + [("93", 800)]))[0], "NOPE")
    check("female kirlia never takes a gallade spot", decide(kl, rk(kirlia__plain__female=[("93", 800)],
          gardevoir__plain=six_better))[0], "NOPE")
    gl = dict(kl, species="gallade", cp=2500)
    check("gallade under 6 better males keeps (they can be gardevoir)",
          decide(gl, rk(kirlia__plain__male=six_better, gallade__plain=[("93", 2500)]))[0], "KEEP")
    check("gallade under 6 better males, gardevoir full", decide(gl, rk(kirlia__plain__male=six_better,
          gallade__plain=[("93", 2500)], gardevoir__plain=six_better))[0], "NOPE")
    ev = dict(kl, species="eevee", cp=500)
    full = {f"{x}__plain": six_better for x in ("flareon", "espeon", "umbreon", "leafeon", "glaceon", "sylveon")}
    check("eevee: vaporeon and jolteon are weak, top 1 each", [spots("eevee", "plain")[slot(x)][0]
          for x in ("vaporeon", "jolteon", "espeon")], [1, 1, 5])
    check("one eevee can't fill two spots", decide(ev, resf("eevee", eevee__plain=[("96", 1), ("93", 500)], **full))[0],
          "KEEP")
    check("eevee: every spot taken", decide(ev, resf("eevee", jolteon__plain=[("100", 1)],
          eevee__plain=[("96", 1), ("93", 500)], **full))[0], "NOPE")
    cb = dict(kl, species="combee", cp=300)
    check("male combee: no spot", decide(cb, resf("combee", combee__plain__male=[("93", 300)]))[0], "NOPE")
    check("female combee keeps", decide(cb, resf("combee", combee__plain__female=[("93", 300)]))[0], "KEEP")
    check("meowstic searches", sorted(q for q, _, _ in groups("espurr", "plain")),
          ["677,678&female&!#Nope&!shadow", "677,678&male&!#Nope&!shadow"])
    check("snorunt finals", {k: sorted(r) for k in ("male", "female") for r in [reach("snorunt", k)]},
          {"male": ["362&!#Nope&!shadow"], "female": ["362&!#Nope&!shadow", "478&!#Nope&!shadow"]})
    check("armored mewtwo keeps", decide(dict(me, species="mewtwo_armored", name="80 a"), {})[0], "KEEP")
    rat = ("bidoof", "bibarel")
    check("bidoof line is weak", strong(rat)[0], False)
    check("not on DialgaDex counts strong", strong(("dunsparce", "dudunsparce"))[0], True)
    rt = dict(me, species="bibarel", name="91")
    rr = lambda tiles, pool="plain": by_fam({search("bibarel", pool): tiles}, "bibarel")
    check("weak line, tie for top keeps", decide(rt, rr([("91", 1), ("91", 2000)]))[0], "KEEP")
    check("weak line, 2nd nopes", decide(rt, rr([("93", 1), ("91", 2000)]))[0], "NOPE")
    check("weak line, 96 under a 98 nopes", decide(dict(rt, name="96"), rr([("98", 1), ("96", 2000)]))[0], "NOPE")
    check("weak line, best lucky still keeps", decide(dict(rt, lucky=True), rr([("93", 1)]))[0], "KEEP")
    check("weak line, Elite TM keeps", decide(dict(rt, name="91 C*"), rr([("93", 1)]))[0], "KEEP")
    check("legendary line never weak", strong(("regice",))[0], True)
    check("gym defender line never weak", strong(("wynaut", "wobbuffet"))[0], True)
    vv = dict(me, species="vivillon", name="80")
    vl = ("scatterbug", "spewpa", "vivillon")
    check("vivillon nope -> leave", decide(vv, by_fam({search("vivillon", "plain"): [("96", 1)] * 6}, "vivillon"))[0], "LEAVE")
    check("icon read as 9", parse_name("996 HD").iv, iv_sum(96))
    check("icon read as dot", parse_name("•62 A").iv, iv_sum(62))
    check("icon variants clean the same", {clean_name(n) for n in ("993 H", "$93 H", "93 H", "• 93 H", "•93H", "093 H")}, {"93 H"})
    check("clean keeps other names", [clean_name(n) for n in ("L35", "87/96A* XXL", "Pvp G12", "Absol")],
          ["L35", "87/96 A* XXL", "Pvp G12", "Absol"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "test":
        test()
    elif a[0] == "name":
        print(parse_name(" ".join(a[1:])))
    elif a[0] == "lines":
        for line in family(a[1]):
            print(" -> ".join(line))
        for pool in POOLS:
            print(f"{pool}: " + ", ".join(f"{n} top {k}{w}" for k, n, w in spots(a[1], pool).values()))
            for q, r, ss in groups(a[1], pool):
                print(f"    {q:40} {'/'.join(ss)} -> {', '.join(spots(a[1], pool)[k][1] for k in r) or 'nothing'}")
    elif a[0] == "megas":
        print(" ".join(sorted(MEGA_BASES)))
    else:
        sys.exit(__doc__)
