#!/usr/bin/env python3
"""/roster: HashTagAJay's best 6 raid attackers against every raid boss, and which species a new traded copy would
still help with. Android only for now.

  node pull.mjs                                                 the bosses' counter lists from DialgaDex (Mac)
  POGO_PHONE=android caffeinate -dimsu python3 roster.py count  count the good copies by search (taps the phone)
  python3 roster.py report [counts.json]                        the top 6s and the trade list again (Mac only)

A good copy is 3★ or 4★. Shadows are counted apart. An earlier stage counts as its evolution (a 4★ Gastly is a
Gengar). In a branched family, each unevolved copy counts for one branch only: the one on the most boss lists.

The counting only searches what it needs. It walks every boss's list from the top, and searches a species when a
boss's 6 aren't filled yet by the time the walk gets to it. Then it walks again, until every boss has 6 or its list
runs out.

Each boss's 6: down its list, a slot per owned copy, at most one mega (or primal) and only with a copy of its base
species. A new traded copy of a species (never shadow) helps against a boss if it would get into those 6. #1 is
Reroll, #2-#6 is GIV. Legendary, Mythical and Ultra Beast species are never tagged (traded by hand).
Output in runs/<time>-count/: counts.json, roster.json (for /cleanup's tradeable.py) and report.md.
"""
import argparse, glob, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.insert(0, os.path.join(HERE, "..", "dex"))
import dex
from run import Stop, log

TRAINER = "HashTagAJay"
GOOD = "3*,4*"
TEAM = 6
POPULAR = 15  # a branch is "on a boss list" when it's in the top this many
APEX = {249, 250}  # form "S" in DialgaDex: Apex Lugia and Ho-Oh (shadow or purified, from research)
SPECIAL = ("legendary", "mythical", "ultrabeast")
GATE = [(383, "Normal"), (382, "Normal"), (384, "Normal"), (150, "Normal"), (483, "Normal")]
NO_MOVE_TERM = re.compile(r"^(count|dynamax|gigantamax)|[()]")  # see SEARCH.md: these break an @ search


def newest(pattern):
    paths = sorted(glob.glob(os.path.join(HERE, pattern)))
    return paths[-1] if paths else None


def is_mega(a):
    return a["form"].startswith("Mega") or a["name"].startswith("Primal")


def region(sid):
    return next((r for r in dex.REGIONS if r in sid), None)


class Model:
    def __init__(self, data):
        self.data = data
        self.by, self.parent = dex.evo_tree()
        self.A = data["attackers"]
        self.bosses = data["bosses"]
        self.sid = [self.sid_of(a) for a in self.A]
        self.moves = {}  # sid -> every move any of its forms can know
        for a, s in zip(self.A, self.sid):
            if s and not is_mega(a):
                self.moves.setdefault(s, set()).update(a.get("moves") or [])
        self.all_moves = {m for ms in self.moves.values() for m in ms}
        self.assign = self.branches()

    def sid_of(self, a):
        cands = [s for s, p in self.by.items() if p["dex"] == a["id"]]
        if not cands:
            return None
        f = "normal" if is_mega(a) else a["form"].lower()
        f = {"alola": "alolan", "a": "armored"}.get(f, f)
        hits = [s for s in cands if s.endswith("_" + f)]  # (Unova 'Standard' Darmanitan vs darmanitan_galarian_standard)
        if hits:
            return next((s for s in hits if (region(s) or "_")[1:] in f), hits[0])
        plain = [s for s in cands if not region(s)]
        return next((s for s in plain if "_" not in s), (plain or cands)[0])

    def group(self, i):
        a = self.A[i]
        return "apex" if a["id"] in APEX and a["form"] == "S" else None

    def special(self, sid):
        return any(t in (self.by[sid].get("tags") or []) for t in SPECIAL)

    def ancestors(self, sid):
        """the earlier stages a copy of which could become this one (a regional form only from its own region)"""
        return [x for x in dex.ancestors(sid, self.parent) if region(sid) is None or region(x) == region(sid)]

    def branches(self):
        """each earlier stage -> the one later stage its copies count for: the one on the most boss lists"""
        pop = {}
        for b in self.bosses:
            for i, *_ in b["list"][:POPULAR]:
                if self.sid[i]:
                    pop[self.sid[i]] = pop.get(self.sid[i], 0) + 1
        targets = {}
        for s in {s for s in self.sid if s}:
            for x in self.ancestors(s):
                targets.setdefault(x, set()).add(s)
        return {x: max(ts, key=lambda s: (pop.get(s, 0), s)) for x, ts in targets.items()}

    def pools(self, i):
        """the piles of copies attacker i can take a copy from, its own first"""
        s, a = self.sid[i], self.A[i]
        if not s:
            return []
        shadow = False if is_mega(a) else a["shadow"]
        own = [(s, None if is_mega(a) else self.group(i), shadow)]
        return own + [(x, None, shadow) for x in self.ancestors(s) if self.assign.get(x) == s]

    # ---------- the 6 against one boss ----------

    def team(self, boss, counts, extra=None, need=None):
        """-> [(attacker index, rating)] best first. extra: one more copy in this pile. need: a set to add the piles
        it couldn't count to (the walk stops there)"""
        left = dict(counts)
        if extra:
            left[extra] = left.get(extra, 0) + 1
        out, mega = [], False
        for i, rat, *_ in boss["list"]:
            if len(out) >= TEAM:
                break
            if is_mega(self.A[i]) and mega:
                continue
            ps = self.pools(i)
            unknown = [p for p in ps if p not in left]
            if unknown:
                if need is not None:
                    need.update(unknown)
                    return out
                ps = [p for p in ps if p in left]
            while len(out) < TEAM:
                p = next((p for p in ps if left[p] > 0), None)
                if not p:
                    break
                left[p] -= 1
                out.append((i, rat))
                if is_mega(self.A[i]):
                    mega = True
                    break
        return out

    def helps(self, counts):
        """species -> (best place a new copy would get, the bosses where it gets that place)"""
        best = {}
        cands = {s for s in self.sid if s}
        for b in self.bosses:
            base = self.team(b, counts)
            on = {self.sid[i] for i, *_ in b["list"]}
            for s in cands & on:
                new = self.team(b, counts, extra=(s, None, False))
                place = next((k + 1 for k, (x, y) in enumerate(zip(new, base + [None] * TEAM)) if x != y), None)
                if place:
                    p, bs = best.get(s, (99, []))
                    if place < p:
                        best[s] = (place, [boss_name(b)])
                    elif place == p:
                        bs.append(boss_name(b))
        return best


def boss_name(b):
    return b["name"] + ("" if b["form"] in ("Normal", "Mega") else f" ({b['form']})")


def attacker_name(a):
    return ("Shadow " if a["shadow"] else "") + a["name"] + \
        ("" if is_mega(a) or a["form"] in ("Normal",) else f" ({a['form'].replace('_', ' ')})")


# ---------- counting on the phone ----------

def move_term(m):
    m = m.replace("_", " ").lower()
    if NO_MOVE_TERM.search(m):
        return None
    return m


def plan(model, pools):
    """the pools to count -> [(dex, region, [sids])]: each species' forms that one set of searches splits"""
    out = {}
    for s, g, sh in pools:
        out.setdefault((model.by[s]["dex"], region(s)), set())
    for s in {s for s in model.sid if s} | set(model.assign):
        k = (model.by[s]["dex"], region(s))
        if k in out:
            out[k].add(s)
    return [(d, r, sorted(ss)) for (d, r), ss in sorted(out.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))]


def count_class(model, d, sids, n, unsure):
    """count every pile of these forms of dex d. n(query) -> result count"""
    q = f"{d}&{GOOD}{dex.form_terms(sids[0], model.by)}"
    tot = n(q)
    sh = n(q + "&shadow") if tot else 0
    got = {}
    if len(sids) == 1:
        s = sids[0]
        got[(s, None, False)], got[(s, None, True)] = tot - sh, sh
        if d in APEX:
            ap_sh = n(q + "&research&shadow") if sh else 0
            ap_pu = n(q + "&research&purified") if tot - sh else 0
            got[(s, "apex", True)], got[(s, "apex", False)] = ap_sh, ap_pu
            got[(s, None, True)] -= ap_sh
            got[(s, None, False)] -= ap_pu
        return got
    # several forms a search can't name (Kyurem White/Black, Origin/Altered...): split by the moves only one form knows
    rest = {False: tot - sh, True: sh}
    for s in sids:
        others = set().union(*(model.moves.get(x, set()) for x in sids if x != s))
        mine = sorted(m for m in model.moves.get(s, set()) - others if move_term(m)
                      and not any(o != m and o.lower().startswith(m.lower()) for o in model.all_moves))
        if not mine or not tot:
            got[(s, None, False)] = got[(s, None, True)] = 0
            continue
        mq = q + "&" + ",".join("@" + move_term(m) for m in mine)
        t = n(mq)
        st = n(mq + "&shadow") if t else 0
        got[(s, None, False)], got[(s, None, True)] = t - st, st
        rest[False] -= t - st
        rest[True] -= st
    weakest = min(sids, key=lambda s: sum(1 for b in model.bosses for i, *_ in b["list"][:POPULAR]
                                          if model.sid[i] == s))
    for sh_, left in rest.items():
        if left < 0:
            unsure.append(f"#{d} {'/'.join(sids)}: the move searches found more than the species search")
            left = 0
        got[(weakest, None, sh_)] += left
        if left:
            unsure.append(f"#{d}: {left} {'shadow ' if sh_ else ''}{model.by[weakest]['speciesName']} by guess "
                          f"(no move only one form knows). Check its form by hand")
    return got


def save(path, counts, unsure):
    json.dump({"counts": [[*k, v] for k, v in counts.items()], "unsure": unsure}, open(path, "w"), indent=0)


def load_counts(path):
    j = json.load(open(path))
    return {(s, g, bool(sh)): v for s, g, sh, v in j["counts"]}, j.get("unsure", [])


def cmd_count(model, resume):
    import home, run as base
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-count"))
    who = home.trainer()
    if who != TRAINER:
        raise Stop(f"{who} is signed in: /roster counts {TRAINER}'s Pokémon")
    counts, unsure = load_counts(resume) if resume else ({}, [])
    home.start()
    cache = {}

    lost = [0]

    def n(q):
        """one search's count. A run that loses its way (a tap that lands on the map) goes back to the list and
        searches again: twice per search, 20 times in all"""
        for attempt in range(3):
            if q in cache:
                break
            try:
                cache[q] = dex.search_exact(q)
                log(f"  {q}: {cache[q]}")
            except Stop as e:
                lost[0] += 1
                if attempt == 2 or lost[0] > 20:
                    raise
                log(f"  {q}: {e}: back to the Pokémon list, again")
                home.start()
        return cache[q]

    for rnd in range(1, 200):
        need = set()
        for b in model.bosses:
            model.team(b, counts, need=need)
        if not need:
            break
        todo = plan(model, need)
        log(f"round {rnd}: {len(todo)} species to count")
        for d, r, sids in todo:
            counts.update(count_class(model, d, sids, n, unsure))
            save(os.path.join(base.RUN_DIR, "counts.json"), counts, unsure)
    log(f"counted {len(cache)} searches")
    return counts, unsure, base.RUN_DIR


# ---------- report ----------

def report(model, counts, unsure, out_dir):
    best = model.helps(counts)
    reroll = sorted(s for s, (p, _) in best.items() if p == 1 and not model.special(s))
    giv = sorted(s for s, (p, _) in best.items() if 2 <= p <= TEAM and not model.special(s))
    seen = {s for s in model.sid if s and not model.special(s)}
    stop = sorted(seen - set(reroll) - set(giv))
    name = lambda s: model.by[s]["speciesName"]
    json.dump({"pulled": model.data.get("pulled"), "trainer": TRAINER,
               "species": {s: {"place": p, "bosses": bs[:10], "special": model.special(s)} for s, (p, bs) in best.items()},
               "reroll": reroll, "giv": giv},
              open(os.path.join(out_dir, "roster.json"), "w"), indent=1)

    def team_lines(b):
        t = model.team(b, counts)
        rows = []
        for i, rat in t:
            a = attacker_name(model.A[i])
            if rows and rows[-1][0] == a:
                rows[-1][1] += 1
            else:
                rows.append([a, 1, rat])
        return ", ".join(f"{a}{f' x{k}' if k > 1 else ''} ({r:.0f})" for a, k, r in rows) + \
            (f"  [only {len(t)}]" if len(t) < TEAM else "")

    lines = [f"# /roster: {TRAINER}'s top 6 per raid boss",
             f"DialgaDex counters pulled {model.data.get('pulled')}. Good copy = 3★/4★. Rating = DialgaDex's.", "",
             "## Check these first", ""]
    for d, f in GATE:
        b = next((b for b in model.bosses if b["id"] == d and b["form"] == f), None)
        if b:
            lines.append(f"- **{boss_name(b)}**: {team_lines(b)}")
    lines += ["", f"Reroll (a new copy would be #1 somewhere): {len(reroll)}. "
              f"GIV-PvE (#2-#6): {len(giv)}. On a list but helps nowhere: {len(stop)}.", ""]
    lines += ["## Reroll", ""] + [f"- {name(s)}: #1 vs {', '.join(best[s][1][:6])}" for s in reroll]
    lines += ["", "## GIV-PvE", ""] + [f"- {name(s)}: #{best[s][0]} vs {', '.join(best[s][1][:6])}" for s in giv]
    lines += ["", "## Stop trading for (on a boss list, but a new copy gets into no top 6)", "",
              ", ".join(name(s) for s in stop)]
    if unsure:
        lines += ["", "## Counted by guess", ""] + [f"- {u}" for u in unsure]
    lines += ["", "## Every boss", ""]
    for b in model.bosses:
        lines.append(f"- {boss_name(b)}{' (unreleased)' if not b['released'] else ''}: {team_lines(b)}")
    path = os.path.join(out_dir, "report.md")
    open(path, "w").write("\n".join(lines) + "\n")
    return path, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("count", "report"))
    ap.add_argument("counts", nargs="?", help="count: carry on from this counts.json. report: which (default newest)")
    a = ap.parse_args()
    data_path = newest("dialgadex-counters-[0-9]*[0-9].json")  # (not a -test<n> pull)
    if not data_path:
        sys.exit("no counters yet: node pull.mjs")
    model = Model(json.load(open(data_path)))
    if a.counts and not os.path.exists(a.counts):  # (runs/... is under the skill folder)
        a.counts = os.path.join(HERE, a.counts)
    try:
        if a.cmd == "count":
            import ui
            if not ui.ANDROID:
                sys.exit("Android only for now: POGO_PHONE=android")
            counts, unsure, out = cmd_count(model, a.counts)
        else:
            path = a.counts or newest("runs/*-count/counts.json")
            if not path:
                sys.exit("no counts yet: roster.py count")
            counts, unsure = load_counts(path)
            out = os.path.dirname(path)
            need = set()
            for b in model.bosses:
                model.team(b, counts, need=need)
            if need:  # a stopped count, or a newer pull with attackers it never counted
                sys.exit(f"{path} misses {len(need)} piles ({', '.join(sorted({s for s, *_ in need})[:8])}...): "
                         f"finish it with roster.py count {path.replace(HERE + os.sep, '')}")
        path, lines = report(model, counts, unsure, out)
        end = lines.index("## Reroll")
        print("\n".join(lines[:end]))
        print(f"report: {path}")
    except Stop as e:
        log(f"STOPPED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
