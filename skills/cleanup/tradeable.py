#!/usr/bin/env python3
"""Tag CyrillJan's Tradeable saved search by what a trade to HashTagAJay is worth, and power them up for Candy XL.

  python3 tradeable.py refresh            the Mac: PvPoke's rankings -> pvp-giv-<date>.json
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py read [searches.json]   HashTagAJay signed in: only searches
  python3 tradeable.py plan               the Mac: every search to tag, in runs/<time>-plan/
  POGO_PHONE=android caffeinate -dimsu python3 tradeable.py tag [--limit N]   CyrillJan signed in: tags, power-ups

One tag each, the first that fits:
 1. Luckydex: HashTagAJay's newest lucky /dex run misses it, or an evolution of it (dex's gender and form rules).
 2. Reroll: a new copy would be #1 against some raid boss (/roster's roster.json).
 3. GIV: any of
    - missing from HashTagAJay's ★100% page, it or an evolution, and no lower evolution of that is there
    - PvPoke top 100 in Great, Ultra or Master League, with every rank 1 IV 5 or more (pvp-giv-<date>.json)
    - a new copy would be #2-#6 against some raid boss
    - HashTagAJay has a lucky one of the family and under 348 candy (read)
 4. XLX: a power-up costs 5,000 Stardust or more (level 29+). Read one by one in the power-up dialog.
 5. Transfer: everything else.
Legendary, Mythical and Ultra Beast never get Reroll or GIV from the raid rule (roster leaves them out). Shadows can't
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
import ui
import run as base
from run import Stop, Skip, log, go, look, wait_for
import search
import pvp
import home
import dex
import cleantrades as ct
from shadows import Pass, swipe_next, owned

GIVER, TAKER = "CyrillJan", "HashTagAJay"  # Tradeable is the giver's; the taker's dex, candy and XL decide
SHORTCUT = "Tradeable"
TAGS = ["Luckydex", "Reroll", "GIV"]  # by species, in this order
XLX, TRANSFER = "XLX", "Transfer"
LUCKY_CANDY = 348  # under this, a lucky one of the family wants a new copy's candy
XL_CAP = 360
XLX_LEVEL = 29  # from here a power-up costs 5,000 Stardust or more
MAX_SUFFIX = 300  # characters added to the saved search: it's already in the bar
PVP_FLOOR = 5  # every rank 1 IV at least this
PVP_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall/rankings-%d.json"


def newest(pattern):
    """the newest file matching runs/*/<name> or <prefix>-<date>.json here"""
    import glob
    got = sorted(glob.glob(os.path.join(HERE, pattern)))
    return got[-1] if got else None


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


def hundred(m, missing):
    """sids a new copy could fill a ★100% hole with: it or an evolution is missing, and nothing below that is there"""
    out = set()
    for sid in m.by:
        for d in m.down(sid):
            if all(m.dex(x) in missing for x in [d, *dex.ancestors(d, m.parent)]):
                out.add(sid)
                break
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
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-read"))
    who = home.trainer()
    if who != TAKER:
        raise Stop(f"signed in as {who!r}: read needs {TAKER}")
    dex.save_trainer(who)
    home.start()
    cache = json.load(open(resume)) if resume else {}
    lost = [0]

    def n(q):
        """one search's count, saved as it goes. A search that loses its way goes back to the list and tries again:
        twice per search, 20 times in all"""
        for attempt in range(3):
            if q in cache:
                break
            try:
                cache[q] = dex.search_exact(q)
            except Stop as e:
                lost[0] += 1
                if attempt == 2 or lost[0] > 20:
                    raise
                log(f"  {q}: {e}: back to the Pokémon list, again")
                home.start()
                continue
            json.dump(cache, open(os.path.join(base.RUN_DIR, "searches.json"), "w"), indent=0)
        return cache[q]
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

def queries(m, sids, gender=None):
    """species forms -> ['&<dexes><form terms>', ...], each under MAX_SUFFIX characters"""
    groups = {}
    for s in sids:
        g = (gender or {}).get(s, "")
        groups.setdefault(m.terms(s) + (f"&{g}" if g else ""), set()).add(m.dex(s))
    out = []
    for terms, ds in sorted(groups.items()):
        part = []
        for r in dex.ranges(ds):
            if part and len(",".join(part + [r])) + len(terms) + 1 > MAX_SUFFIX - 40:  # room for the tag terms
                out.append(f"&{','.join(part)}{terms}")
                part = []
            part.append(r)
        out.append(f"&{','.join(part)}{terms}")
    return out


def cmd_plan():
    m = Model()
    lucky_missing, lucky_run = dex.latest("lucky", TAKER)  # (an evolve-lucky run counts too)
    hund_missing, hund_run = dex.latest("100", TAKER)
    roster_f = newest(os.path.join("..", "roster", "runs", "*", "roster.json"))
    read_f = newest(os.path.join("runs", "*-read", "read.json"))
    pvp_f = newest("pvp-giv-*.json")
    lacking = [n for n, v in [("a lucky /dex run", lucky_run), ("a ★100% /dex run", hund_run),
                              ("roster.json", roster_f), ("read.json", read_f), ("pvp-giv", pvp_f)] if not v]
    if lacking:
        sys.exit(f"no {', '.join(lacking)} for {TAKER} yet")
    roster = json.load(open(roster_f))
    read = json.load(open(read_f))
    pvp_giv = json.load(open(pvp_f))

    ok = [s for s in m.by if m.tradeable(s)]
    lucky = luckydex(m, set(lucky_missing))
    reroll = {s for s in roster["reroll"] if s in m.by}
    why = {}
    for s in ok:
        if s in lucky:
            why.setdefault(s, ("Luckydex", "lucky dex hole"))
    for s in ok:
        if s in reroll:
            why.setdefault(s, ("Reroll", "#1 raid attacker: " + ", ".join(roster["species"][s]["bosses"][:3])))
    hund = hundred(m, set(hund_missing))
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
    plan = {"from": {"lucky": lucky_run, "100": hund_run, "roster": roster_f, "read": read_f, "pvp": pvp_f},
            "tags": {t: queries(m, [s for s, (w, _) in why.items() if w == t], lucky if t == "Luckydex" else None)
                     for t in TAGS},
            "taker_xl_full": sorted({m.dex(x) for s in m.by if m.dex(s) in read["xl_full"] for x in m.family(s)})}
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-plan"))
    json.dump(plan, open(os.path.join(base.RUN_DIR, "plan.json"), "w"), indent=1)
    lines = [f"# Tradeable plan {time.strftime('%Y-%m-%d %H:%M')}", ""]
    lines += [f"- {k}: {v}" for k, v in plan["from"].items()] + [""]
    for t in TAGS:
        lines += [f"## {t}: {sum(1 for w, _ in why.values() if w == t)} species forms", ""]
        lines += [f"- {m.by[s]['speciesName']} (#{m.dex(s)}): {r}"
                  for s, (w, r) in sorted(why.items(), key=lambda x: m.dex(x[0])) if w == t]
        lines += ["", "Searches (after the Tradeable search):", ""] + [f"    {q}" for q in plan["tags"][t]] + [""]
    open(os.path.join(base.RUN_DIR, "plan.md"), "w").write("\n".join(lines))
    log(f"plan: {', '.join(f'{t} {len(q)} searches' for t, q in plan['tags'].items())} -> {base.RUN_DIR}")


# ---------- tag (CyrillJan) ----------

NOT_TAGGED = "".join(f"&!#{t}" for t in TAGS)


def level_of(info, texts):
    """-> the levels this one can be at, from the power-up cost on the detail page. No taps"""
    return ct.cost_levels(texts)[1]


def walk(suffix, xlx, power, limit, skip_dex=(), unsure=None):
    """open each one in Tradeable + suffix: xlx -> tag it XLX if it's level 29+ (the ones it can't tell go in unsure).
    power -> cleantrades' power-up, not for a family in skip_dex. -> power-ups made, or None if --limit stopped it"""
    if not ct.run_shortcut(SHORTCUT, suffix):
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
        checked = not xlx  # its level is known to be under 29, or it's tagged XLX
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
                info2 = ui.detail_info(wait_for("detail")[1])
                seen.add((info2["name"], info2["cp"], info2["hp"]))
                log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {n} power-up(s)")
        except (Pass, Skip) as e:
            log(f"pass {info['name']} CP{info['cp']}: {e}")
            if (not checked or isinstance(e, ct.Unsure)) and unsure is not None:
                unsure.append(f"{info['name']} CP{info['cp']} HP{info['hp']}: {e}")
        moved = False
        for attempt in range(2):  # next one; a swipe that does nothing twice = end of the list
            swipe_next(bounds)  # (the bounds don't change on the detail page)
            for _ in range(10):
                time.sleep(0.12)
                screen, texts, _, _ = look()
                if screen == "detail" and (lambda i: (i["name"], i["cp"], i["hp"]))(ui.detail_info(texts)) not in seen:
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
    go("close", "list")
    return done


def cmd_tag(limit):
    plan_f = newest(os.path.join("runs", "*-plan", "plan.json"))
    if not plan_f:
        sys.exit("no plan yet: python3 tradeable.py plan")
    plan = json.load(open(plan_f))
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-tag"))
    who = home.trainer()
    if who != GIVER:
        raise Stop(f"signed in as {who!r}: tag needs {GIVER}")
    search.to_search_list()
    done_f = os.path.join(os.path.dirname(plan_f), "tagged.json")  # this plan's searches already tagged: a rerun
    done = set(json.load(open(done_f))) if os.path.exists(done_f) else set()  # skips them (14 s each, even at 0)
    for t in TAGS:  # each search leaves out all three tags: the first that fits wins, and a rerun skips what's done
        for q in plan["tags"][t]:
            if q + NOT_TAGGED in done:
                continue
            ct.tag_pile(SHORTCUT, t, q + NOT_TAGGED)
            done.add(q + NOT_TAGGED)
            json.dump(sorted(done), open(done_f, "w"))
    if done:
        log(f"{len(done)} tag search(es) done for this plan (a new plan starts over)")
    # (HashTagAJay's 360+ XL families are passed on the detail page: as '&!<dex>' terms they'd overflow the bar)
    traded = "&" + ",".join(f"#{t}" for t in TAGS)
    rest = NOT_TAGGED + f"&!#{XLX}&!#{TRANSFER}"
    unsure, power_ok = [], True
    # power-ups for the traded ones (HashTagAJay transfers them), then XLX and power-ups for the rest
    for suffix, xlx, power, skip in [(traded, False, True, set(plan["taker_xl_full"])),
                                     (rest + ct.UNDER_360_XL, True, True, ()),
                                     (rest + f"&countcandyxl{XL_CAP}-", True, False, ())]:
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
    ct.tag_pile(SHORTCUT, TRANSFER, rest)


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"refresh": cmd_refresh, "plan": cmd_plan}
    if not a or a[0] not in (*cmds, "read", "tag"):
        sys.exit(__doc__)
    try:
        if a[0] == "read":
            cmd_read(a[1] if len(a) > 1 else None)
        elif a[0] == "tag":
            cmd_tag(int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9)
        else:
            cmds[a[0]]()
    except Stop as e:
        log(f"STOPPED: {e}")
        sys.exit(1)
    finally:
        if base.RUN_DIR:
            log(f"run folder: {base.RUN_DIR}")
