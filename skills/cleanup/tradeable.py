#!/usr/bin/env python3
"""Tag CyrillJan's Tradeable saved search by what a trade to HashTagAJay is worth, and power them up for Candy XL.

  python3 tradeable.py refresh            the Mac: PvPoke's rankings -> pvp-giv-<date>.json, PokeMiners' game master
                                          -> giv-evolved-<date>.json, dynamax-<date>.json and maxmove-xl-<date>.json
                                          (one Max Move's Candy XL per dex number), LeekDuck's egg pools
                                          -> eggs-<date>.json (adds to the last one: a species stays once seen)
  POGO_PHONE=android python3 tradeable.py dynamax   either account: only searches, counts the
                                          signed-in one's (no rule reads its count since 2026-11-16)
  POGO_PHONE=android python3 tradeable.py read [searches.json]   HashTagAJay signed in: only searches
  POGO_PHONE=android python3 tradeable.py [door] [--limit N]  CyrillJan signed in: the default.
                                          The tag searches that need no page read first (2XL, GIV ...), then
                                          each untagged one left opened once and given its final tag at the door
  POGO_PHONE=android python3 tradeable.py tag [--limit N]   CyrillJan signed in: the fast way,
                                          bulk tag searches first, then power-ups, then the door for the rest
  POGO_PHONE=android python3 tradeable.py team100   either account: only searches. Its 100s
                                          (4*) of each Team Future and Team Ideal #1 pick that trades, and of what
                                          evolves into it -> runs/<time>-team100/team100.json (verdict.cyrill_short's
                                          bar, both accounts; specieswise counts them first by itself)
  python3 tradeable.py plan               the Mac, optional: a look at the searches tag would run (runs/<time>-plan/)

The species lists and the order here are also ../shared/verdict.py's: /ivc and /pvpc judge a Pokémon that
isn't a keeper with them (the door, no Nope). hashtag_species() is the other side, HashTagAJay's pile (leftovers.py),
judged for any account: Reroll, GIV, GIV (level 26+), GIV (evolved, 10/12 km eggs, Smeargle); regionals not from
San Francisco (rules.SF_NATIVE) and Spinda by hand (its docstring has the rules). MEDALS (a tiny Rattata, a big Magikarp: GIV for any account's medals) are the
door's too, on HashTagAJay.

Reroll means HashTagAJay needs it. GIV means CyrillJan needs the trade's candy (the sender gets 2-4 Candy and a
Candy XL: rules.TRADE_SENDER_CANDY), or the trade is worth it for some other reason below (the user, 2026-11-23).
One tag each, the first that fits:
 1. Luckydex: HashTagAJay's newest lucky /dex run misses it, or an evolution of it (dex's gender and form rules).
 2. Reroll: a strong line (strong_lines: on the ideal raid team against some 4-star+ boss, /ivc's sort.strong, or a
    gym defender's line), or a new copy would be in HashTagAJay's own top 6 against some raid boss (/roster's
    roster.json: #1 or #2-#6, the user 2026-11-19). Only for a 100 HashTagAJay still needs (the user, 2026-11-20): a
    place won only as a mega doesn't count (one 100 of it is enough), nor a family HashTagAJay has 5 100s of.
    A pattern collection (Vivillon's line) is GIV instead: the patterns aren't told apart yet (the user, 2026-11-20).
 3. Reroll too (GIV till 2026-11-23), any of
    - a new 100 would fill a hole on HashTagAJay's ★100% page, itself or by evolving (dex.hundred_useful: a later
      stage on the page counts for the earlier ones, each missing branch wants its own copy, and only a 100 still in
      storage counts as a copy: the /dex run's owned-100.json)
    - PvPoke top 100 in Great, Ultra or Master League, with every rank 1 IV 5 or more (pvp-giv-<date>.json)
    - HashTagAJay has a lucky one of the family and under 348 candy (read)
    - Tandemaus (rules.REROLL_FOR_TAKER)
 4. GIV at level 26+ (was XLX, the user 2026-11-19): a power-up costs 4 Candy or more (level 26+: 4,000 Stardust with 4 Candy, or 4,500+). Read one by one in the power-up dialog.
 5. GIV (evolved): a stage 2 (a baby isn't a stage), or a stage 1 that takes 100+ candy, a quest or an item to
    evolve into, or one GO can't evolve into yet (Kleavor, Alolan Marowak) (giv-evolved-<date>.json). Also gym
    defenders (/ivc's GYM_DEFENDERS) and untraded Dynamax ones. Tagged after the level 26+ walk.
 6. GIV (far): never traded and caught 100 km or more away ('distance100-'), and no other tag fits.
 7. GIV (CyrillJan short of candy): never traded, and CyrillJan has under 348 Candy of the family, or under 360
    Candy XL of a family with a species on Team Future, Team Ideal or one of CyrillJan's Team Availables or Team
    Potentials (team_lines, the user 2026-11-23) (cyrill_short_searches, verdict.cyrill_short). A line with a Team Future or Team Ideal #1 pick (not as a
    mega) wants 360 Candy XL for each 100 CyrillJan has of it, up to 5 (rules.TEAM_SLOTS: 4 100 Salamence want 1440,
    the user 2026-11-23). team100 counts those 100s (team_xl_need).
 8. Transfer: everything else, but a never-traded XXS one gets renamed xxs and tagged IVC (sizes.py)
    (a never-traded trade evolution gets Transfer here: HashTagAJay doesn't need the XP, 2026-11-02).
An XXL one gets no tag at all and is never powered up: it's made a favorite first (sizes.py, the user 2026-11-04).
Special trades get no tag at all and are never powered up: Legendary, Mythical, Ultra Beast, shiny and Gigantamax. The
user trades them by hand, so a tag never lines one up for a trade that uses up the day's special trade. Shadows can't
be traded.

Power-ups: only cleantrades' cheap jumps (14->15, 19->20, 22->23, 30->31), never below 1,000,000 Stardust, and only while
the account that will transfer it has under 360 Candy XL of the family: HashTagAJay (read) for the traded tags,
CyrillJan for the rest.

read (HashTagAJay): which families have a lucky one and under 348 candy, and which have 360+ Candy XL. Group searches
('lucky&1-151&countcandy0-347'), halved until each hit is one family. -> runs/<time>-read/read.json
tag makes its searches itself, each run, from the newest lucky and ★100% /dex runs of HashTagAJay, roster.json,
read.json and pvp-giv (no plan step; `plan` only shows them). A rerun within 12 hours skips the ones already done.
tag (CyrillJan): the saved search 'Tradeable' + each tag search (bulk_searches, in verdict.py's order: GuaranteedLucky,
Luckydex, Old, 2XL, Reroll, GIV) -> long press, SELECT ALL, tag. A lucky, costume or background one or a gym defender
skips the tag searches and goes to the door (rules.TAG_SKIP). tests/taggers.py checks these against verdict.py. Then each one left is
opened for GIV (level 26+) and power-ups, then the rest go through the door one by one (../shared/door.py: their final tag, or
left as they are and listed as not sure). Log in runs/<time>-tag/.

Data first: refresh, then read (HashTagAJay), plus HashTagAJay's newest lucky and ★100% /dex runs and /roster's roster.json.
--limit N caps the power-ups in each walk; all the tag searches still run. tag has never run on the phone: the first
time, tag --limit 1 (it still tags every tag search).
"""
import json, math, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.insert(0, os.path.join(HERE, "..", "dex"))
sys.path.append(os.path.join(HERE, "..", "ivc"))  # for ivc.py
import ui
import base
from base import Stop, Skip, log, go, look, wait_for
import search, pokedb
import pvp, gamedata
import home, session, tagsheet
import dex
import powerup
import savedsearch
import sizes
from taps import Pass, owned, details
from ivc import GYM_DEFENDERS
from rules import (GIVER, TAKER, TAGS, XLX, OLD_XLX, TRANSFER, LUCKY_CANDY, XL_CAP, TEAM_SLOTS, XLX_LEVEL, REROLL_FOR_TAKER, XLX_FOR,
    PVE_TOP, REROLL_ML, REROLL_ENOUGH, HARD_EGGS, HARD_TO_FARM, BY_HAND, SF_NATIVE, PVP_FLOOR, HARD_CANDY, BABIES, SPECIAL, NO_SPECIAL, DYNAMAX, UNDER_360_XL, UNDER_348_CANDY, TAG_SKIP, GUARANTEED,
    LUCKY_YEAR, OLD, OLD_AGE)

if ui.ANDROID:  # a look's shrink, save and OCR take 0.3-0.6 s, so at 0.3 most head-start shots were thrown away. The
    ui.android.PREFETCH_AGE = 0.8  # door's reads all look again till right: an older picture costs one cheap look (2026-11-09)

SHORTCUT = "Tradeable"
MAX_SUFFIX = 300  # characters added to the saved search: it's already in the bar
PVP_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall/rankings-%d.json"
EGGS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.min.json"


# ---------- refresh: PvPoke ----------

def cmd_refresh():
    import urllib.request
    keep = {}
    for cap in (1500, 2500, 10000):
        ranks = json.load(urllib.request.urlopen(PVP_URL % cap))[:100]
        for i, r in enumerate(ranks, 1):
            sid = r["speciesId"].replace("_shadow", "")
            if sid not in pvp.SPECIES:
                print(f"{cap}: no {sid} in the game data")
                continue
            ivs = (15, 15, 15) if cap == 10000 else pvp.table(sid, cap)[0][2]
            if min(ivs) >= PVP_FLOOR:
                keep.setdefault(sid, []).append(f"{cap}:#{i}")
    out = os.path.join(HERE, f"pvp-giv-{time.strftime('%Y%m%d')}.json")
    base.write_json(out, dict(sorted(keep.items())), indent=0)
    print(f"{len(keep)} species -> {out}")
    gm = gamedata.raw()
    hard = hard_evolutions(gm)
    out = os.path.join(HERE, f"giv-evolved-{time.strftime('%Y%m%d')}.json")
    base.write_json(out, dict(sorted(hard.items())), indent=0)
    print(f"{len(hard)} hard evolutions -> {out}")
    can = dynamax_species(gm)
    out = os.path.join(HERE, f"dynamax-{time.strftime('%Y%m%d')}.json")
    base.write_json(out, can)
    print(f"{len(can)} dex numbers can Dynamax -> {out}")
    xl = max_move_xl(gm)
    out = os.path.join(HERE, f"maxmove-xl-{time.strftime('%Y%m%d')}.json")
    base.write_json(out, xl, indent=0)
    print(f"{len(xl)} dex numbers' Max Move Candy XL -> {out}")
    refresh_eggs()


def refresh_eggs():
    """LeekDuck's egg pools (ScrapedDuck) -> eggs-<date>.json, {"10 km": [sid], ...}: HARD_EGGS' species, added to
    the newest copy's, so one that leaves the pool stays hard to get"""
    import urllib.request
    old_f = base.newest(HERE, "eggs-[0-9]*[0-9].json")
    out = json.load(open(old_f)) if old_f else {}
    by_name = {v["speciesName"].lower(): s for s, v in pvp.SPECIES.items()}
    for e in json.load(urllib.request.urlopen(EGGS_URL)):
        if e["eggType"] not in HARD_EGGS:
            continue
        sid = by_name.get(e["name"].lower())
        if not sid:
            print(f"eggs: no {e['name']} in the game data")
            continue
        if sid not in out.setdefault(e["eggType"], []):
            out[e["eggType"]].append(sid)
    f = os.path.join(HERE, f"eggs-{time.strftime('%Y%m%d')}.json")
    base.write_json(f, {k: sorted(v) for k, v in sorted(out.items())}, indent=0)
    print(f"{sum(map(len, out.values()))} hard egg species -> {f}")


def dynamax_species(gm):
    """PokeMiners' game master -> [dex numbers that can Dynamax] (a 'BREAD_MODE' override: 'bread' is Max)"""
    return sorted({int(re.search(r"V(\d{4})_", x["templateId"]).group(1)) for x in gm
                   if any(o.get("breadMode") == "BREAD_MODE"
                          for o in (x["data"].get("pokemonExtendedSettings") or {}).get("breadOverrides") or [])})


def max_move_xl(gm):
    """PokeMiners' game master -> {dex: the Candy XL that takes one Max Move to level 3 (the user, 2026-11-19: was all
    three)}, the most of its forms. Each species has a cost group (breadTierGroup); a group's three moves each cost XL
    on their last level, the costliest one counted"""
    cost = {}
    for x in gm:
        g = x["data"].get("breadMoveLevelSettings")
        if g and x["templateId"].startswith("BREAD_MOVE_LEVEL_SETTINGS_"):
            cost[x["templateId"].removeprefix("BREAD_MOVE_LEVEL_SETTINGS_")] = max(
                sum(lv.get("xlCandyCost", 0) for lv in g[k]) for k in ("aSettings", "bSettings", "cSettings"))
    out = {}
    for x in gm:
        grp = (x["data"].get("pokemonSettings") or {}).get("breadTierGroup")
        if grp and (m := re.match(r"V(\d{4})_POKEMON_", x["templateId"])) and grp in cost:
            d = str(int(m.group(1)))
            out[d] = max(out.get(d, 0), cost[grp])
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def dmax_need(m, ok):
    """{sid: Candy XL the account wants for it} for each ok one that can Dynamax, or evolves into one that can: XL_CAP
    plus what one Max Move costs (the most of the ones it can become). Read by verdict.py's Dynamax rule"""
    can = set(can_dynamax())
    f = base.newest(HERE, "maxmove-xl-[0-9]*[0-9].json")
    if not f:
        raise NoData("no maxmove-xl yet: python3 tradeable.py refresh")
    xl = {int(d): n for d, n in json.load(open(f)).items()}
    most = max(n for d, n in xl.items() if d != 890)  # (one not in the file: the costliest group, Eternatus left out)
    out = {}
    for s in ok:
        costs = [xl.get(m.dex(x), most) for x in m.down(s) if m.dex(x) in can]
        if costs:
            out[s] = XL_CAP + max(costs)
    return out


def hard_evolutions(gm):
    """PokeMiners' game master -> {speciesId: why}: evolving into it costs HARD_CANDY+ candy, a quest or an item, or
    it evolves from something in the main games but can't be evolved into in GO yet (Kleavor, Alolan Marowak)"""
    sid_of = {}  # a PokeMiners form (or a formless pokemonId) -> its PvPoke id, the shortest one first
    for sid, p in sorted(pvp.PLAIN.items(), key=lambda kv: len(kv[0])):
        sid_of.setdefault(p["form"] or p["template"].split("_POKEMON_", 1)[1], sid)
    out, reached = {}, set()
    for x in gm:
        for b in (x["data"].get("pokemonSettings") or {}).get("evolutionBranch") or []:
            if "evolution" not in b or b.get("temporaryEvolution"):
                continue
            forms = [b.get("form"), f"{b['evolution']}_NORMAL", b["evolution"]]  # (an odd form: the species)
            sid = next((sid_of[f] for f in forms if f in sid_of), None) or \
                next((s for f, s in sid_of.items() if f.startswith(f"{b['evolution']}_")), None)
            if not sid:
                print(f"no {forms[0] or forms[2]} in the game data")
                continue
            reached.add(pvp.SPECIES[sid]["template"])  # (by template: lanturnw is Lanturn)
            item = b.get("evolutionItemRequirement") or b.get("lureItemRequirement") or ""
            why = [w for w, ok in [(f"{b.get('candyCost')} candy", (b.get("candyCost") or 0) >= HARD_CANDY),
                                   ("quest", b.get("questDisplay")),
                                   (item.removeprefix("ITEM_").lower().replace("_", " "), item)] if ok]
            if why:
                out.setdefault(sid, ", ".join(why))
    m = Model()
    for sid in m.by:
        par = m.parent_of(sid)
        if par and m.by[sid]["template"] not in reached and m.by[sid].get("released") and \
                "duplicate" not in m.by[sid].get("tags", []):
            out.setdefault(sid, f"can't evolve into it from {m.by[par]['speciesName']} in GO yet")
    return out


# ---------- the family model ----------

class Model:
    def __init__(self):
        self.by, self.parent = dex.evo_tree()
        self.kids = {}
        for c, p in self.parent.items():
            self.kids.setdefault(p, []).append(c)

    def down(self, sid):
        """sid and every evolution after it"""
        out, stack = [], [sid]
        while stack:
            s = stack.pop()
            out.append(s)
            stack += self.kids.get(s, [])
        return out

    def root(self, sid):
        a = dex.ancestors(sid, self.parent)
        return a[-1] if a else sid

    def family(self, sid):
        return self.down(self.root(sid))

    def dex(self, sid):
        return self.by[sid]["dex"]

    def terms(self, sid):
        return dex.form_terms(sid, self.by)

    def parent_of(self, sid):
        """what it evolves from, in GO or (gamemaster 'parent', for one GO can't evolve into yet) in the main games"""
        return pvp.kin_parent(sid)

    def stage(self, sid):
        """0 for a family's first, 1 after one evolution, 2 after two, counting evolutions GO doesn't have yet. A baby
        isn't a stage: Raichu is 1"""
        n, seen = 0, {sid}
        while (sid := self.parent_of(sid)) and sid not in seen:
            seen.add(sid)
            n += self.dex(sid) not in BABIES
        return n

    def special(self, sid):
        return any(t in (self.by[sid].get("tags") or []) for t in SPECIAL)

    def tradeable(self, sid):
        return self.dex(sid) not in dex.NEVER_TRADED and not re.search(r"_shadow|_mega|_primal", sid)


def luckydex(m, missing):
    """-> {sid: gender term or ''}: a new lucky copy of sid fills a missing number, itself or by evolving"""
    out = {}
    for sid in m.by:
        need = set()
        for d in m.down(sid):
            if m.dex(d) in missing:
                r = dex.route(sid, d, m.parent, m.by) if d != sid else (set(), None)
                if r:
                    need.add(r[1] or "")
        if need:
            out[sid] = "" if "" in need or len(need) > 1 else need.pop()  # both genders fill something: any copy
    return out


# ---------- read: HashTagAJay's candy ----------

def families_by_dex(m):
    """[(lowest dex, every dex in the family)], one per family, by lowest dex. Candy goes by dex number: regional
    forms share it (Meowth, Galarian Meowth and Perrserker are one family)"""
    fam = {}
    for sid in m.by:
        ds = {m.dex(x) for x in m.family(sid)}
        for d in list(ds):
            ds |= fam.get(d, set())
        for d in ds:
            fam[d] = ds
    out = {min(ds): sorted(ds) for ds in fam.values()}
    return sorted(out.items())


def cmd_read(resume=None):
    """resume: a stopped run's searches.json, so its searches aren't typed again"""
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="read")
    who = home.trainer()
    if who not in (TAKER, GIVER):
        raise Stop(f"signed in as {who!r}: read needs {TAKER} (or {GIVER}, for plan --to {GIVER})")
    dex.save_trainer(who)
    home.start()
    cache = json.load(open(resume)) if resume else {}
    saved = os.path.join(base.RUN_DIR, "searches.json")
    n = tagsheet.counter(cache, lambda q, c: base.write_json(saved, cache, indent=0),  # saved as it goes
                         edit=True, live=True)  # (like roster: edit the last search's end, count with the keyboard up)
    m = Model()
    fams = families_by_dex(m)
    chunks = [fams[i:i + 20] for i in range(0, len(fams), 20)]  # 20 families: a short search, and fewer splits
    seen = [0, 0]
    lucky = [h for c in chunks for h in tagsheet.group_hits(c, "lucky&", f"countcandy0-{LUCKY_CANDY - 1}", n, seen)]
    log(f"lucky, under {LUCKY_CANDY} candy: {lucky}")
    seen = [0, 0]
    xl = [h for c in chunks for h in tagsheet.group_hits(c, "", f"countcandyxl{XL_CAP}-", n, seen)]
    log(f"{XL_CAP}+ Candy XL: {xl}")
    out = {"trainer": who, "lucky_low_candy": lucky, "xl_full": xl}
    base.write_json(os.path.join(base.RUN_DIR, "read.json"), out, indent=1)


# ---------- plan ----------

def newest_for(pattern, who, key="trainer", default=None):
    """the newest runs/<pattern> json whose key is who (one without the key counts as default's)"""
    import glob
    for f in sorted(glob.glob(os.path.join(HERE, "runs", pattern)), reverse=True):
        if json.load(open(f)).get(key, default) == who:
            return f
    return None


def raid_tops(m, n=PVE_TOP, real=False, megas=True):
    """-> ({sid: [bosses]}, {sid in some top as itself}, roster.Model): roster.raid_tops over the tradeable species
    (real: 4-star raid bosses or higher; megas=False: a mega takes its spot but counts for no one)"""
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    return roster.raid_tops(m.tradeable, n, real=real, megas=megas)


_STRONG = {}  # {megas: {sid: why}}


def strong_lines(m, megas=True):
    """-> {sid: why}: every species of m in a strong line (/ivc's sort.strong, the one copy of the rule: on the ideal
    raid team against some 4-star+ boss, released or not, or a gym defender's line). Not kept and not a special trade:
    Reroll, on both accounts' piles (the user, 2026-11-19). verdict.py's strong-line shadows read it too.
    megas=False: a line on the ideal team only as a mega isn't strong (CyrillJan's Reroll, the user 2026-11-20)"""
    if megas not in _STRONG:
        sys.path.append(os.path.join(HERE, "..", "ivc"))
        import sort
        got_ = _STRONG[megas] = {}
        for s in m.by:
            if s not in sort.SPECIES:
                continue
            for line in sort.family(s):
                if s in line and (got := sort.strong(tuple(line), megas))[0]:
                    got_[s] = "strong line: " + got[1]
                    break
    return _STRONG[megas]


def pve(m, enough=lambda s, mega_only: False, n=PVE_TOP, **kw):
    """-> ({sid: why}, {sid: why dropped}): a traded copy (never shadow) would be in DialgaDex's top n against
    some raid boss, or evolve into one that is. Special trades left out of the top: they're never tagged. A mega counts
    as its species. enough(sid, only in as a mega) -> why the taker needs no more of it, or None"""
    tops, plain, rm = raid_tops(m, n, **kw)
    out, dropped = {}, {}
    for s, bs in tops.items():
        if s not in m.by:
            continue
        if why := enough(s, s not in plain):
            dropped[s] = why
            continue
        for x in [s, *rm.ancestors(s)]:
            out.setdefault(x, []).extend(bs)
    why = {s: "top %d vs %s" % (n, ", ".join(bs[:3]) + (f" +{len(bs) - 3}" if len(bs) > 3 else ""))
           for s, bs in out.items() if s in m.by}
    return why, dropped


def queries(m, sids, gender=None, room=40):
    """species forms -> ['&<dexes><form terms>', ...], each under MAX_SUFFIX characters with room left for the tag
    terms"""
    groups = {}
    for s in sids:
        g = (gender or {}).get(s, "")
        groups.setdefault(m.terms(s) + (f"&{g}" if g else ""), set()).add(m.dex(s))
    out = []
    for terms, ds in sorted(groups.items()):
        part = []
        for r in dex.ranges(ds):
            if part and len(",".join(part + [r])) + len(terms) + 1 > MAX_SUFFIX - room:
                out.append(f"&{','.join(part)}{terms}")
                part = []
            part.append(r)
        out.append(f"&{','.join(part)}{terms}")
    return out


def evolved_giv(m, ok, why, hard):
    """-> {sid: why} for the GIV (evolved) rule: stage 2, a hard stage 1 (hard: giv-evolved-<date>.json) or a gym
    defender, of the ok ones not in why. Tagged GIV only after the level 26+ walk: that one wins over these"""
    out = {}
    for s in ok:
        if s not in why:
            if m.stage(s) >= 2:
                out[s] = "stage 2"
            elif m.stage(s) == 1 and s in hard:
                out[s] = f"stage 1, {hard[s]}"
            elif s in GYM_DEFENDERS:
                out[s] = "gym defender"
    return out


class NoData(Exception):
    """a file the species lists need isn't there yet"""


def cyrill_species(m):
    """CyrillJan's pile, judged for HashTagAJay. Reroll: a strong line (strong_lines, the same rule as HashTagAJay's
    pile), or a new copy would be in HashTagAJay's own top 6 against some raid boss (roster.json: #1 or #2-#6).
    CyrillJan trades only to HashTagAJay, so a Reroll is only for a 100 HashTagAJay still needs (the user, 2026-11-20):
    a place won only as a mega counts for nothing (one 100 is enough there: the ★100% hole rule's Reroll), and a family
    HashTagAJay holds REROLL_ENOUGH 100s of gets no strong-line or raid-attacker Reroll. Either can still get a Reroll
    from the ★100% hole, PvP, lucky-family or REROLL_FOR_TAKER rules, or 2XL or GIV (candy, distance, ...)
    -> {"why": {sid: (tag, why)}, "lucky": {sid: gender term},
    "evolved": {sid: why}, "xl_full": {dex}, "from": {what: file}}. Shared by plan and ../shared/verdict.py"""
    lucky_missing, lucky_run = dex.latest("lucky", TAKER)  # (an evolve-lucky run counts too)
    hund_missing, hund_run = dex.latest("100", TAKER)
    roster_f = newest_for(os.path.join("..", "..", "roster", "runs", "*", "roster.json"), TAKER, default=TAKER)
    read_f = newest_for(os.path.join("*-read", "read.json"), TAKER)
    pvp_f = base.newest(HERE, "pvp-giv-*.json")
    hard_f = base.newest(HERE, "giv-evolved-*.json")
    lacking = [n for n, v in [("a lucky /dex run", lucky_run), ("a ★100% /dex run", hund_run),
                              ("roster.json", roster_f), ("read.json", read_f), ("pvp-giv", pvp_f),
                              ("giv-evolved (python3 tradeable.py refresh)", hard_f)] if not v]
    if lacking:
        raise NoData(f"no {', '.join(lacking)} for {TAKER} yet")
    roster = json.load(open(roster_f))
    read = json.load(open(read_f))
    pvp_giv = json.load(open(pvp_f))

    ok = [s for s in m.by if m.tradeable(s) and not m.special(s)]
    lucky = luckydex(m, set(lucky_missing))
    if "reroll_plain" not in roster:
        raise NoData(f"{roster_f} is from before megas were split out: python3 ../roster/roster.py report "
                     f"{os.path.join(os.path.dirname(roster_f), 'counts.json')}")
    reroll = {s for s in roster["reroll_plain"] if s in m.by}
    hund_owned = dex.owned_100(hund_run)
    if hund_owned is None:  # (the page alone would count 100s gone since as copies: the Magnemite of 2026-11-19)
        raise NoData(f"the newest ★100% /dex run of {TAKER} has no count of its 100s yet: "
                     f"POGO_PHONE=android python3 ../dex/dex.py evolve 100, signed in as {TAKER}")
    fam_100 = Counter()
    for s, n in hund_owned.items():
        if s in m.by:
            fam_100[m.root(s)] += n
    for r, n in team_100s(TAKER, m).items():  # (the ★100% run counts only lines with a hole: 6 Rhyperior read as 0,
        fam_100[r] = max(fam_100[r], n)  # the user 2026-11-23. Both are counts of real copies, so the bigger one)
    why = {}
    for s in ok:
        if s in lucky:
            why.setdefault(s, ("Luckydex", "lucky dex hole"))
    strong = strong_lines(m, megas=False)
    import sort  # (strong_lines put /ivc on the path)
    for s in ok:
        if any(s.startswith(c) for c in sort.COLLECT):  # never Reroll; GIV till the patterns are told apart (a pattern
            why.setdefault(s, ("GIV", "pattern collection"))  # HashTagAJay has no 100 of is wanted: the user, 2026-11-20)
            continue
        if fam_100[m.root(s)] >= REROLL_ENOUGH:
            continue  # (HashTagAJay has enough 100s of the family: no Reroll)
        if s in strong:
            why.setdefault(s, ("Reroll", strong[s]))
        elif s in reroll:
            why.setdefault(s, ("Reroll", "#1 raid attacker: " + ", ".join(roster["species"][s]["bosses"][:3])))
        elif s in roster["giv_plain"]:  # (was GIV: #2-#6 is a Reroll too, the user 2026-11-19)
            why.setdefault(s, ("Reroll", "#2-#6 raid attacker"))
    hund = dex.hundred_useful(set(hund_missing), hund_owned, m.by, m.parent)
    low = {m.root(s) for s in m.by if m.dex(s) in read["lucky_low_candy"]}
    for s in ok:  # (all three were GIV till 2026-11-23: HashTagAJay needs them, so Reroll. GIV is now what CyrillJan
        if s in hund:  # needs the trade's candy for: verdict.cyrill_short. The user)
            why.setdefault(s, ("Reroll", "★100% hole"))
        elif s in pvp_giv:
            why.setdefault(s, ("Reroll", "PvP " + " ".join(pvp_giv[s])))
        elif m.root(s) in low:
            why.setdefault(s, ("Reroll", f"lucky family under {LUCKY_CANDY} candy"))
        elif s in REROLL_FOR_TAKER:
            why.setdefault(s, ("Reroll", REROLL_FOR_TAKER[s]))
    evolved = evolved_giv(m, ok, why, json.load(open(hard_f)))
    team_xl, team_f = team_xl_need(m, ok, GIVER)
    return {"why": why, "lucky": lucky, "evolved": evolved, "dmax": dmax_need(m, ok), "team_xl": team_xl,
            "team_line": team_lines(m),
            "xl_full": {m.dex(x) for s in m.by if m.dex(s) in read["xl_full"] for x in m.family(s)},
            "from": {"lucky": lucky_run, "100": hund_run, "roster": roster_f, "read": read_f, "pvp": pvp_f,
                     "evolved": hard_f, "team100": team_f}}


def build_plan(m):
    """every search tag runs, from the newest /dex, /roster and read data (made fresh each run: no plan step).
    -> (plan, cyrill_species' answer). NoData if a data file isn't there yet"""
    sp = cyrill_species(m)
    why, lucky, evolved = sp["why"], sp["lucky"], sp["evolved"]
    plan = {"taker": TAKER, "xlx_level": XLX_FOR[TAKER], "from": sp["from"],
            "tags": {t: queries(m, [s for s, (w, _) in why.items() if w == t], lucky if t == "Luckydex" else None,
                                room=len(BULK) + 10) for t in TAGS},
            "2xl": queries(m, sorted(s for s in pve(m)[0] if s in m.by), room=len(BULK) + len(UNDER_360_XL) + 20),
            "giv_evolved": queries(m, evolved, room=len(BULK_REST) + 10) + [DYNAMAX],
            "taker_xl_full": sorted(sp["xl_full"])}
    return plan, sp


def cmd_plan(to=TAKER):
    """only a preview (plan.md) of the searches tag would run: tag makes its own, nothing reads this"""
    if to != TAKER:
        sys.exit(f"plan is for {TAKER} only (the door judges for {GIVER}: ../shared/verdict.py)")
    m = Model()
    try:
        plan, sp = build_plan(m)
    except NoData as e:
        sys.exit(str(e))
    why, evolved = sp["why"], sp["evolved"]
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="plan")
    base.write_json(os.path.join(base.RUN_DIR, "plan.json"), plan, indent=1)
    lines = [f"# Tradeable plan {time.strftime('%Y-%m-%d %H:%M')}", ""]
    lines += [f"- {k}: {v}" for k, v in plan["from"].items()] + [""]
    for t in TAGS:
        lines += [f"## {t}: {sum(1 for w, _ in why.values() if w == t)} species forms", ""]
        lines += [f"- {m.by[s]['speciesName']} (#{m.dex(s)}): {r}"
                  for s, (w, r) in sorted(why.items(), key=lambda x: m.dex(x[0])) if w == t]
        lines += ["", "Searches (after the Tradeable search):", ""] + [f"    {q}" for q in plan["tags"][t]] + [""]
    lines += [f"## GIV (evolved, only after the level 26+ walk): {len(evolved)} species forms", "",
              "Stage 2, a stage 1 that takes 100+ candy, a quest or an item, a gym defender, or (the last search) an "
              "untraded Dynamax one. Tagged after the level 26+ walk, so a level 26+ one gets GIV there first. Special trades "
              "(Legendary, Mythical, Ultra Beast, shiny, Gigantamax) get no tag at all: they're for you to trade.", ""]
    lines += [f"- {m.by[s]['speciesName']} (#{m.dex(s)}): {r}" for s, r in sorted(evolved.items(), key=lambda x: m.dex(x[0]))]
    lines += ["", f"Searches (after the Tradeable search, with {EVOLVED_REST}):", ""]
    lines += [f"    {q}" for q in plan["giv_evolved"]] + [""]
    open(os.path.join(base.RUN_DIR, "plan.md"), "w").write("\n".join(lines))
    log(f"plan: {', '.join(f'{t} {len(q)} searches' for t, q in plan['tags'].items())}, "
        f"evolved GIV {len(plan['giv_evolved'])} searches -> {base.RUN_DIR}")


def can_dynamax():
    """dex numbers that can Dynamax (refresh's dynamax-<date>.json: pvp.can_dynamax)"""
    got = pvp.can_dynamax()
    if got is None:
        sys.exit("no dynamax-<date>.json yet: python3 tradeable.py refresh")
    return got


def cmd_dynamax():
    """either account signed in: how many Dynamax ones it has of each family that can Dynamax (only searches).
    dynamax.json says whose count it is"""
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="dynamax")
    who = home.trainer()
    log(f"counting {who}'s Dynamax ones")
    m, can = Model(), can_dynamax()
    home.start()
    n = tagsheet.counter({}, lambda q, c: log(f"  {q}: {c}"), edit=True, live=True)
    out = {}
    for lo, ds in families_by_dex(m):
        if can & set(ds):
            out[lo] = n(",".join(dex.ranges(ds)) + "&dynamax")
            base.write_json(os.path.join(base.RUN_DIR, "dynamax.json"), {"trainer": who, "families": out})
    log(f"{sum(1 for v in out.values() if v)} of {len(out)} families have a Dynamax one -> {base.RUN_DIR}")


def hashtag_species(m):
    """HashTagAJay's pile (Leftovers), judged for CyrillJan or the user's wife's account: what's good for any account
    (the user, 2026-11-16) -> {"why": {sid: (tag, why)}, "evolved": {sid: why}, "hard": {sid: why}, "by_hand": {sid},
    "xl_full": {dex}, "from": {what: file}}. Read by ../shared/verdict.py
      Reroll: a new 100 is worth having: a strong line (strong_lines), DialgaDex's top PVE_TOP against a boss like a
        4-star raid's or higher (real_boss; #2-#6 was GIV, the user 2026-11-19), or PvPoke's Master League top REROLL_ML
        (each with the earlier stages that evolve into it). The two raid reasons (the ideal team, the top PVE_TOP) only
        while some copy of the line could still make one of CyrillJan's Team Potentials (no_team_b: its newest whole count).
        One that's in only as a Mega counts only till CyrillJan has a 100 of it (cyrill_has_100: one Mega is enough)
        Also a line that could make one of CyrillJan's own Team Potentials (cyrill_potentials: a trade rolls new IVs, so the
        species decides, the user 2026-11-23), even when it's in no DialgaDex top; one in only as a Mega, only till
        CyrillJan has a 100 of it
      hard (GIV, after 2XL and the level 26+ GIV): the family of a 10 or 12 km egg hatch (refresh's eggs-<date>.json), Smeargle, and
        a gym defender's line (/ivc's GYM_DEFENDERS and what evolves into them: a potential top gym defender for an
        account with fewer, the user 2026-11-16)
      dmax: what dmax_need says (a Dynamax one, or one that can Dynamax while this account is short: verdict.py)
      cyrill_xl {sid: (CyrillJan's Candy XL of its family, when it was read)}: the Pokémon database's last read.
        cyrill_team_xl: team_xl_need for CyrillJan's 100s. The level 26+ GIV asks both (verdict.cyrill_xl_full)
      by_hand: likely special trades the user tags by hand: regionals (PvPoke's tag + rules.BY_HAND, less
        rules.SF_NATIVE: they spawn in San Francisco) and Spinda
    (An Adventure Effect move would be a Reroll, but only legendaries and Ultra Beasts have one: special trades)"""
    read_f = newest_for(os.path.join("*-read", "read.json"), GIVER)  # (only its 360+ XL families: none without)
    xl_full = json.load(open(read_f))["xl_full"] if read_f else []
    pvp_f = base.newest(HERE, "pvp-giv-*.json")
    hard_f = base.newest(HERE, "giv-evolved-*.json")
    eggs_f = base.newest(HERE, "eggs-[0-9]*[0-9].json")
    if lacking := [n for n, f in [("pvp-giv", pvp_f), ("giv-evolved", hard_f), ("eggs", eggs_f)] if not f]:
        raise NoData(f"no {', '.join(lacking)} yet: python3 tradeable.py refresh")
    ok = {s for s in m.by if m.tradeable(s) and not m.special(s)}
    why = {}

    def add(tag, picked):
        """picked: {sid: why} -> each one and the earlier stages that evolve into it, unless an earlier rule has it"""
        for s, r in picked.items():
            for x in [s, *dex.ancestors(s, m.parent)]:
                if x in ok:
                    why.setdefault(x, (tag, r))
    count_f, gone = no_team_b(m)
    has_100 = cyrill_has_100(m)
    plain = strong_lines(m, megas=False)
    add("Reroll", {s: r for s, r in strong_lines(m).items() if " on the ideal team " not in r
                   or (not gone(s) and (s in plain or not has_100(r.split()[2])))})
    enough = lambda s, mega_only: f"{GIVER} has a 100" if mega_only and has_100(s) else None
    add("Reroll", {s: r for s, r in pve(m, enough, real=True)[0].items() if not gone(s)})  # (it has the earlier stages)
    add("Reroll", {s: f"could make {GIVER}'s Team Potential (IV sum {b}+ at level 50)"
                   for s, (b, mega_only) in cyrill_potentials(m).items() if not (mega_only and has_100(s))})
    ml = {s: int(r.split("#")[1]) for s, rs in json.load(open(pvp_f)).items() for r in rs if r.startswith("10000:")}
    add("Reroll", {s: f"Master League #{r}" for s, r in ml.items() if r <= REROLL_ML and s in m.by})
    eggs = json.load(open(eggs_f))
    hard = {}
    for km in HARD_EGGS:
        for s in eggs.get(km, []):
            hard.update({x: f"{km} egg ({m.by[s]['speciesName']})" for x in m.family(s) if x in ok and x not in hard})
    for s in HARD_TO_FARM:
        hard.update({x: "hard to farm" for x in m.family(s) if x in ok and x not in hard})
    for s in sorted(GYM_DEFENDERS):  # (after 2XL and the level 26+ GIV, the user 2026-11-16)
        hard.update({x: "a gym defender's line: a top one for an account with fewer" for x in m.family(s)
                     if x in ok and x not in hard})
    by_hand = set()
    for s in m.by:
        if "regional" in (m.by[s].get("tags") or []) or s in BY_HAND:
            by_hand |= {s, *(x for x in dex.ancestors(s, m.parent) if m.dex(x) not in BABIES)}
    by_hand -= SF_NATIVE  # (caught in San Francisco: judged like any other)
    team_xl, team_f = team_xl_need(m, ok, TAKER)
    cyrill_bar, cyrill_team_f = team_xl_need(m, ok, GIVER)
    counts = pokedb.candies(GIVER)
    cyrill_xl = {s: (c["xl"], c["xl_at"]) for s in ok if (c := counts.get(pvp.candy_family(s))) and c["xl"] is not None}
    return {"why": why, "evolved": evolved_giv(m, ok, why, json.load(open(hard_f))), "hard": hard, "by_hand": by_hand,
            "dmax": dmax_need(m, ok), "team_xl": team_xl, "cyrill_xl": cyrill_xl, "cyrill_team_xl": cyrill_bar,
            "xl_full": {m.dex(x) for s in m.by if m.dex(s) in xl_full for x in m.family(s)},
            "from": {"read": read_f, "pvp": pvp_f, "evolved": hard_f, "eggs": eggs_f, "raidteam": count_f,
                     "team100": team_f, "cyrill_team100": cyrill_team_f}}


def no_team_b(m):
    """-> (the teams.json of CyrillJan's newest whole /raidteam count or None, gone(sid)). gone: no copy of sid's line
    from sid on, not even a 100 at level 50, could make any of CyrillJan's Team Potentials (bars50 None for every one the
    count has), so a raid reason for a Reroll is gone (the user, 2026-11-22: HashTagAJay's pile goes to CyrillJan).
    A traded copy is never a shadow: the plain piles only. No count, or a line the count doesn't have: never gone"""
    import raidteams
    b50 = (raidteams.newest(GIVER)[0] or {}).get("bars50", {})

    def gone(sid):
        xs = [x for x in m.down(sid) if x in b50]
        return bool(xs) and all(b50[x] is None for x in xs)
    return raidteams.path_of(GIVER), gone


def cyrill_potentials(m):
    """-> {sid: (the lowest IV sum that could make it, mega only)}: species a traded copy of could make one of
    CyrillJan's Team Potentials (bars50 not None in its newest whole /raidteam count; not a shadow pile: a shadow can't
    be traded). A trade rolls new IVs, so the species decides, not the copy's IVs (the user, 2026-11-23: HashTagAJay's
    Transfer pile held some). mega only: it can Mega Evolve (mega_sids) and no copy holds a Team Potential spot as
    itself, so one 100 is enough there (cyrill_has_100, the user 2026-11-22). No count: none"""
    import raidteams
    t = raidteams.newest(GIVER)[0] or {}
    copies = t.get("copies", [])
    plain_on, mega_on = set(), set()
    for boss, team in t.get("bosses", {}).items():
        if boss.endswith(", level 50)"):
            for e in team:
                for x in copies[e["copy"]]["species"] if e["copy"] < len(copies) else ():
                    if not e["attacker"].startswith("Shadow "):  # (a shadow's spot: a trade gives no shadow)
                        (mega_on if e["attacker"].startswith(("Mega ", "Primal ")) else plain_on).add(x)
    megas = mega_sids() if t else set()
    return {k: (b, k in (megas | mega_on) and k not in plain_on) for k, b in t.get("bars50", {}).items()
            if b is not None and "|" not in k and k in m.by}


def mega_sids():
    """species that can Mega or Primal Evolve (DialgaDex's attackers). A pile's bars50 doesn't hold to the one mega a
    team: a mega species' bar can be a spot only its mega wins"""
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    rm = next(roster.load_models(roster.COUNTERS[:1]))
    return {s for a, s in zip(rm.A, rm.sid) if s and roster.is_mega(a)}


def team_100s(who, m):
    """-> Counter {family root: copies}: the 100s (15/15/15 its only IV read, not a shadow) in who's newest whole
    /raidteam count. It reads every copy of a raid attacker's line, hole or not. No count: empty"""
    import raidteams
    copies = (raidteams.newest(who)[0] or {}).get("copies", [])
    copies = copies.values() if isinstance(copies, dict) else copies
    return Counter(m.root(c["species"][0]) for c in copies
                   if not c["shadow"] and c["ivs"] == [[15, 15, 15]] and c["species"] and c["species"][0] in m.by)


def cyrill_has_100(m):
    """-> has_100(sid): CyrillJan's newest whole /raidteam count has a 100 (15/15/15, not a shadow) of sid or of a
    stage that evolves into it. A Mega spot needs one copy: a line that's in only as a Mega (on the ideal team or in
    the top PVE_TOP) is no Reroll once CyrillJan has a 100 of it (the user, 2026-11-22). A copy whose IVs the count
    didn't read counts as no 100, so a line stays Reroll till a count reads it. No count: never a 100"""
    import raidteams
    copies = (raidteams.newest(GIVER)[0] or {}).get("copies", [])
    copies = copies.values() if isinstance(copies, dict) else copies
    got = {s for c in copies if not c["shadow"] and [15, 15, 15] in (c["ivs"] or []) for s in c["species"]}
    return lambda sid: any(x in got for x in [sid, *dex.ancestors(sid, m.parent)])


def team_picks(m):
    """-> {sid: [bosses]}: the #1 non-mega picks of Team Future and Team Ideal (roster.ideal_firsts, megas=False) that
    trade. Each team holds TEAM_SLOTS of one; a mega's one spot needs one 100, so it raises no bar"""
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    out = {}
    for pulls in (roster.IDEAL, roster.COUNTERS):
        for s, bosses in roster.ideal_firsts(pulls, megas=False).items():
            if s in m.by and m.tradeable(s) and not m.special(s):
                have = out.setdefault(s, [])
                have += [b for b in bosses if b not in have]
    return out


def team_lines(m):
    """-> the tradeable species of every family with a species on Team Future or Team Ideal (roster.ideal_firsts, its
    megas too) or on one of CyrillJan's Team Availables or Team Potentials (its newest whole /raidteam count). Only these
    lines want XL_CAP Candy XL on CyrillJan: a trade's XL for any other line isn't worth the trade (verdict.cyrill_short,
    the user 2026-11-23). None: CyrillJan has no whole /raidteam count yet"""
    import raidteams
    t = raidteams.newest(GIVER)[0]
    if t is None:
        return None
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    on = set()
    for pulls in (roster.IDEAL, roster.COUNTERS):
        on |= set(roster.ideal_firsts(pulls))
    copies = t.get("copies", [])
    for team in t.get("bosses", {}).values():
        for e in team:
            if e["copy"] < len(copies):
                on |= set(copies[e["copy"]]["species"])
    return {s for x in on if x in m.by for s in m.family(x) if m.tradeable(s) and not m.special(s)}


TEAM100 = os.path.join("*", "team100.json")  # (a team100 run, or a specieswise run that counted first)


def team_xl_need(m, ok, who):
    """-> ({sid: [Candy XL who wants, the pick, its 100s] or None}, the team100.json read or None). who: the account
    holding the pile (either one: the user, 2026-11-23). Every species of a pick's family (the family shares its Candy
    XL) wants XL_CAP for each 100 of the pick (or of a stage that evolves into it) in who's newest team100 count, up
    to TEAM_SLOTS. The family's highest bar wins. Only bars over XL_CAP are listed. None: a pick the count doesn't
    have (verdict: not sure)"""
    f = newest_for(TEAM100, who)
    counts = json.load(open(f))["counts"] if f else {}
    ok, out = set(ok), {}
    for p in sorted(team_picks(m)):
        n = counts.get(p)
        bar = None if n is None else XL_CAP * min(n, TEAM_SLOTS)
        if bar is not None and bar <= XL_CAP:
            continue
        for s in m.family(p):
            if s not in ok or (s in out and out[s] is None):
                continue
            if bar is None or s not in out or out[s][0] < bar:
                out[s] = None if bar is None else [bar, p, n]
    return out, f


def cmd_team100():
    """either account signed in: count_team100. Only searches"""
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="team100")
    count_team100(home.trainer())


def count_team100(who):
    """the 4* count of each team_picks pick with the stages that evolve into it, shadow or not (queries' form terms)
    -> {pick: 100s}, also in <run folder>/team100.json. who: the account signed in"""
    m = Model()
    search.to_search_list()
    counts = {}
    for p in sorted(team_picks(m)):
        n = 0
        for q in queries(m, [p, *dex.ancestors(p, m.parent)]):
            got = search.result_count(search.start_search("4*" + q)[1])
            if got is None:
                raise Stop(f"no result count read for 4*{q}")
            n += got
        counts[p] = n
        log(f"team100: {p}: {n}")
    f = os.path.join(base.RUN_DIR, "team100.json")
    base.write_json(f, {"trainer": who, "counted": time.strftime("%Y-%m-%d %H:%M"), "counts": counts}, indent=1)
    log(f"team100: {f}")
    return counts


# ---------- tag (CyrillJan's Tradeable) ----------

# every tag search and walk leaves special trades out: the user trades them by hand
NOT_TAGGED = NO_SPECIAL + "".join(f"&!#{t}" for t in TAGS)
BULK = NOT_TAGGED + TAG_SKIP  # what a tag search may touch: TAG_SKIP's ones wait for the door
REST = NOT_TAGGED + f"&!#{TRANSFER}"  # not tagged yet (a level 26+ one gets GIV: NOT_TAGGED leaves it out)
EVOLVED_REST = REST + "&traded,!xxs"  # and not a never-traded XXS one (those get IVC)
BULK_REST = EVOLVED_REST + TAG_SKIP


def cyrill_short_searches(team_xl=None, m=None, team_line=None):
    """the last GIV searches, after the far one: never traded, and CyrillJan has under XL_CAP Candy XL of a team line
    (cyrill_species' team_line: team_lines) or under LUCKY_CANDY Candy of the family (verdict.cyrill_short). Then each
    Team Future/Ideal bar (cyrill_species' team_xl): those families, under their bar. A family whose 100s weren't
    counted gets none, nor does any line with no raid team count (team_line None): the door judges it"""
    out = [q + "&!traded" + UNDER_360_XL for q in (queries(m, sorted(team_line)) if team_line else [])]
    out += ["&!traded" + UNDER_348_CANDY]
    bars = {}
    for s, v in (team_xl or {}).items():
        if v:
            bars.setdefault(v[0], []).append(s)
    for bar, sids in sorted(bars.items()):
        out += [q + f"&!traded&countcandyxl0-{bar - 1}" for q in queries(m, sids)]
    return out


def size_search(size):
    """a never-traded XXS one is renamed and tagged IVC, never GIV or Transfer"""
    return REST + TAG_SKIP + f"&!#{sizes.IVC}&!traded&{size}"


def bulk_searches(plan):
    """the tag searches, in verdict.py's order -> [(tag, the species part, the rest of the suffix)]. Tradeable's !# drops
    whatever gets a tag out of the later ones"""
    tags = plan["tags"]
    return ([(GUARANTEED, "", BULK + LUCKY_YEAR)]
            + [("Luckydex", q, BULK) for q in tags["Luckydex"]]
            + [(OLD, "", BULK + OLD_AGE)]
            + [("2XL", q, BULK + "&!xxs" + UNDER_360_XL) for q in plan["2xl"]]  # (a count term goes last)
            + [("2XL", "", BULK + "&!xxs" + DYNAMAX + UNDER_360_XL)]  # a Dynamax one, raid line or not (2026-11-16)
            + [(t, q, BULK) for t in ("Reroll", "GIV") for q in tags[t]])


def keep_xxl_ones(limit):
    """an XXL one in the pile is no trade: a favorite, before any tag search"""
    sizes.walk(lambda: run_pile("&xxl&!favorite"), "xxl", limit)


def run_pile(suffix):
    """the pile's search + suffix -> its count, or None if this account has no Tradeable shortcut"""
    return savedsearch.run_shortcut(SHORTCUT, suffix)


def tag_pile(tag, suffix):
    return savedsearch.tag_pile(SHORTCUT, tag, suffix)


def level_of(info, texts):
    """-> the levels this one can be at, from the power-up cost on the detail page. No taps. A cost on both sides of
    XLX_LEVEL (4,000 at 26) needs its candy, which OCR often misses: a few more looks for it"""
    for _ in range(4):
        lvs = powerup.cost_levels(texts, info["cp"])[1]
        if not lvs or min(lvs) >= XLX_LEVEL or max(lvs) < XLX_LEVEL:
            break
        _, texts, _, _ = look()
    return lvs


def walk(suffix, xlx, power, limit, skip_dex=(), unsure=None):
    """open each one in the pile + suffix: xlx -> tag it GIV if it's XLX_LEVEL+ (the ones it can't tell go in unsure).
    power -> cleantrades' power-up, not for a family in skip_dex. -> power-ups made, or None if --limit stopped it"""
    if not run_pile(suffix):
        return 0
    done = 0
    for info, texts, bounds, seen in details():
        base.OPENED["who"] = base.who(info)  # the swipe moved here on purpose: set_tags checks against this one
        checked = not xlx  # its level is known to be under 26, or it's tagged GIV for it
        try:
            if xlx:
                lvs = level_of(info, texts)
                if lvs and min(lvs) >= XLX_LEVEL:
                    base.set_tags(on=(XLX,), off=(OLD_XLX,))
                    checked = True
                    log(f"{XLX} {info['name']} CP{info['cp']}: level {lvs}")
                    raise Pass(f"tagged {XLX} (level {XLX_LEVEL}+)")
                if not lvs or max(lvs) >= XLX_LEVEL:
                    raise Pass(f"level {lvs or '?'} ({powerup.page_cost(texts)} dust): can't tell if it's {XLX_LEVEL}+, "
                               f"left for a look by hand")
                checked = True
            if skip_dex:
                sids = ui.species_for(info["name"], info["texts"])
                if sids and all(pvp.SPECIES[x]["dex"] in skip_dex for x in sids):
                    raise Pass(f"{TAKER} has {XL_CAP}+ Candy XL of the family")
            if power:
                if done >= limit:
                    log(f"--limit {limit} reached")
                    go("close", "list")
                    return None
                n = powerup.power_up(info, texts)
                done += 1
                for _ in range(10):  # the new CP sparkles for a moment and can read blank
                    info2 = ui.detail_info(wait_for("detail")[1])
                    if info2["cp"] is not None:
                        break
                    time.sleep(0.2)
                info2["cp"] = info2["cp"] or powerup.last_cp  # (the GPS banner can hide the CP)
                seen.add((info2["name"], info2["cp"], info2["hp"]))
                pokedb.changed(base.who(info), base.who(info2))  # the database's record follows the new CP
                log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {n} power-up(s)")
        except (Pass, Skip) as e:
            log(f"pass {info['name']} CP{info['cp']}: {e}")
            if (not checked or isinstance(e, powerup.Unsure)) and unsure is not None:
                unsure.append(f"{info['name']} CP{info['cp']} HP{info['hp']}: {e}")
    go("close", "list")
    return done


SMALL_PILE = 40  # a pile this small is opened once to read its species: searches for species not in it are skipped


def survey():
    """-> the dex numbers in the pile, opening each one once. None if the pile is big (searching is quicker then) or
    one's species can't be told from its name (a nickname): then every search runs"""
    n = run_pile("")
    if not n or n > SMALL_PILE:
        return set() if n == 0 else None
    seen, out = set(), set()
    for info, texts, bounds, seen in details():
        sids = ui.species_for(info["name"], info["texts"])
        if not sids:
            log(f"survey: can't tell the species of {info['name']} CP{info['cp']}: every search runs")
            go("close", "list")
            return None
        out |= {pvp.SPECIES[x]["dex"] for x in sids}
    go("close", "list")
    log(f"survey: {len(seen)} of {n} seen, dex {sorted(out)}: " + ", ".join(f"{a} CP{b}" for a, b, _ in seen))
    if len(seen) < n:  # the walk stopped short: one not seen could need a skipped search
        log("survey: missed some: every search runs")
        return None
    return out


DONE_HOURS = 12  # one sitting of stops and restarts: after that every search runs again (new Pokémon came in)
DONE_F = os.path.join(HERE, "runs", "tagged.json")


def tagged_before(plan):
    """the tag searches an earlier run already did with these same searches, in the last DONE_HOURS (a rerun skips
    them: 14 s each, even at 0). New /dex, /roster or read data makes new searches, so it starts over.
    -> (set of searches done, save())"""
    import hashlib
    key = hashlib.sha1(json.dumps([plan["tags"], plan["2xl"], plan["giv_evolved"]], sort_keys=True).encode()).hexdigest()
    old = json.load(open(DONE_F)) if os.path.exists(DONE_F) else {}
    fresh = old.get("key") == key and time.time() - old.get("at", 0) < DONE_HOURS * 3600
    done = set(old.get("done", [])) if fresh else set()
    at = old["at"] if fresh else time.time()

    def save():
        base.write_json(DONE_F, {"key": key, "at": at, "done": sorted(done)})
    return done, save


def bulk_tag(plan, wanted=lambda q: True):
    """bulk_searches' tag searches, each one SELECT ALL + tag (Tradeable's !# drops the tagged ones from the rest)
    -> (set of searches done, save()), for more tag searches after"""
    done, save_done = tagged_before(plan)
    for t, q, tail in bulk_searches(plan):  # rerun skips them (14 s each, even at 0)
        if q + tail in done or not wanted(q):
            continue
        tag_pile(t, q + tail)
        done.add(q + tail)
        save_done()
    if done:
        log(f"{len(done)} tag search(es) done for these searches (new data or {DONE_HOURS} h starts over)")
    return done, save_done


def cmd_tag(limit):
    global XLX_LEVEL
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="tag")
    who = home.trainer()
    if who != GIVER:
        raise Stop(f"signed in as {who!r}: tag needs {GIVER}")
    to = TAKER
    try:
        m = Model()
        plan, sp = build_plan(m)
    except NoData as e:
        raise Stop(str(e))
    save_plan = os.path.join(base.RUN_DIR, "plan.json")  # what this run tagged by, for the record
    base.write_json(save_plan, plan, indent=1)
    XLX_LEVEL = plan.get("xlx_level", XLX_LEVEL)
    log(f"{who}: tagging for {to} from {plan['from']}, XLX at level {XLX_LEVEL}+")
    search.to_search_list()
    have = survey()  # a small pile: only the searches for species in it run
    wanted = lambda q: have is None or (d := search.dexes_of(q)) is None or bool(d & have)
    done, save_done = bulk_tag(plan, wanted)
    # (the taker's 360+ XL families are passed on the detail page: as '&!<dex>' terms they'd overflow the bar)
    traded = NO_SPECIAL + "&" + ",".join(f"#{t}" for t in TAGS)  # (one tagged before special trades were left out)
    keep_xxl_ones(limit)
    for size in sizes.NAMES:  # first: these get IVC
        q = size_search(size)
        sizes.walk(lambda: run_pile(q), size, 10 ** 9)
    rest = BULK_REST  # (one passed over there stays out of Transfer too)
    unsure, power_ok = [], True
    # power-ups for the tagged ones (the taker transfers them), then GIV (level 26+) and power-ups for the rest
    walks = [(traded, False, True, set(plan["taker_xl_full"])), (rest + UNDER_360_XL, True, True, ()),
             (rest + f"&countcandyxl{XL_CAP}-", True, False, ())]
    for suffix, xlx, power, skip in walks:
        while xlx or (power and power_ok):
            n = len(unsure)
            try:
                if walk(suffix, xlx, power and power_ok, limit, skip, unsure if xlx else None) is None:
                    log("--limit: the rest weren't checked, so nothing is tagged Transfer")
                    return
                break
            except Stop as e:
                if "Stardust" not in str(e) or not power_ok:
                    raise
                log(f"stopped powering up: {e}. Going on with the level 26+ GIV only")
                power_ok = False
                del unsure[n:]  # this walk starts over
                if look()[0] != "list":
                    go("close", "list")
    if unsure:
        log(f"{len(unsure)} couldn't be checked for {XLX_LEVEL}+ or a cheap power-up (the door judges them too):\n  "
            + "\n  ".join(unsure))
    for q in plan.get("giv_evolved", []):  # after XLX: an XLX_LEVEL+ one has XLX by now and stays out
        if rest + q in done or not wanted(q):
            continue
        tag_pile("GIV", rest + q)
        done.add(rest + q)
        save_done()
    tag_pile("GIV", rest + "&!traded&distance100-")  # fits nothing else, but a far trade: GIV
    for q in cyrill_short_searches(sp.get("team_xl"), m, sp.get("team_line")):  # then CyrillJan short of the family's candy: the trade's candy (verdict.cyrill_short)
        tag_pile("GIV", rest + q)
    got = door_walk(EVOLVED_REST, limit, who)  # (it leaves out #GIV. TAG_SKIP's ones are judged here)
    log(f"the rest, through the door: {dict(got)}")


def cmd_door(limit):
    """the tag searches that need no page read first (bulk_first), then the door walk on the rest: the door's rules
    are the plan's, one by one"""
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="door")
    who = home.trainer()
    if who != GIVER:
        raise Stop(f"signed in as {who!r}: door needs {GIVER}")
    home.start()
    bulk_first()
    keep_xxl_ones(limit)
    log(f"the rest, through the door: {dict(door_walk(EVOLVED_REST, limit, who))}")


DOOR_OPEN_S, TAG_SEARCH_S = 30, 14  # what the door takes for each one it opens, and a tag search, even at 0 (2026-11)
BULK_HIT = 0.4  # the share of the door's opens a tag search would have tagged (104 of 263, 2026-11-10 to 11-13)


def bulk_first():
    """before the door: the tag searches that need no page read (bulk_searches: GuaranteedLucky, Luckydex, Old,
    2XL, Reroll, GIV), so the door opens only the rest. The same tags the door gives (tests/taggers.py): 104 of 263
    door opens in 2026-11-10 to 11-13 were 2XL or a ★100% hole GIV, 30 s each. No power-up walk for them: the door
    doesn't power up a 2XL or GIV one either. Skipped when the pile is too small to pay for the searches, or a data
    file is missing (then the door judges them all, as before)"""
    try:
        plan, _ = build_plan(Model())
    except NoData as e:
        log(f"no tag searches first ({e}): the door judges every one")
        return
    n = run_pile("")
    todo = [x for x in bulk_searches(plan) if x[1] + x[2] not in tagged_before(plan)[0]]
    if not n or n * BULK_HIT * DOOR_OPEN_S < len(todo) * TAG_SEARCH_S:
        log(f"no tag searches first: {n} in the pile, {len(todo)} searches cost more than the door's opens")
        return
    base.write_json(os.path.join(base.RUN_DIR, "plan.json"), plan, indent=1)  # what this run tagged by
    log(f"{n} in the pile: {len(todo)} tag searches first, then the door for the rest")
    bulk_tag(plan)


def pile_tiles(suffix, shortcut=SHORTCUT):
    """the pile + suffix, every tile read -> search.run_search's answer ([(name, cp)], the game's count)"""
    n = savedsearch.run_shortcut(shortcut, suffix)
    if not n:
        return [], n
    _, texts, path, bounds = wait_for("list")
    return search.read_results(f"{shortcut}{suffix}", path, texts, bounds)


def door_walk(suffix, limit, who, shortcut=SHORTCUT, gone=None):
    """each one in the pile + suffix gets its final tag at the door (../shared/door.py, the same rules as /ivc's
    losers), or is left as it is and listed as not sure. Never a Transfer by default. gone(what the door said, the
    door): did that one leave this pile? -> Counter of what happened"""
    import door
    from ivc import GYM_DEFENDERS  # noqa: F401 (verdict, loaded by Door, needs /ivc on the path)
    gate = door.Door(shortcut, account=who, find=lambda term: pile_tiles(f"{suffix}&{term}", shortcut), rank_gym=True)
    passed = gate.listed()
    log(f"door: {sum(passed.values())} on the not-sure list, passed over")
    counts, judged = Counter(), set()

    def visit(i, n, c):
        if passed[(n, c)]:
            passed[(n, c)] -= 1
            return False
        if (n, c) in judged:  # the list hasn't dropped it yet (or a twin: the next run gets that one). Never judged twice
            log(f"  {n!r} CP{c}: done, still on the list: passed over")
            return False
        counts["opened"] += 1
        got, iv = gate.judge_open(i, n, c)
        counts[got] += 1
        log(f"DONE door {got} {n!r} CP{c} {iv}")
        go("close", "list")
        # gone only with a tag the rest leaves out (Old, 2XL, a star or not sure: it stays, and is passed)
        left = gone(got, gate) if gone else got == "tag" and bool(set(gate.last.tags) & {*TAGS, XLX, TRANSFER})
        if left:
            judged.add((n, c))
        return left

    def walk(part):  # one part of the pile (door.walk_parts): its search says traded or not, and the catch date's age
        nonlocal gate
        gate = part
        search.walk_list(visit, stop=lambda n: counts["opened"] >= limit)
        return counts["opened"] >= limit

    count = lambda terms: savedsearch.run_shortcut(shortcut, f"{suffix}&{terms}" if terms else suffix)
    if whole := count(""):
        door.walk_parts(gate, whole, count, walk, limit)
    return counts


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):  # the default: the door walk
        a = ["door"] + a
    cmds = {"refresh": cmd_refresh}
    cmds["dynamax"] = cmd_dynamax
    cmds["team100"] = cmd_team100
    if a[0] not in (*cmds, "plan", "read", "tag", "door"):
        sys.exit(__doc__)
    if a[0] == "door":
        session.main(cmd_door, session.limit(a))
    elif a[0] == "read":
        session.main(cmd_read, a[1] if len(a) > 1 else None)
    elif a[0] == "tag":
        session.main(cmd_tag, session.limit(a))
    elif a[0] == "plan":
        session.main(cmd_plan)
    else:
        session.main(cmds[a[0]])
