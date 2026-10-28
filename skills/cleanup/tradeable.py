#!/usr/bin/env python3
"""Tag CyrillJan's Tradeable saved search by what a trade to HashTagAJay is worth, and power them up for Candy XL.

  python3 tradeable.py refresh            the Mac: PvPoke's rankings -> pvp-giv-<date>.json, PokeMiners' game master
                                          -> giv-evolved-<date>.json and dynamax-<date>.json
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py dynamax   CyrillJan signed in: only searches, for plan --to
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py read [searches.json]   HashTagAJay signed in: only searches
  python3 tradeable.py plan [--to CyrillJan]   the Mac: every search to tag, in runs/<time>-plan/
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py tag [--limit N]   CyrillJan signed in: tags, power-ups
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py tag --nope [--limit N]   either account: its Nope pile

--nope: the same tags for everything tagged Nope, judged for the other account (the one it would be traded to). It
runs rescue.py first (a 98%+ one gets the star, never a tag). A traded one can't trade again: Transfer only. Never
touched: shadows, lucky, costumes, backgrounds, special trades, and anything with another of the user's tags. An
untraded 2016-2020 catch gets GuaranteedLucky (a trade makes it lucky). Nope comes off once a new tag is on. HashTagAJay's Nope goes to CyrillJan,
which only wants good raid attackers and XL candy: plan --to CyrillJan has just GIV (top 6 against some raid boss,
until CyrillJan has 6 good copies, 1 for a mega-only one, and a Dynamax one if it can; and an untraded Dynamax one of
a family CyrillJan has none of), XLX (5,000 Stardust+, level 29+) and GIV (evolved). It reads CyrillJan's /roster
count and dynamax. HashTagAJay's untraded Nope also gets, right after Old: GIV for a tiny Rattata (2.41 kg or less)
or a big Magikarp (13.13 kg or more), for any account's medals; then 2XL for one with under 360 Candy XL (a Friendship
Friday trade gives a sure 2 Candy XL), over every other GIV and XLX. --resort: the untraded Transfer ones go back to
Nope first, to be judged again.

One tag each, the first that fits:
 1. Luckydex: HashTagAJay's newest lucky /dex run misses it, or an evolution of it (dex's gender and form rules).
 2. Reroll: a new copy would be #1 against some raid boss (/roster's roster.json).
 3. GIV: any of
    - a new 100 would fill a hole on HashTagAJay's ★100% page, itself or by evolving (dex.hundred_useful: a later
      stage on the page counts for the earlier ones, and each missing branch wants its own copy)
    - PvPoke top 100 in Great, Ultra or Master League, with every rank 1 IV 5 or more (pvp-giv-<date>.json)
    - a new copy would be #2-#6 against some raid boss
    - HashTagAJay has a lucky one of the family and under 348 candy (read)
 4. XLX: a power-up costs 4 Candy or more (level 26+: 4,000 Stardust with 4 Candy, or 4,500+). Read one by one in the power-up dialog.
 5. GIV (evolved): a stage 2 (a baby isn't a stage), or a stage 1 that takes 100+ candy, a quest or an item to
    evolve into, or one GO can't evolve into yet (Kleavor, Alolan Marowak) (giv-evolved-<date>.json). Also gym
    defenders (/ivc's GYM_DEFENDERS) and untraded Dynamax ones. Tagged after the XLX walk.
 6. GIV (far): never traded and caught 100 km or more away ('distance100-'), and no other tag fits.
 7. Transfer: everything else, but a never-traded XXL or XXS one gets renamed XXL or xxs and tagged IVC (sizes.py).
Special trades get no tag at all and are never powered up: Legendary, Mythical, Ultra Beast, shiny and Gigantamax. The
user trades them by hand, so a tag never lines one up for a trade that uses up the day's special trade. Shadows can't
be traded.

Power-ups: only cleantrades' cheap jumps (14->15, 19->20, 22->23, 30->31), never below 1,000,000 Stardust, and only while
the account that will transfer it has under 360 Candy XL of the family: HashTagAJay (read) for the traded tags,
CyrillJan for the rest.

read (HashTagAJay): which families have a lucky one and under 348 candy, and which have 360+ Candy XL. Group searches
('lucky&1-151&countcandy0-347'), halved until each hit is one family. -> runs/<time>-read/read.json
plan: the searches from the newest lucky and ★100% /dex runs of HashTagAJay, roster.json, read.json and pvp-giv.
tag (CyrillJan): the saved search 'Tradeable' + each plan search -> long press, SELECT ALL, tag. Then each one left is
opened for XLX and power-ups, then the rest -> Transfer. Log in runs/<time>-tag/.
"""
import json, math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.insert(0, os.path.join(HERE, "..", "dex"))
sys.path.append(os.path.join(HERE, "..", "ivc"))  # last: its run.py isn't pvpc's
import ui
import run as base
from run import Stop, Skip, log, go, look, wait_for
import search
import pvp
import home, session
import dex
import cleantrades as ct
import sizes
import rescue
import suspects
from shadows import Pass, next_one, owned
from ivc import GYM_DEFENDERS

GIVER, TAKER = "CyrillJan", "HashTagAJay"  # Tradeable is the giver's; the taker's dex, candy and XL decide
SHORTCUT = "Tradeable"
TAGS = ["Luckydex", "Reroll", "GIV"]  # by species, in this order
XLX, TRANSFER = "XLX", "Transfer"
LUCKY_CANDY = 348  # under this, a lucky one of the family wants a new copy's candy
XL_CAP = 360
XLX_LEVEL = 26  # from here a power-up costs 4 Candy or more (4,000 Stardust at 26-26.5, 4,500+ after)
# CyrillJan's pile only: GIV where it would get Transfer (tagged after XLX, like the evolved GIV ones)
GIV_FOR_TAKER = {"tandemaus": "HashTagAJay still wants the family of 3 Maushold (and CyrillJan gets candy from the "
                              "trade if it ever wants one)"}
XLX_FOR = {TAKER: XLX_LEVEL, GIVER: 29}  # by who'd get it. CyrillJan: 5,000 Stardust+, likely to drop a Candy XL
PVE_TOP = 6  # plan --to CyrillJan: GIV if a traded copy would be this high against some raid boss
MAX_SUFFIX = 300  # characters added to the saved search: it's already in the bar
PVP_FLOOR = 5  # every rank 1 IV at least this
PVP_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall/rankings-%d.json"
PM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
HARD_CANDY = 100  # a stage 1 that costs this much candy to evolve into counts for the evolved GIV rule
BABIES = {172, 173, 174, 175, 236, 238, 239, 240, 298, 360, 406, 433, 438, 439, 440, 446, 447, 458, 848}  # not a stage
SPECIAL = ("legendary", "mythical", "ultrabeast")  # special trades by species: traded by hand, never tagged
# every special trade: no search here tags or powers one up. (Not in the taker's dex is one too: the user checks that)
NO_SPECIAL = "&!gigantamax&!shiny" + "".join(f"&!{t}" for t in SPECIAL)
DYNAMAX = "&dynamax&!traded"  # evolved GIV too


# ---------- refresh: PvPoke ----------

def cmd_refresh():
    import urllib.request
    keep = {}
    for cap in (1500, 2500, 10000):
        ranks = json.load(urllib.request.urlopen(PVP_URL % cap))[:100]
        for i, r in enumerate(ranks, 1):
            sid = r["speciesId"].replace("_shadow", "")
            if sid not in pvp.SPECIES:
                print(f"{cap}: no {sid} in the gamemaster")
                continue
            ivs = (15, 15, 15) if cap == 10000 else pvp.table(sid, cap)[0][2]
            if min(ivs) >= PVP_FLOOR:
                keep.setdefault(sid, []).append(f"{cap}:#{i}")
    out = os.path.join(HERE, f"pvp-giv-{time.strftime('%Y%m%d')}.json")
    json.dump(dict(sorted(keep.items())), open(out, "w"), indent=0)
    print(f"{len(keep)} species -> {out}")
    gm = json.load(urllib.request.urlopen(PM_URL))
    hard = hard_evolutions(gm)
    out = os.path.join(HERE, f"giv-evolved-{time.strftime('%Y%m%d')}.json")
    json.dump(dict(sorted(hard.items())), open(out, "w"), indent=0)
    print(f"{len(hard)} hard evolutions -> {out}")
    can = dynamax_species(gm)
    out = os.path.join(HERE, f"dynamax-{time.strftime('%Y%m%d')}.json")
    json.dump(can, open(out, "w"))
    print(f"{len(can)} dex numbers can Dynamax -> {out}")


def dynamax_species(gm):
    """PokeMiners' game master -> [dex numbers that can Dynamax] (a 'BREAD_MODE' override: 'bread' is Max)"""
    return sorted({int(re.search(r"V(\d{4})_", x["templateId"]).group(1)) for x in gm
                   if any(o.get("breadMode") == "BREAD_MODE"
                          for o in (x["data"].get("pokemonExtendedSettings") or {}).get("breadOverrides") or [])})


def hard_evolutions(gm):
    """PokeMiners' game master -> {speciesId: why}: evolving into it costs HARD_CANDY+ candy, a quest or an item, or
    it evolves from something in the main games but can't be evolved into in GO yet (Kleavor, Alolan Marowak)"""
    out, reached = {}, set()
    for x in gm:
        for b in (x["data"].get("pokemonSettings") or {}).get("evolutionBranch") or []:
            if "evolution" not in b or b.get("temporaryEvolution"):
                continue
            names = [re.sub(r"_alola$", "_alolan", n.lower().removesuffix("_normal"))
                     for n in (b.get("form"), b["evolution"]) if n]  # (pvpoke: _alolan; an odd form: the species)
            sid = next((n for n in names if n in pvp.SPECIES), None)
            if not sid:
                print(f"no {names[0]} in the gamemaster")
                continue
            reached.update(n for n in names if n in pvp.SPECIES)
            item = b.get("evolutionItemRequirement") or b.get("lureItemRequirement") or ""
            why = [w for w, ok in [(f"{b.get('candyCost')} candy", (b.get("candyCost") or 0) >= HARD_CANDY),
                                   ("quest", b.get("questDisplay")),
                                   (item.removeprefix("ITEM_").lower().replace("_", " "), item)] if ok]
            if why:
                out.setdefault(sid, ", ".join(why))
    m = Model()
    for sid in m.by:
        par = m.parent_of(sid)
        if par and sid not in reached and m.by[sid].get("released") and "duplicate" not in m.by[sid].get("tags", []):
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
        p = self.parent.get(sid) or (self.by[sid].get("family") or {}).get("parent")
        return p if p in self.by and (p, sid) not in dex.BAD_EDGES else None

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


def find(fams, prefix, count, n, seen):
    """group test: the families where prefix&<their dexes>&count finds something. Halves each group with hits, or
    tests each family alone once hits turn out common. n(query) -> result count. seen: [hits, families settled] so
    far in this pass, updated"""
    hits, todo = [], [fams]
    while todo:
        g = todo.pop(0)
        dexes = ",".join(dex.ranges({d for _, ds in g for d in ds}))
        n_ = n(f"{prefix}{dexes}&{count}")
        log(f"  {len(g)} families {g[0][0]}-{g[-1][0]}: {n_}")
        if not n_:
            seen[1] += len(g)
            continue
        if len(g) == 1:
            hits.append(g[0][0])
            seen[0] += 1
            seen[1] += 1
        elif len(g) <= 3 or (seen[0] + 1) / (seen[1] + 10) > 0.2:  # hits are common: halving costs more than one each
            todo += [[f] for f in g]
        else:
            todo += [g[:len(g) // 2], g[len(g) // 2:]]
    return sorted(hits)


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
    n = dex.counter(cache, lambda q, c: json.dump(cache, open(saved, "w"), indent=0))  # saved as it goes
    m = Model()
    fams = families_by_dex(m)
    chunks = [fams[i:i + 20] for i in range(0, len(fams), 20)]  # 20 families: a short search, and fewer splits
    seen = [0, 0]
    lucky = [h for c in chunks for h in find(c, "lucky&", f"countcandy0-{LUCKY_CANDY - 1}", n, seen)]
    log(f"lucky, under {LUCKY_CANDY} candy: {lucky}")
    seen = [0, 0]
    xl = [h for c in chunks for h in find(c, "", f"countcandyxl{XL_CAP}-", n, seen)]
    log(f"{XL_CAP}+ Candy XL: {xl}")
    out = {"trainer": who, "lucky_low_candy": lucky, "xl_full": xl}
    json.dump(out, open(os.path.join(base.RUN_DIR, "read.json"), "w"), indent=1)


# ---------- plan ----------

def newest_for(pattern, who, key="trainer", default=None):
    """the newest runs/<pattern> json whose key is who (one without the key counts as default's)"""
    import glob
    for f in sorted(glob.glob(os.path.join(HERE, "runs", pattern)), reverse=True):
        if json.load(open(f)).get(key, default) == who:
            return f
    return None


def pve(m, enough=lambda s, mega_only: False):
    """-> ({sid: why}, {sid: why dropped}): a traded copy (never shadow) would be in DialgaDex's top PVE_TOP against
    some raid boss, or evolve into one that is. Special trades left out of the top: they're never tagged. A mega counts
    as its species. enough(sid, only in as a mega) -> why the taker needs no more of it, or None"""
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    data_f = base.newest(HERE, os.path.join("..", "roster", "dialgadex-counters-[0-9]*[0-9].json"))
    if not data_f:
        sys.exit("no DialgaDex counters yet: node ../roster/pull.mjs")
    rm = roster.Model(json.load(open(data_f)))
    tops, plain = {}, set()
    for b in rm.bosses:
        top = []
        for i, *_ in b["list"]:
            s, a = rm.sid[i], rm.A[i]
            if not s or (a["shadow"] and not roster.is_mega(a)) or rm.special(s) or not m.tradeable(s):
                continue
            if s not in top:
                top.append(s)
                if not roster.is_mega(a):
                    plain.add(s)  # in some top as itself: a mega-only one is only ever in as its mega
            if len(top) >= PVE_TOP:
                break
        boss = b["name"] + ("" if b["form"] == "Normal" else f" ({b['form']})")
        for s in top:
            tops.setdefault(s, []).append(boss)
    out, dropped = {}, {}
    for s, bs in tops.items():
        if s not in m.by:
            continue
        if why := enough(s, s not in plain):
            dropped[s] = why
            continue
        for x in [s, *rm.ancestors(s)]:
            out.setdefault(x, []).extend(bs)
    why = {s: "top %d vs %s" % (PVE_TOP, ", ".join(bs[:3]) + (f" +{len(bs) - 3}" if len(bs) > 3 else ""))
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
    defender, of the ok ones not in why. Tagged GIV only after the XLX walk: XLX wins over these"""
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


def cmd_plan(to=TAKER):
    if to == GIVER:
        return plan_for_giver()
    if to != TAKER:
        sys.exit(f"plan --to {TAKER} or {GIVER}")
    m = Model()
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
        sys.exit(f"no {', '.join(lacking)} for {TAKER} yet")
    roster = json.load(open(roster_f))
    read = json.load(open(read_f))
    pvp_giv = json.load(open(pvp_f))

    ok = [s for s in m.by if m.tradeable(s) and not m.special(s)]
    lucky = luckydex(m, set(lucky_missing))
    reroll = {s for s in roster["reroll"] if s in m.by}
    why = {}
    for s in ok:
        if s in lucky:
            why.setdefault(s, ("Luckydex", "lucky dex hole"))
    for s in ok:
        if s in reroll:
            why.setdefault(s, ("Reroll", "#1 raid attacker: " + ", ".join(roster["species"][s]["bosses"][:3])))
    hund = dex.hundred_useful(set(hund_missing), m.by, m.parent)
    low = {m.root(s) for s in m.by if m.dex(s) in read["lucky_low_candy"]}
    for s in ok:
        if s in hund:
            why.setdefault(s, ("GIV", "★100% hole"))
        elif s in pvp_giv:
            why.setdefault(s, ("GIV", "PvP " + " ".join(pvp_giv[s])))
        elif s in roster["giv"]:
            why.setdefault(s, ("GIV", "#2-#6 raid attacker"))
        elif m.root(s) in low:
            why.setdefault(s, ("GIV", f"lucky family under {LUCKY_CANDY} candy"))
    evolved = evolved_giv(m, ok, why, json.load(open(hard_f)))
    evolved.update({s: r for s, r in GIV_FOR_TAKER.items() if s in ok and s not in why})
    plan = {"taker": TAKER, "xlx_level": XLX_FOR[TAKER],
            "from": {"lucky": lucky_run, "100": hund_run, "roster": roster_f, "read": read_f, "pvp": pvp_f,
                     "evolved": hard_f},
            "tags": {t: queries(m, [s for s, (w, _) in why.items() if w == t], lucky if t == "Luckydex" else None,
                                room=len(NOT_TAGGED) + 10) for t in TAGS},
            "giv_evolved": queries(m, evolved, room=len(EVOLVED_REST) + 10) + [DYNAMAX],
            "taker_xl_full": sorted({m.dex(x) for s in m.by if m.dex(s) in read["xl_full"] for x in m.family(s)})}
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="plan")
    json.dump(plan, open(os.path.join(base.RUN_DIR, "plan.json"), "w"), indent=1)
    lines = [f"# Tradeable plan {time.strftime('%Y-%m-%d %H:%M')}", ""]
    lines += [f"- {k}: {v}" for k, v in plan["from"].items()] + [""]
    for t in TAGS:
        lines += [f"## {t}: {sum(1 for w, _ in why.values() if w == t)} species forms", ""]
        lines += [f"- {m.by[s]['speciesName']} (#{m.dex(s)}): {r}"
                  for s, (w, r) in sorted(why.items(), key=lambda x: m.dex(x[0])) if w == t]
        lines += ["", "Searches (after the Tradeable search):", ""] + [f"    {q}" for q in plan["tags"][t]] + [""]
    lines += [f"## GIV (evolved, only after XLX): {len(evolved)} species forms", "",
              "Stage 2, a stage 1 that takes 100+ candy, a quest or an item, a gym defender, or (the last search) an "
              "untraded Dynamax one. Tagged after the XLX walk, so a level 26+ one gets XLX instead. Special trades "
              "(Legendary, Mythical, Ultra Beast, shiny, Gigantamax) get no tag at all: they're for you to trade.", ""]
    lines += [f"- {m.by[s]['speciesName']} (#{m.dex(s)}): {r}" for s, r in sorted(evolved.items(), key=lambda x: m.dex(x[0]))]
    lines += ["", f"Searches (after the Tradeable search, with {EVOLVED_REST}):", ""]
    lines += [f"    {q}" for q in plan["giv_evolved"]] + [""]
    open(os.path.join(base.RUN_DIR, "plan.md"), "w").write("\n".join(lines))
    log(f"plan: {', '.join(f'{t} {len(q)} searches' for t, q in plan['tags'].items())}, "
        f"evolved GIV {len(plan['giv_evolved'])} searches -> {base.RUN_DIR}")


def can_dynamax():
    """dex numbers that can Dynamax (refresh's dynamax-<date>.json)"""
    f = base.newest(HERE, "dynamax-[0-9]*[0-9].json")
    if not f:
        sys.exit("no dynamax-<date>.json yet: python3 tradeable.py refresh")
    return set(json.load(open(f)))


def cmd_dynamax():
    """CyrillJan signed in: how many Dynamax ones of each family that can Dynamax (only searches)"""
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="dynamax")
    who = home.trainer()
    if who != GIVER:
        raise Stop(f"signed in as {who!r}: dynamax counts {GIVER}'s")
    m, can = Model(), can_dynamax()
    home.start()
    n = dex.counter({}, lambda q, c: log(f"  {q}: {c}"))
    out = {}
    for lo, ds in families_by_dex(m):
        if can & set(ds):
            out[lo] = n(",".join(dex.ranges(ds)) + "&dynamax")
            json.dump({"trainer": who, "families": out}, open(os.path.join(base.RUN_DIR, "dynamax.json"), "w"))
    log(f"{sum(1 for v in out.values() if v)} of {len(out)} families have a Dynamax one -> {base.RUN_DIR}")


def plan_for_giver():
    """HashTagAJay's Nope -> CyrillJan: only good raid attackers (GIV) and Candy XL (XLX). No dex rules"""
    sys.path.append(os.path.join(HERE, "..", "roster"))
    import roster
    m, can = Model(), can_dynamax()
    read_f = newest_for(os.path.join("*-read", "read.json"), GIVER)  # (only its 360+ XL families: none without)
    xl_full = json.load(open(read_f))["xl_full"] if read_f else []
    counts_f = newest_for(os.path.join("..", "..", "roster", "runs", "*-count", "counts.json"), GIVER, default=TAKER)
    dmax_f = newest_for(os.path.join("*-dynamax", "dynamax.json"), GIVER)
    good = {}
    for (s, _, shadow), v in (roster.load_counts(counts_f)[0] if counts_f else {}).items():
        if not shadow:
            good[s] = good.get(s, 0) + v
    fam_of = {d: lo for lo, ds in families_by_dex(m) for d in ds}
    dmax = {int(lo): v for lo, v in json.load(open(dmax_f))["families"].items()} if dmax_f else {}
    has_dmax = lambda s: dmax.get(fam_of.get(m.dex(s)), 0) > 0

    def enough(s, mega_only):
        """CyrillJan has PVE_TOP good copies (1 for one that's only in as a mega: one mega per team), and a Dynamax
        one of the family if it can Dynamax. (Not counted is 0: /roster stops counting once a team is full)"""
        need = 1 if mega_only else PVE_TOP
        if good.get(s, 0) >= need and (m.dex(s) not in can or has_dmax(s)):
            return f"{GIVER} has {good[s]} good" + (", and a Dynamax one" if m.dex(s) in can else "")
        return None

    hard_f = base.newest(HERE, "giv-evolved-*.json")
    if not hard_f:
        sys.exit("no giv-evolved yet: python3 tradeable.py refresh")
    picked, dropped = pve(m, enough)
    ok = [s for s in m.by if m.tradeable(s) and not m.special(s)]
    why = {s: r for s, r in picked.items() if s in ok}
    evolved = evolved_giv(m, ok, why, json.load(open(hard_f)))
    no_dmax = [s for s in ok if m.dex(s) in can and not has_dmax(s)]
    plan = {"taker": GIVER, "xlx_level": XLX_FOR[GIVER],
            "from": {"read": read_f, "counts": counts_f, "dynamax": dmax_f, "evolved": hard_f},
            "tags": {"Luckydex": [], "Reroll": [], "GIV": queries(m, why, room=len(NOT_TAGGED) + 10)},
            "giv_evolved": queries(m, evolved, room=len(EVOLVED_REST) + 10)
                           + [q + DYNAMAX for q in queries(m, no_dmax, room=len(EVOLVED_REST + DYNAMAX) + 10)],
            "taker_xl_full": sorted({m.dex(x) for s in m.by if m.dex(s) in xl_full for x in m.family(s)})}
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="plan")
    json.dump(plan, open(os.path.join(base.RUN_DIR, "plan.json"), "w"), indent=1)
    name = lambda s: f"{m.by[s]['speciesName']} (#{m.dex(s)})"
    lines = [f"# Nope plan for {GIVER} {time.strftime('%Y-%m-%d %H:%M')}", "",
             f"- read: {read_f or f'none ({GIVER} signed in: tradeable.py read), so no family counts as 360+ XL'}",
             f"- good copies: {counts_f or f'none ({GIVER} signed in: roster.py count), so nothing is enough yet'}",
             f"- Dynamax: {dmax_f or f'none ({GIVER} signed in: tradeable.py dynamax), so no family has one yet'}", "",
             f"## GIV: {len(why)} species forms", "",
             f"In DialgaDex's top {PVE_TOP} against some raid boss (no shadows, megas as their species, special trades "
             f"left out), or an earlier stage of one. Not once {GIVER} has {PVE_TOP} good (3★/4★) copies (1 for one "
             f"that's only in as a mega) and a Dynamax one if it can Dynamax. Then (after XLX) an untraded Dynamax one "
             f"of a family {GIVER} has no Dynamax one of.", ""]
    lines += [f"- {name(s)}: {r}" for s, r in sorted(why.items(), key=lambda x: m.dex(x[0]))]
    lines += ["", f"Enough already ({len(dropped)}):", ""]
    lines += [f"- {name(s)}: {r}" for s, r in sorted(dropped.items(), key=lambda x: m.dex(x[0]))]
    lines += ["", "Searches (after the Nope search):", ""] + [f"    {q}" for q in plan["tags"]["GIV"]] + [""]
    lines += [f"## XLX: level {XLX_FOR[GIVER]}+ (a power-up costs 5,000 Stardust or more)", ""]
    lines += [f"## GIV (evolved, only after XLX): {len(evolved)} species forms", "",
              "Stage 2, a stage 1 that takes 100+ candy, a quest or an item, or a gym defender. 2XL (under 360 Candy XL) "
              "comes first, so these only get GIV in a family with 360+ Candy XL.", ""]
    lines += [f"- {name(s)}: {r}" for s, r in sorted(evolved.items(), key=lambda x: m.dex(x[0]))]
    lines += ["", f"Searches (with {EVOLVED_REST}):", ""] + [f"    {q}" for q in plan["giv_evolved"]] + [""]
    open(os.path.join(base.RUN_DIR, "plan.md"), "w").write("\n".join(lines))
    log(f"plan for {GIVER}: GIV {len(why)} species forms ({len(dropped)} enough already), "
        f"{len(plan['tags']['GIV'])} searches -> {base.RUN_DIR}")


# ---------- tag (CyrillJan's Tradeable, or either account's Nope) ----------

# every tag search and walk leaves special trades out: the user trades them by hand
NOT_TAGGED = NO_SPECIAL + "".join(f"&!#{t}" for t in TAGS)
REST = NOT_TAGGED + f"&!#{XLX}&!#{TRANSFER}"  # not tagged yet
EVOLVED_REST = REST + "&traded,!xxl&traded,!xxs"  # and not a never-traded XXL/XXS one (those get IVC)
NOPE = "Nope"
OTHER_TAGS = ("IVC", "PvpC", "Old", "GuaranteedLucky", "Evo")  # a Nope with one of these is the user's to sort
NOPE_KEEP = "&!shadow&!lucky&!costume&!background" + "".join(f"&!#{t}" for t in OTHER_TAGS)  # never-Nope kinds
NOPE_PILE = f"#{NOPE}&!traded&year2021-" + NOPE_KEEP  # the untraded ones: every rule, like Tradeable
NOPE_TRADED = f"#{NOPE}&traded" + NOPE_KEEP + NO_SPECIAL + f"&!#{TRANSFER}"  # can't trade again: Transfer only
GUARANTEED = "GuaranteedLucky"
NOPE_OLD = f"#{NOPE}&!traded&year-2020" + NOPE_KEEP + NO_SPECIAL  # a trade makes it lucky: GuaranteedLucky
# suspects.py checks these before any tag: the untraded ones, and every gym defender (traded too: the gym rule).
# (',' binds tighter than '&': Nope and (untraded or a gym defender's dex))
SUSPECT_PILE = f"#{NOPE}&!traded,{suspects.GYM_DEX}" + NOPE_KEEP + NO_SPECIAL
OLD, OLD_AGE = "Old", "&age300-"  # caught 300+ days ago: after Luckydex, before Reroll, GIV and XLX
PILE = None  # tag --nope: NOPE_PILE, typed in place of the Tradeable shortcut
# HashTagAJay's Nope only, after Old: medal ones (by weight, read on the detail page) -> GIV, for any other account.
# The Youngster medal counts tiny Rattata (any region), the Fisherman medal big Magikarp
MEDALS = [("Rattata", "&19&xxs,xs", lambda kg: kg <= 2.41), ("Magikarp", "&129", lambda kg: kg >= 13.13)]
MEDAL_KG = {"Rattata": (0.5, 10), "Magikarp": (2, 30)}  # a weight outside this is a misread (a lost decimal point)
# then 2XL: under 360 Candy XL, for a Friendship Friday trade (a sure 2 Candy XL). Beats every other GIV and XLX. A
# never-traded XXL/XXS one is left for sizes.py's IVC
TWO_XL = "2XL"
TWO_XL_PILE = NOPE_PILE + NOT_TAGGED + "&!xxl&!xxs" + ct.UNDER_360_XL  # (the count term last)
RESORT = f"#{TRANSFER}&!traded&!#{NOPE}" + NOPE_KEEP + NO_SPECIAL  # --resort: Nope back on, Transfer off


def run_pile(suffix):
    """the pile's search + suffix -> its count, or None if this account has no Tradeable shortcut"""
    if PILE is None:
        return ct.run_shortcut(SHORTCUT, suffix)
    return ct.long_search(PILE + suffix)


def tag_pile(tag, suffix):
    if PILE is None:
        return ct.tag_pile(SHORTCUT, tag, suffix)
    return ct.tag_pile(NOPE, tag, query=PILE + suffix)  # (Nope comes off at the end: the walks find them by it)


def level_of(info, texts):
    """-> the levels this one can be at, from the power-up cost on the detail page. No taps. A cost on both sides of
    XLX_LEVEL (4,000 at 26) needs its candy, which OCR often misses: a few more looks for it"""
    for _ in range(4):
        lvs = ct.cost_levels(texts, info["cp"])[1]
        if not lvs or min(lvs) >= XLX_LEVEL or max(lvs) < XLX_LEVEL:
            break
        _, texts, _, _ = look()
    return lvs


def walk(suffix, xlx, power, limit, skip_dex=(), unsure=None):
    """open each one in the pile + suffix: xlx -> tag it XLX if it's XLX_LEVEL+ (the ones it can't tell go in unsure).
    power -> cleantrades' power-up, not for a family in skip_dex. -> power-ups made, or None if --limit stopped it"""
    if not run_pile(suffix):
        return 0
    go("tile 1", "detail")
    seen, done = set(), 0
    while True:
        _, texts, _, bounds = wait_for("detail")
        info = ui.detail_info(texts)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:
            break
        seen.add(me)
        base.OPENED["who"] = base.who(info)  # the swipe moved here on purpose: set_tags checks against this one
        checked = not xlx  # its level is known to be under 26, or it's tagged XLX
        try:
            if xlx:
                lvs = level_of(info, texts)
                if lvs and min(lvs) >= XLX_LEVEL:
                    base.set_tags(on=(XLX,))
                    checked = True
                    log(f"XLX {info['name']} CP{info['cp']}: level {lvs}")
                    raise Pass("tagged XLX")
                if not lvs or max(lvs) >= XLX_LEVEL:
                    raise Pass(f"level {lvs or '?'} ({ct.page_cost(texts)} dust): can't tell if it's {XLX_LEVEL}+, "
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
                n = ct.power_up(info, texts)
                done += 1
                for _ in range(10):  # the new CP sparkles for a moment and can read blank
                    info2 = ui.detail_info(wait_for("detail")[1])
                    if info2["cp"] is not None:
                        break
                    time.sleep(0.2)
                seen.add((info2["name"], info2["cp"], info2["hp"]))
                log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {n} power-up(s)")
        except (Pass, Skip) as e:
            log(f"pass {info['name']} CP{info['cp']}: {e}")
            if (not checked or isinstance(e, ct.Unsure)) and unsure is not None:
                unsure.append(f"{info['name']} CP{info['cp']} HP{info['hp']}: {e}")
        # (the bounds don't change on the detail page)
        if not next_one(bounds, lambda t: (lambda i: (i["name"], i["cp"], i["hp"]))(ui.detail_info(t)) not in seen):
            break
    go("close", "list")
    return done


SMALL_PILE = 40  # a pile this small is opened once to read its species: searches for species not in it are skipped


def dexes_of(q):
    """'&1-3,7&!galar' -> {1, 2, 3, 7}: the dex numbers a plan search is for. None if it has none (&dynamax)"""
    for term in q.split("&"):
        if term and re.fullmatch(r"[\d,\-]+", term):
            out = set()
            for r in term.split(","):
                a, _, b = r.partition("-")
                out.update(range(int(a), int(b or a) + 1))
            return out
    return None


def survey():
    """-> the dex numbers in the pile, opening each one once. None if the pile is big (searching is quicker then) or
    one's species can't be told from its name (a nickname): then every search runs"""
    n = run_pile("")
    if not n or n > SMALL_PILE:
        return set() if n == 0 else None
    go("tile 1", "detail")
    seen, out = set(), set()
    while True:
        _, texts, _, bounds = wait_for("detail")
        info = ui.detail_info(texts)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:
            break
        seen.add(me)
        sids = ui.species_for(info["name"], info["texts"])
        if not sids:
            log(f"survey: can't tell the species of {info['name']} CP{info['cp']}: every search runs")
            go("close", "list")
            return None
        out |= {pvp.SPECIES[x]["dex"] for x in sids}
        if not next_one(bounds, lambda t: (lambda i: (i["name"], i["cp"], i["hp"]))(ui.detail_info(t)) not in seen):
            break
    go("close", "list")
    log(f"survey: {len(seen)} of {n} seen, dex {sorted(out)}: " + ", ".join(f"{a} CP{b}" for a, b, _ in seen))
    if len(seen) < n:  # the walk stopped short: one not seen could need a skipped search
        log("survey: missed some: every search runs")
        return None
    return out


def medal_walk(unsure, have=None):
    """HashTagAJay's Nope: open each Rattata and Magikarp in MEDALS' searches and tag GIV the ones whose weight fits.
    One whose weight doesn't read goes in unsure"""
    for name, q, fits in MEDALS:
        if have is not None and not dexes_of(q) & have:
            continue
        if not run_pile(q + NOT_TAGGED):
            continue
        go("tile 1", "detail")
        seen = set()
        while True:
            _, texts, _, bounds = wait_for("detail")
            info = ui.detail_info(texts)
            me = (info["name"], info["cp"], info["hp"])
            if me in seen:
                break
            seen.add(me)
            base.OPENED["who"] = base.who(info)
            kg = base.OPENED["who"][2]
            lo, hi = MEDAL_KG[name]
            if kg is None or not lo <= kg <= hi:
                log(f"pass {info['name']} CP{info['cp']}: weight read {kg}")
                unsure.append(f"{name} {info['name']} CP{info['cp']} HP{info['hp']}: weight read {kg}")
            elif fits(kg):
                base.set_tags(on=("GIV",))
                log(f"GIV {name} {info['name']} CP{info['cp']}: {kg} kg")
            else:
                log(f"pass {name} {info['name']} CP{info['cp']}: {kg} kg")
            if not next_one(bounds, lambda t: (lambda i: (i["name"], i["cp"], i["hp"]))(ui.detail_info(t)) not in seen):
                break
        go("close", "list")


def cmd_tag(limit, nope=False, resort=False):
    global PILE, XLX_LEVEL
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="tag")
    who = home.trainer()
    if who not in (GIVER, TAKER) or (who != GIVER and not nope):
        raise Stop(f"signed in as {who!r}: tag needs {GIVER} (tag --nope: {GIVER} or {TAKER})")
    to = TAKER if who == GIVER else GIVER
    plan_f = newest_for(os.path.join("*-plan", "plan.json"), to, key="taker", default=TAKER)
    if not plan_f:
        raise Stop(f"no plan for {to} yet: python3 tradeable.py plan" + (f" --to {to}" if to == GIVER else ""))
    plan = json.load(open(plan_f))
    XLX_LEVEL = plan.get("xlx_level", XLX_LEVEL)
    log(f"{who}: tagging for {to} from {plan_f}, XLX at level {XLX_LEVEL}+")
    search.to_search_list()
    if resort:  # the untraded ones tagged Transfer before a rule changed: back in the Nope pile, judged again
        ct.tag_pile(NOPE, NOPE, off=(TRANSFER,), query=RESORT)
        search.to_search_list()
    if nope:
        rescue.main(10 ** 9, False)  # first: a 98%+ one in Nope gets the star and loses Nope, so it's never tagged here
        PILE = NOPE_PILE
        search.to_search_list()
    if nope:  # one that may still be a keeper gets no tag until it's checked (suspects.py). First: a traded gym
        left = suspects.run(SUSPECT_PILE, who)  # defender may be top 20, so it waits for this too
        if left:
            log(f"not tagging the untraded Nope: {len(left)} suspect(s) still unresolved. Sort these by hand (keep: "
                f"star on and Nope off; or blank the name), then run tag --nope again:\n  "
                + "\n  ".join(f"{v['tile']} CP{v['cp']}: {(v.get('why') or ['?'])[0] if isinstance(v.get('why'), list) else v['why']}"
                              for v in left))
            return
        search.to_search_list()
        ct.tag_pile(NOPE, TRANSFER, off=(NOPE,), query=NOPE_TRADED)  # a traded one can't trade again: Transfer
        search.to_search_list()
        ct.tag_pile(NOPE, GUARANTEED, off=(NOPE,), query=NOPE_OLD)
    have = survey()  # a small pile: only the searches for species in it run
    wanted = lambda q: have is None or (d := dexes_of(q)) is None or bool(d & have)
    done_f = os.path.join(os.path.dirname(plan_f), f"tagged-nope-{who}.json" if nope else "tagged.json")  # this
    done = set(json.load(open(done_f))) if os.path.exists(done_f) and not resort else set()  # plan's searches already tagged: a
    for t in TAGS:  # rerun skips them (14 s each, even at 0). Each search leaves out all three tags: the first wins
        if nope and t == "Reroll":  # Old: under Luckydex, over Reroll, GIV and XLX
            ct.tag_pile(NOPE, OLD, off=(NOPE,), query=NOPE_PILE + OLD_AGE + NOT_TAGGED)
            if who == TAKER:  # then medal GIV, then 2XL: both over every other GIV and XLX
                medal_unsure = []
                medal_walk(medal_unsure, have)
                if medal_unsure:
                    log("not tagging 2XL or the rest: these medal ones had no weight read. Look at each by hand (GIV "
                        "if it fits, or leave it), then run tag --nope again:\n  " + "\n  ".join(medal_unsure))
                    return
                ct.tag_pile(NOPE, TWO_XL, off=(NOPE,), query=TWO_XL_PILE)
        for q in plan["tags"][t]:
            if q + NOT_TAGGED in done or not wanted(q):
                continue
            tag_pile(t, q + NOT_TAGGED)
            done.add(q + NOT_TAGGED)
            json.dump(sorted(done), open(done_f, "w"))
    if done:
        log(f"{len(done)} tag search(es) done for this plan (a new plan starts over)")
    # (the taker's 360+ XL families are passed on the detail page: as '&!<dex>' terms they'd overflow the bar)
    traded = NO_SPECIAL + "&" + ",".join(f"#{t}" for t in TAGS)  # (one tagged before special trades were left out)
    rest = REST
    for size in sizes.NAMES:  # first: a never-traded XXL/XXS one is renamed and tagged IVC, never XLX or Transfer
        q = rest + f"&!#{sizes.IVC}&!traded&{size}"
        sizes.walk(lambda: run_pile(q), size, 10 ** 9)
    rest = EVOLVED_REST  # (one passed over there stays out of Transfer too)
    unsure, power_ok = [], True
    # power-ups for the tagged ones (the taker transfers them), then XLX and power-ups for the rest
    walks = [(traded, False, True, set(plan["taker_xl_full"])), (rest + ct.UNDER_360_XL, True, True, ()),
             (rest + f"&countcandyxl{XL_CAP}-", True, False, ())]
    if nope and who == TAKER:  # 2XL took every one under 360 Candy XL (a never-traded XXL/XXS one is IVC by now)
        del walks[1]
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
                log(f"stopped powering up: {e}. Going on with XLX only")
                power_ok = False
                del unsure[n:]  # this walk starts over
                if look()[0] != "list":
                    go("close", "list")
    if unsure:
        log(f"not tagging the rest Transfer: {len(unsure)} couldn't be checked for {XLX_LEVEL}+ or a cheap power-up. "
            f"Look at these by hand (tag each {XLX}, power it up, or leave it), then run tag again:\n  "
            + "\n  ".join(unsure))
        return
    for q in plan.get("giv_evolved", []):  # after XLX: an XLX_LEVEL+ one has XLX by now and stays out
        if rest + q in done or not wanted(q):
            continue
        tag_pile("GIV", rest + q)
        done.add(rest + q)
        json.dump(sorted(done), open(done_f, "w"))
    tag_pile("GIV", rest + "&!traded&distance100-")  # fits nothing else, but a far trade: GIV
    tag_pile(TRANSFER, rest)  # (rest leaves out #GIV)
    if nope:  # every one has its new tag: Nope off
        ct.tag_pile(NOPE, None, off=(NOPE,), query=f"#{NOPE}&" + ",".join(f"#{t}" for t in (*TAGS, XLX, TRANSFER)))


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"refresh": cmd_refresh}
    cmds["dynamax"] = cmd_dynamax
    if not a or a[0] not in (*cmds, "plan", "read", "tag"):
        sys.exit(__doc__)
    if a[0] == "read":
        session.main(cmd_read, a[1] if len(a) > 1 else None)
    elif a[0] == "tag":
        if "--resort" in a and "--nope" not in a:
            sys.exit("--resort goes with tag --nope")
        session.main(cmd_tag, session.limit(a), "--nope" in a, "--resort" in a)
    elif a[0] == "plan":
        session.main(cmd_plan, a[a.index("--to") + 1] if "--to" in a else TAKER)
    else:
        session.main(cmds[a[0]])
