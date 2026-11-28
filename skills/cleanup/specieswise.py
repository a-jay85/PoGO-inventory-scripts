#!/usr/bin/env python3
"""Re-judge HashTagAJay's #GIV, #Transfer or #Reroll pile by species alone, with no Pokémon opened (the user, 2026-11-16;
#Reroll 2026-11-22, after its raid Rerolls began to follow CyrillJan's raid team count).

  python3 specieswise.py plan GIV|Transfer|Reroll                                   the Mac: the searches it would tag
  POGO_PHONE=android python3 specieswise.py GIV|Transfer|Reroll   HashTagAJay on the Pixel: tag them

Each species is judged once by ../shared/verdict.py, the one rule book, as a plain one: untraded, caught 30 days ago,
no odd size, level 20, caught nearby, its gym top 20 out. HashTagAJay's Candy and Candy XL per family come from the
Pokémon database (../shared/pokedb.py: what the scripts read last); a family it has no count for counts as 360+ XL
and plenty of Candy (most of HashTagAJay's are), except a costly line's Candy (5000+ of it: Transfer), so that's not sure. So the species rules decide: Reroll (raid top 6, the user 2026-11-19), GIV (stage 2, hard
evolutions, egg families, gym lines, trade evolutions, costly lines, short of Candy for Dynamax), 2XL (under 360 XL),
or Transfer. No appraisal, no power-up cost, no page read: the IV rule (98%+) doesn't run. Level isn't searchable, so a
Transfer search takes only CPs no level 26+ one has (GIV at level 26+ comes before Transfer): under the species'
CP at level 26 with 0/0/0 IVs (cp-N). Species are put in CP tiers (TIER: the top cap at most 1.5 x the lowest),
one search per tier at its lowest cap. Ones over it stay in the pile. Each species is judged as caught nearby, so
before each Transfer search the same one with distance100- gets GIV (far, which comes before Transfer).

Left as they are, out of every search: ones a rule before the species rules decides (traded, lucky, shadow, shiny,
costume, background, XXL, XXS, Dynamax, Gigantamax, caught 300+ days ago or in 2016-2020, special trades), ones with
another of the user's tags, and a species verdict.py isn't sure of (regionals and Spinda: by hand). A dex number whose
forms disagree is searched form by form (37&alola, 37&!alola).

Each group (one tag, one search) is tagged in bulk: long press, SELECT ALL, the new tag on, the pile's tag off
(../shared/savedsearch.py tag_pile). A group whose answer is the pile's own tag isn't touched.

CyrillJan's #Reroll or #GIV, for some dex numbers (the user, 2026-11-20: after a rule change, the families it touched;
#GIV 2026-11-23):
  python3 specieswise.py plan Reroll|GIV --as CyrillJan --and 4-6,25-26
  POGO_PHONE=android python3 specieswise.py Reroll|GIV --as CyrillJan --and 4-6,25-26
Only 0-2* ones that aren't shadows (on no raid team: the user's rule of thumb). The searches go in steps by what the
game can search: caught in 2016-2020, caught 300+ days ago, Dynamax, caught 100 km+ away, then the rest; inside a
step, split by the family's Candy and Candy XL (countcandy, countcandyxl) where the rules cut. Each species and step
is tried at every value a search can't see (dates, gender, IVs inside 0-2*), and goes in a search only if all give
one tag. Gym defenders and the size-medal species are left out. Levels don't count in #Reroll (the user, 2026-11-20).
#GIV holds the old level 26+ ones (XLX), so its Transfer searches take only CPs under level 26 (cp-N, as above). What's
left (3*+, shadows, not sure) goes to the walk: leftovers.py again Reroll|GIV --as CyrillJan.
On the phone (either account) it first counts the account's 100s of each Team Future/Ideal pick
(tradeable.count_team100), so a line's GIV bar (360 Candy XL a 100, up to 5: verdict.team_short) is today's. plan
uses the newest count.
"""
import datetime, itertools, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.append(os.path.join(HERE, "..", "ivc"))  # verdict needs /ivc's GYM_DEFENDERS
import base
from base import Stop, log
import ui
import pvp, rules, search

PILES = ("GIV", "Transfer", "Reroll")  # (Reroll: after a raid Reroll rule change, the user 2026-11-22)
FAR = "&distance100-"  # caught 100 km+ away: GIV (far), which comes before Transfer
GIVER_PILES = ("Reroll", "GIV")  # (GIV: 2026-11-23, once GIV became "CyrillJan needs the trade's candy")
WHO = rules.TAKER  # HashTagAJay
GIVER = rules.GIVER  # CyrillJan: its piles go by the steps below
# a rule before the species ones decides these (or the user does): never in a search
LEFT_OUT = ("&!favorite&!traded&!lucky&!shadow&!shiny&!costume&!background&!xxl&!xxs&!dynamax&!gigantamax"
            "&!legendary&!mythical&!ultrabeast&!age300-&!year2016-2020"
            "&!#IVC&!#PvpC&!#Old&!#2XL&!#XLX&!#Reroll&!#GuaranteedLucky&!#RT")
CHUNK = 700  # characters of dex numbers per search: with LEFT_OUT, well under the 1,000 a search keeps to
TIER = 1.5  # Transfer's CP tiers: a tier's caps are at most this times its lowest (a lower cap leaves more as they are)
CAP_TAGS = (rules.TRANSFER,)  # the tags verdict.py puts after GIV (level 26+): only CPs under level 26 go in


def species_tag(sid, t, counts, vd):
    """-> verdict.Verdict for a plain one of this species on HashTagAJay"""
    c = counts.get(pvp.candy_family(sid)) or {}
    candy, xl = c.get("candy"), c.get("xl")
    costly = pvp.SPECIES[sid]["dex"] in vd.COSTLY_DEX  # (no count: plenty, but a costly line's 5000 bar needs one)
    candy = (None if costly else 10 ** 6) if candy is None else candy
    # (no count: 360+ XL, but a Team Future/Ideal line's bar can be higher, so its count stays unread: not sure)
    read = None if xl is None and sid in t.get("team_xl", {}) else xl
    xl = 10 ** 6 if xl is None else xl
    f = vd.Facts(account=WHO, sids=[sid], iv_sum=30, ivs=(10, 10, 10), traded=False,
                 caught=datetime.date.today() - datetime.timedelta(days=30), gender="", size="", kg=None,
                 candy_xl=xl, candy=candy, xl=xl if read is not None else None, levels=[20.0], evolves=True,
                 far=False, gym_top20=False)
    return vd.final_tag(f, t)


def groups(pile):
    """-> ({tag: [search part]}, {tag: n species}, [(sid, why) not sure])"""
    import verdict as vd
    import pokedb
    t = vd.tables(vd.TO[WHO])
    if "missing" in t:
        raise Stop(f"no species lists: {t['missing']}")
    counts = pokedb.candies(WHO)
    by_dex = defaultdict(dict)  # dex -> {sid: tag or None (not sure)}
    unsure = []
    for sid, p in pvp.PLAIN.items():
        if not p.get("released", True) or set(p.get("tags") or []) & set(rules.SPECIAL):
            continue
        v = species_tag(sid, t, counts, vd)
        if v.kind == "tag" and len(v.tags) == 1:
            by_dex[p["dex"]][sid] = v.tags[0]
        else:
            by_dex[p["dex"]][sid] = None
            unsure.append((sid, f"{v.kind} {'+'.join(v.tags)}: {v.why}"))
    out, n, more = dex_parts(by_dex, pile, CHUNK, caps={tag: under26 for tag in CAP_TAGS})
    return out, n, unsure + more


def under26(sids):
    """the highest CP no level 26+ one of these forms can have: one under the lowest one's CP at level 26, 0/0/0"""
    return min(pvp.cp(pvp.SPECIES[s]["baseStats"], (0, 0, 0), rules.XLX_LEVEL) for s in sids) - 1


def tiers(caps):
    """{key: CP cap} -> {key: its tier's cap}: caps sorted low to high, a new tier once one is over TIER x the tier's
    lowest. The tier's cap is its lowest, so no level 26+ one comes in"""
    out, low = {}, None
    for k, c in sorted(caps.items(), key=lambda kc: kc[1]):
        if low is None or c > low * TIER:
            low = c
        out[k] = low
    return out


def dex_parts(by_dex, pile, size, caps=None):
    """{dex: {sid: tag or None (not sure)}} -> ({tag: [search part]}, {tag: n species}, [(sid, why) not sure]). A dex
    whose forms all agree is searched by its number alone; one whose forms disagree, form by form (37&alola).
    caps {tag: f([sid]) -> CP cap}: that tag's searches go by CP tier, each with &cp-<its cap>"""
    caps = caps or {}
    unsure = []
    parts = defaultdict(lambda: defaultdict(list))  # tag -> the form terms ('', '&alola', '&!alola') -> [(dex, sids)]
    n = defaultdict(int)
    for d, forms in sorted(by_dex.items()):
        if len(set(forms.values())) == 1:  # every form agrees: the dex number alone
            tag = next(iter(forms.values()))
            if tag:
                parts[tag][""].append((d, list(forms)))
                n[tag] += len(forms)
            continue
        for sid, tag in forms.items():
            terms = pvp.search(sid, "plain").removeprefix(str(d)).removesuffix(pvp.POOL_TERMS["plain"])
            if not terms:  # forms with no region term (Burmy's cloaks) that disagree: by hand
                unsure.append((sid, f"its dex's forms disagree and have no search term"))
                continue
            if tag:
                parts[tag][terms].append((d, [sid]))
                n[tag] += 1
    out = {}
    for tag, by_terms in parts.items():
        if tag == pile:
            continue
        groups = defaultdict(list)  # (the form terms, the CP term) -> [dex]
        if tag in caps:
            tier = tiers({(terms, d): caps[tag](sids) for terms, ds in by_terms.items() for d, sids in ds if not terms})
            for terms, ds in by_terms.items():  # the few split by form: one search each, at their lowest cap
                if terms:
                    tier.update({(terms, d): caps[tag](sum((sids for _, sids in ds), [])) for d, _ in ds})
            for (terms, d), cap in tier.items():
                groups[(terms, f"&cp-{cap}")].append(d)
        else:
            for terms, ds in by_terms.items():
                groups[(terms, "")] = [d for d, _ in ds]
        qs = []
        for (terms, cp), dexes in sorted(groups.items(), key=lambda g: (g[0][0], int(g[0][1][4:] or 0))):
            chunk = []
            for r in search.dex_ranges(dexes):
                if chunk and len(",".join(chunk + [r])) > size:
                    qs.append(",".join(chunk) + terms + cp)
                    chunk = []
                chunk.append(r)
            if chunk:
                qs.append(",".join(chunk) + terms + cp)
        out[tag] = qs
    return out, dict(n), unsure


# ---------- CyrillJan's piles: step by step, by what a search can see (the user, 2026-11-20) ----------
# The user's shortcuts for the rules a search can't see: a raid team needs 3* or better (shadows aside), so 0-2* ones
# are on none; the gym top 20 and the size medals are their own few species (left out here); levels don't count.
D = datetime.date
GIVER_STEPS = (  # (search term, the facts it leaves open: every value is tried, all must give one tag)
    ("year2016-2020", dict(caught=(D(2016, 7, 6), D(2020, 12, 31)), dynamax=(False, True), far=(False, True))),
    ("age300-", dict(caught=("300", D(2021, 1, 1)), dynamax=(False, True), far=(False, True))),
    ("dynamax", dict(caught=("1", "299"), dynamax=(True,), far=(False, True))),
    ("distance100-", dict(caught=("1", "299"), dynamax=(False,), far=(True,))),
    ("", dict(caught=("1", "299"), dynamax=(False,), far=(False,))),
)
GIVER_IVS = ((0, 0, 0), (10, 10, 10), (12, 12, 12))  # 0-2*: on no raid team
GIVER_LEFT_OUT = ("&!favorite&!traded&!lucky&!shadow&!shiny&!costume&!background&!xxl&!xxs&!gigantamax"
                  "&!legendary&!mythical&!ultrabeast")
GIVER_OTHER_TAGS = ("IVC", "PvpC", "Old", "2XL", "XLX", "GIV", "Transfer", "Reroll", "GuaranteedLucky", "RT")
GIVER_CHUNK = 450
TOP = 10 ** 5  # a Candy or Candy XL count no family reaches  # the step terms, the Candy terms and the other tags take more room than LEFT_OUT


def candy_grid(sid, t):
    """-> ([Candy range], [Candy XL range]): where the rules cut for this species (XL_CAP for 2XL and cyrill_short;
    LUCKY_CANDY for cyrill_short; COSTLY_ENOUGH for a costly line, verdict.transfer; DMAX_CANDY and one Max Move's XL for a Dynamax line; a Team Future/Ideal line's bar,
    tradeable.team_xl_need). A range is (lo, hi), hi TOP for no top"""
    import verdict as vd
    need, team = t.get("dmax", {}).get(sid), t.get("team_xl", {}).get(sid)
    xl_starts = {0, vd.XL_CAP} | ({need + 1} if need is not None else set()) | ({team[0]} if team else set())
    candy_starts = ({0, rules.LUCKY_CANDY} | ({rules.DMAX_CANDY + 1} if need is not None else set())
                    | ({rules.COSTLY_ENOUGH} if pvp.SPECIES[sid]["dex"] in vd.COSTLY_DEX else set()))
    return ranges(candy_starts), ranges(xl_starts)


def ranges(starts):
    """{first value of each range} -> [(lo, hi)] in order, the last one up to TOP"""
    s = sorted(starts)
    return [(lo, hi - 1) for lo, hi in zip(s, s[1:])] + [(s[-1], TOP)]


def count_term(name, lo, hi):
    return "" if (lo, hi) == (0, TOP) else f"{name}{lo or ''}-{hi if hi < TOP else ''}"


def runs(cells):
    """[((lo, hi), tag)] in order -> the same with neighbours of one tag joined"""
    out = []
    for (lo, hi), tag in cells:
        if out and out[-1][1] == tag:
            out[-1] = ((out[-1][0][0], hi), tag)
        else:
            out.append(((lo, hi), tag))
    return out


def cyrill_tag(sid, t, open_facts, counts, vd, today):
    """-> the one tag every value of the open facts gives a plain 0-2* untraded one of this species, or None"""
    seen = set()
    for caught, dyn, far, ivs, gender, (candy, xl) in itertools.product(
            open_facts["caught"], open_facts["dynamax"], open_facts["far"], GIVER_IVS, ("male", "female"), counts):
        if isinstance(caught, str):  # days ago
            caught = today - datetime.timedelta(days=int(caught))
        f = vd.Facts(account=GIVER, sids=[sid], iv_sum=sum(ivs), ivs=ivs, traded=False, caught=caught, gender=gender,
                     size="", kg=None, candy_xl=xl, candy=candy, xl=xl, levels=[20.0], evolves=vd.plain_evolves(sid),
                     far=far, gym_top20=False, dynamax=dyn, raid_team=[])
        v = vd.final_tag(f, t, today)
        plain = v.kind == "tag" and len(v.tags) == 1 and not (v.name or v.purify or v.clear or v.star or v.unstar)
        seen.add(v.tags[0] if plain else None)
        if len(seen) > 1 or None in seen:
            return None
    return seen.pop()


def cyrill_groups(pile, dexes):
    """CyrillJan's pile, for these dex numbers -> [(tag, search part)] in the order to tag them, and [(sid, why)]
    left for the walk (leftovers.py again)"""
    import verdict as vd
    t = vd.tables(vd.TO[GIVER])
    if "missing" in t:
        raise Stop(f"no species lists: {t['missing']}")
    today = datetime.date.today()
    skip = {*rules.GYM_DEX, *vd.MEDALS}  # (their own rules: by hand)
    sids = [s for s, p in pvp.PLAIN.items() if p["dex"] in dexes and p["dex"] not in skip
            and p.get("released", True) and not set(p.get("tags") or []) & set(rules.SPECIAL)]
    out, walk, before = [], [], ""
    corners = lambda c, x: [(cc, xx) for cc in c for xx in x]
    # judged at level 20: a level 26+ one is GIV, so #GIV's Transfer searches take only CPs no level 26+ one has.
    # #Reroll goes without (levels don't count there, the user 2026-11-20)
    caps = {rules.TRANSFER: under26} if pile == "GIV" else None
    for term, open_facts in GIVER_STEPS:
        by = defaultdict(lambda: defaultdict(dict))  # the Candy terms -> dex -> {sid: tag or None}
        for sid in sids:
            cs, xs = candy_grid(sid, t)
            if tag := cyrill_tag(sid, t, open_facts, [p for c in cs for x in xs for p in corners(c, x)], vd, today):
                by[""][pvp.PLAIN[sid]["dex"]][sid] = tag
                continue
            rows = [runs([(x, cyrill_tag(sid, t, open_facts, corners(c, x), vd, today)) for x in xs]) for c in cs]
            if all(r == rows[0] for r in rows):  # the Candy count doesn't matter: Candy XL alone
                rows, cs = rows[:1], [(0, TOP)]
            for c, row in zip(cs, rows):
                for x, tag in row:
                    cterm = "&".join(filter(None, (count_term("countcandy", *c), count_term("countcandyxl", *x))))
                    by[cterm][pvp.PLAIN[sid]["dex"]][sid] = tag
                    if not tag:
                        walk.append((sid, f"{term or 'the rest'} {cterm}: the rules split it"))
        for cterm, by_dex in by.items():
            for d, forms in by_dex.items():  # a form of this dex that isn't in this group must not come in
                for sid in (s for s in sids if pvp.PLAIN[s]["dex"] == d):
                    forms.setdefault(sid, None)
            parts, _, unsure = dex_parts(by_dex, pile, GIVER_CHUNK, caps=caps)
            walk += [(s, w) for s, w in unsure if by_dex[pvp.PLAIN[s]["dex"]].get(s)]
            for tag, qs in parts.items():
                out += [(tag, "&".join(filter(None, (q, term, cterm))) + before) for q in qs]
        if term:
            before += f"&!{term}"
    return out, walk


def query(pile, part, who=WHO):
    if who == GIVER:
        others = "".join(f"&!#{t}" for t in GIVER_OTHER_TAGS if t != pile)
        return f"#{pile}&0*,1*,2*&{part}{GIVER_LEFT_OUT}{others}"  # (0-2* first: a bar ending in #Reroll reads back short)
    return f"#{pile}&{part}{LEFT_OUT.replace(f'&!#{pile}', '')}"  # (the pile's own tag would leave out all of it)


def plan_of(pile, who, dexes):
    """-> ([(tag, search part)] in the order to tag them, [(sid, why) not sure], {tag: n species} or None)"""
    if who == GIVER:
        got, unsure = cyrill_groups(pile, dexes)
        return got, unsure, None
    got, n, unsure = groups(pile)
    out = []
    for tag, qs in got.items():
        for q in qs:  # a species judged Transfer was judged as caught nearby: its far ones get GIV first
            out += ([("GIV", q + FAR)] if tag == rules.TRANSFER and pile != "GIV" else []) + [(tag, q)]
    return out, unsure, n


def cmd_plan(pile, who, dexes):
    got, unsure, n = plan_of(pile, who, dexes)
    for tag, q in got:
        print(f"{tag}: {query(pile, q, who)}")
    print(f"\n{len(got)} searches." + (f" Left as #{pile}: {n.get(pile, 0)} species." if n else "")
          + f" Not sure (left as they are): {len(unsure)}")
    for sid, why in unsure:
        print(f"  {sid}: {why}")


def cmd_tag(pile, who, dexes):
    import home, savedsearch
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=f"specieswise-{pile.lower()}")
    now = home.trainer()
    if now != who:
        if not ui.ANDROID:  # account.py signs in on the Pixel only
            raise Stop(f"signed in as {now!r}: this is {who}'s pile")
        import account
        log(f"signed in as {now!r}: switching to {who}")
        account.switch(who)
    home.start()
    import tradeable  # (before the species lists load: verdict.team_short's Team Future/Ideal bars read it)
    tradeable.count_team100(who)
    got, unsure, _ = plan_of(pile, who, dexes)
    log(f"#{pile}: {len(got)} searches; {len(unsure)} species not sure, left as they are")
    for sid, why in unsure:
        log(f"  not sure: {sid}: {why}")
    done, empty = {}, step_probe(pile, who, savedsearch)
    for tag, q in got:
        if empty(q):
            continue
        k = savedsearch.tag_pile(f"#{pile}", tag, off=(pile,), query=query(pile, q, who))
        done[tag] = done.get(tag, 0) + k
        log(f"DONE {tag}: {k} from #{pile} ({query(pile, q, who)})")
    log(f"#{pile} by species: {done}")


def step_probe(pile, who, savedsearch):
    """CyrillJan's piles: -> empty(search part), True when the part's step (GIVER_STEPS) has nothing in the pile at
    all. One short search a step (#GIV&0*,1*,2*&year2016-2020: short enough to type in one go), once, so every search
    of an empty step is skipped (2026-11-23: all 38 of the year, age and Dynamax ones found 0). HashTagAJay's piles
    have no steps: never empty"""
    seen, steps = {}, [term for term, _ in GIVER_STEPS if term]

    def empty(part):
        step = next((s for s in steps if s in part.split("&")), None) if who == GIVER else None
        if step is None:
            return False
        if step not in seen:
            seen[step] = savedsearch.long_search(f"#{pile}&0*,1*,2*&{step}") == 0
            log(f"#{pile}&0*,1*,2*&{step}: {'nothing: its searches are skipped' if seen[step] else 'some'}")
        return seen[step]
    return empty


def args(a):
    """-> (plan?, pile, who, dexes or None) from [plan] PILE [--as CyrillJan] [--and DEXES], or None"""
    plan = a[:1] == ["plan"]
    a = a[plan:]
    who = a[a.index("--as") + 1] if "--as" in a else WHO
    dexes = set(search.dexes_of(a[a.index("--and") + 1])) if "--and" in a else None
    piles = GIVER_PILES if who == GIVER else PILES
    if not a or a[0] not in piles or who not in (WHO, GIVER) or (who == GIVER) != (dexes is not None):
        return None
    return plan, a[0], who, dexes


if __name__ == "__main__":
    got = args(sys.argv[1:])
    if not got:
        sys.exit(__doc__)
    plan, pile, who, dexes = got
    if plan:
        cmd_plan(pile, who, dexes)
    else:
        import session
        session.main(cmd_tag, pile, who, dexes)
