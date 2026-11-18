#!/usr/bin/env python3
"""/raidteam: the signed-in account's best 6 raid attackers against every released raid boss like a 4-star raid's
or higher, at the level and IVs its copies have today (the user, 2026-11-17). Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 raidteam.py count [copies.json] [--limit N]
                                       count whoever is signed in; with a copies.json, carry on from it.
                                       --limit N: only the first N bosses (a test)
  python3 raidteam.py report [copies.json]   the teams again (Mac only)
  pogo.py raidteam count                     the same, through the front door

What it's for: a Pokémon on some team is a favorite, whatever its IVs (a Mighty one, a traded one powered up long
ago). One that falls off every team, because something better got powered up, is judged again and can be traded or
transferred. A better copy that isn't powered up yet doesn't push anything out: only what each copy is today counts.

Bosses: roster.real_boss() and released, in both DialgaDex pulls (Party Power off, a party of 2: a team in either
counts). Every attacker on a boss's list counts, legendary, shadow and mega too: these are the account's own teams. A
mega is a copy of its species, at that copy's level and IVs, one mega per team. Ratings are DialgaDex's own (rate.mjs):
best moves with Elite TMs, so a copy's real moves don't count. Only the attackers on DialgaDex's lists (80 deep) count.

How it counts. A pile is one storage search: the species' dex number, its form terms, and shadow or !shadow. Its list
is sorted by CP, highest first, and walked from the top. A tile's CP caps the copy's level (no IVs give that CP any
higher), so a 15/15/15 at that level caps its rating. Once that cap can't beat a boss's 6th, no copy further down can
either, and the walk stops. Like roster.py it goes round by round: each boss asks for the first pile on its list whose
cap still beats its 6th, and those piles are walked, until no boss asks.
An opened copy: CP, HP and the power-up cost on the page's top (no drag) give the level and the IVs that fit
(powerup.cost_levels). The database (pokedb) may know its IVs. Still more than one fit, and the best of them could beat
some boss's 6th: the appraisal gives them.

Output in runs/<time>-raidteam/: copies.json (every copy opened, saved after each pile: a stopped count carries on
from it), teams.json (../shared/raidteams.py reads it, for the door and /ivc) and report.md. teams.json: per boss its 6; every copy opened, with the
bosses it's on; per pile, the lowest CP a copy could make some team at (bar). A copy under its pile's bar can't be on
any team. One over it that isn't among the opened ones came or grew after the count.
"""
import argparse, json, math, os, re, subprocess, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.insert(0, os.path.join(HERE, "..", "dex"))
import dex, pvp
import roster
from roster import COUNTERS, is_mega, real_boss, boss_name, attacker_name
from base import Stop, Skip, log, newest

TEAM = roster.TEAM
HUNDO = (15, 15, 15)
CHUNK = 4  # needs(): piles of each boss's list rated per line to rate.mjs
RUNS = os.path.join(HERE, "runs")
RATE = os.path.join(HERE, "rate.mjs")


# ---------- the rater (DialgaDex's own math, rate.mjs) ----------

class Rater:
    """one rate.mjs for the whole run: a line of JSON in, a line out. Every answer is kept"""

    def __init__(self):
        self.p = None
        self.cache = {}
        self.party = None  # rate.mjs's party size now

    def start(self):
        self.p = subprocess.Popen(["node", RATE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        line = self.p.stdout.readline()
        if '"ready"' not in line:
            raise Stop(f"rate.mjs didn't start: {line.strip() or 'no answer'} (Playwright: see pull.mjs)")

    def key(self, party, boss, ask):
        a, lv, ivs = ask
        return (party, boss["id"], boss["form"], a["id"], a["form"], bool(a["shadow"]), lv, tuple(ivs))

    def rate(self, party, boss, asks):
        """asks: [(attacker dict, level, ivs)] against this boss -> [rating or None], from the cache when it can"""
        self.warm([(party, boss, asks)])
        return [self.cache[self.key(party, boss, x)] for x in asks]

    def warm(self, groups):
        """[(party, boss, asks)]: rate every one not known yet, in one line to rate.mjs"""
        todo = {}
        for party, boss, asks in groups:
            for x in asks:
                k = self.key(party, boss, x)
                if k not in self.cache:
                    todo.setdefault((party, boss["id"], boss["form"]), {})[k] = x
        if not todo:
            return
        if self.p is None:
            self.start()
        todo = dict(sorted(todo.items(), key=lambda t: t[0][0] != self.party))  # a party switch costs ~30 ms
        self.party = next(reversed(todo))[0]
        q = {"groups": [{"party": pa, "boss": {"id": i, "form": f},
                         "copies": [{"id": a["id"], "form": a["form"], "shadow": bool(a["shadow"]), "level": lv,
                                     "ivs": list(v)} for a, lv, v in xs.values()]}
                        for (pa, i, f), xs in todo.items()]}
        self.p.stdin.write(json.dumps(q) + "\n")
        self.p.stdin.flush()
        got = json.loads(self.p.stdout.readline() or "{}")
        if "groups" not in got:
            raise Stop(f"rate.mjs: {got.get('error') or 'no answer'}")
        for xs, rats in zip(todo.values(), got["groups"]):
            self.cache.update(zip(xs, rats))

    def close(self):
        if self.p:
            self.p.stdin.close()
            self.p.wait(timeout=30)


# ---------- piles, copies and teams (no phone) ----------

def stats(sid):
    return pvp.SPECIES[sid]["baseStats"]


def top_level(sid, cp):
    """the highest level any IVs give this species a CP of cp or less at (0/0/0 there). No CP read: 50"""
    if not cp:
        return pvp.LEVELS[-1]
    b = stats(sid)
    return max((lv for lv in pvp.LEVELS if pvp.cp(b, (0, 0, 0), lv) <= cp), default=pvp.LEVELS[0])


def fits(sids, cp, hp, levels=None):
    """[(sid, level, ivs)] that give exactly this CP and HP, at these levels (None: any)"""
    out = []
    for s in sids:
        if s not in pvp.SPECIES:
            continue
        b = stats(s)
        for lv in levels or pvp.LEVELS:
            hs = [h for h in range(16) if pvp.hp(b, (0, 0, h), lv) == hp]
            out += [(s, lv, (a, d, h)) for h in hs for a in range(16) for d in range(16) if pvp.cp(b, (a, d, h), lv) == cp]
    return out


class Count:
    """the counting state for one account: the two pulls' bosses, the piles, the copies opened so far"""

    def __init__(self, models, rater, limit=None):
        self.rater = rater
        self.limit = limit
        self.pairs = []  # (model, boss): a boss in one pull
        for m in models:
            bs = [b for b in m.bosses if b["released"] and real_boss(b)]
            self.pairs += [(m, b) for b in bs[:limit]]
        self.piles = {}  # query -> {"sids", "shadow", "dex"}: one storage search
        self.of = {}  # (id(model), attacker index) -> query
        for m, b in self.pairs:
            for i, *_ in b["list"]:
                if (id(m), i) not in self.of:
                    self.of[(id(m), i)] = self.pile(m, i)
        self.ent = {}  # (id(model), id(boss)) -> {query: [attacker index]}: each pile's attackers on that list
        for m, b in self.pairs:
            e = self.ent[(id(m), id(b))] = {}
            for i, *_ in b["list"]:
                if self.of[(id(m), i)]:
                    e.setdefault(self.of[(id(m), i)], []).append(i)
        self.walk = {q: {"next_cp": None, "end": False} for q in self.piles}
        self._sixth = {}  # (id(model), id(boss)) -> (copies counted, 6th): teams only change with a new copy
        self.counted = time.strftime("%Y-%m-%d %H:%M")
        self.copies = []  # dicts: q, name, tile_cp, cp, hp, kg, m, fits [(sid, level, ivs)], ivs_sure. Or skip: why not
        self.sorted = False  # the list sorted by CP this run

    def pile(self, m, i):
        a, s = m.A[i], m.sid[i]
        if not s or s not in pvp.SPECIES:
            return None
        shadow = bool(a["shadow"]) and not is_mega(a)
        terms = dex.form_terms(s, m.by)
        q = f"{m.by[s]['dex']}{terms}&{'shadow' if shadow else '!shadow'}"
        if q not in self.piles:
            d = m.by[s]["dex"]
            self.piles[q] = {"dex": d, "shadow": shadow,
                             "sids": sorted(x for x, p in m.by.items() if p["dex"] == d and dex.form_terms(x, m.by) == terms)}
        return q

    def entries(self, m, b, q):
        """the attackers of this pile on this boss's list"""
        return self.ent[(id(m), id(b))].get(q, [])

    def cap_asks(self, m, b, q, cp):
        return [(m.A[i], top_level(m.sid[i], cp), HUNDO) for i in self.entries(m, b, q)]

    def cap(self, m, b, q, cp):
        """the best rating any copy of pile q with this CP or less could have against this boss"""
        return max((r or 0 for r in self.rater.rate(m.data["party"], b, self.cap_asks(m, b, q, cp))), default=0)

    def warm_caps(self, wants):
        """[(m, b, q, cp)]: every cap() these will ask for, in one line to rate.mjs"""
        self.rater.warm([(m.data["party"], b, self.cap_asks(m, b, q, cp)) for m, b, q, cp in wants])

    def option_asks(self, m, b):
        asks, who = [], []
        for k, c in enumerate(self.copies):
            for i in self.entries(m, b, c["q"]):
                s = m.sid[i]
                for fs, lv, ivs in c["fits"]:
                    if fs == s:
                        asks.append((m.A[i], lv, ivs))
                        who.append((k, i))
        return asks, who

    def options(self, m, b):
        """[(rating, copy index, attacker index)] for every opened copy that fits an attacker on this list"""
        asks, who = self.option_asks(m, b)
        best = {}
        for (k, i), r in zip(who, self.rater.rate(m.data["party"], b, asks)):
            if r is not None and r > best.get((k, i), -1):  # IVs not sure: its best fit (the side that keeps)
                best[(k, i)] = r
        return sorted(((r, k, i) for (k, i), r in best.items()), reverse=True)

    def team(self, m, b):
        """-> [(rating, copy index, attacker index)]: the 6, best first. A copy takes one spot, one mega a team"""
        out, used, mega = [], set(), False
        for r, k, i in self.options(m, b):
            if len(out) >= TEAM:
                break
            if k in used or (is_mega(m.A[i]) and mega):
                continue
            used.add(k)
            mega = mega or is_mega(m.A[i])
            out.append((r, k, i))
        return out

    def sixth(self, m, b):
        k = (id(m), id(b))
        if self._sixth.get(k, (None,))[0] != len(self.copies):
            t = self.team(m, b)
            self._sixth[k] = (len(self.copies), t[-1][0] if len(t) >= TEAM else 0)
        return self._sixth[k][1]

    def warm_sixths(self, pairs=None):
        """every pair's 6th, in one line to rate.mjs"""
        todo = [(m, b) for m, b in pairs or self.pairs if self._sixth.get((id(m), id(b)), (None,))[0] != len(self.copies)]
        self.rater.warm([(m.data["party"], b, self.option_asks(m, b)[0]) for m, b in todo])

    def listing(self, q):
        return [(m, b) for m, b in self.pairs if self.entries(m, b, q)]

    def beats(self, q, cp, pairs=None):
        """the pairs (of these, else all listing q) whose 6th a copy of pile q with this CP could still beat"""
        pairs = self.listing(q) if pairs is None else pairs
        self.warm_sixths(pairs)
        self.warm_caps([(m, b, q, cp) for m, b in pairs])
        return [(m, b) for m, b in pairs if self.cap(m, b, q, cp) > self.sixth(m, b)]

    def wanted(self, q):
        """the pairs whose 6th the next copy in pile q could still beat"""
        return self.beats(q, self.walk[q]["next_cp"])

    def needs(self):
        """each boss: the first pile on its list not walked to its end whose next copy could beat its 6th"""
        self.warm_sixths()
        left = {}  # each pair still looking: its piles not walked to the end, in list order (dict: first place)
        for m, b in self.pairs:
            left[(id(m), id(b))] = (m, b, [q for q in self.ent[(id(m), id(b))] if not self.walk[q]["end"]])
        need = []
        while left:  # a few piles of each pair at a time: most find theirs in the first few
            self.warm_caps([(m, b, q, self.walk[q]["next_cp"]) for m, b, qs in left.values() for q in qs[:CHUNK]])
            for k, (m, b, qs) in list(left.items()):
                r6 = self.sixth(m, b)
                hit = next((q for q in qs[:CHUNK] if self.cap(m, b, q, self.walk[q]["next_cp"]) > r6), None)
                if hit or len(qs) <= CHUNK:
                    del left[k]
                    if hit and hit not in need:
                        need.append(hit)
                else:
                    left[k] = (m, b, qs[CHUNK:])
        return need

    def could_help(self, q, fits_):
        """the best of these fits could beat some listing boss's 6th"""
        pairs = self.listing(q)
        self.warm_sixths(pairs)
        groups = [(m, b, [(m.A[i], lv, ivs) for i in self.entries(m, b, q) for s, lv, ivs in fits_ if s == m.sid[i]])
                  for m, b in pairs]
        self.rater.warm([(m.data["party"], b, asks) for m, b, asks in groups])
        return any(asks and max(r or 0 for r in self.rater.rate(m.data["party"], b, asks)) > self.sixth(m, b)
                   for m, b, asks in groups)

    def bars(self):
        """pile -> the lowest CP a copy of it could make some team at today (None: none could). A cap only changes
        where some form's 0/0/0 CP is, and grows with the CP: the first of those whose cap beats some 6th. Every
        pile's search goes a step at a time together, so each step is one line to rate.mjs"""
        self.warm_sixths()
        cps = {q: sorted({pvp.cp(stats(x), (0, 0, 0), lv) for x in p["sids"] if x in pvp.SPECIES for lv in pvp.LEVELS})
               for q, p in self.piles.items()}
        lst = {q: self.listing(q) for q in self.piles}
        self.warm_caps([(m, b, q, cps[q][-1]) for q in self.piles if cps[q] for m, b in lst[q]])
        span = {q: [0, len(cps[q]) - 1] for q in self.piles if cps[q] and self.any_beats(q, cps[q][-1], lst[q])}
        while any(lo < hi for lo, hi in span.values()):
            self.warm_caps([(m, b, q, cps[q][(lo + hi) // 2]) for q, (lo, hi) in span.items() if lo < hi for m, b in lst[q]])
            for q, sp in span.items():
                lo, hi = sp
                if lo < hi:
                    mid = (lo + hi) // 2
                    sp[:] = [lo, mid] if self.any_beats(q, cps[q][mid], lst[q]) else [mid + 1, hi]
        return {q: cps[q][span[q][0]] if q in span else None for q in self.piles}

    def any_beats(self, q, cp, pairs):
        return any(self.cap(m, b, q, cp) > self.sixth(m, b) for m, b in pairs)

    # ---------- saving ----------

    def state(self, who):
        return {"trainer": who, "counted": self.counted, "copies": self.copies, "walk": self.walk,
                "limit": self.limit, "pulls": [m.data.get("pulled") for m in {id(m): m for m, _ in self.pairs}.values()]}

    def load(self, j):
        self.copies = [dict(c, fits=[(s, lv, tuple(v)) for s, lv, v in c["fits"]]) for c in j["copies"]]
        self.counted = j.get("counted", self.counted)  # a carry-on keeps its count's start
        for q, w in j["walk"].items():
            if q in self.walk:
                self.walk[q] = w

    def teams(self, who):
        """teams.json: what ../shared/raidteams.py reads"""
        out = {"trainer": who, "counted": self.counted, "limit": self.limit, "bosses": {}, "copies": [], "bars": {}}
        on = {}
        self.warm_sixths()
        for m, b in self.pairs:
            key = f"{boss_name(b)} (party {m.data['party']})"
            t = self.team(m, b)
            out["bosses"][key] = [{"attacker": attacker_name(m.A[i]), "rating": round(r, 2), "copy": k} for r, k, i in t]
            for r, k, i in t:
                on.setdefault(k, []).append(key)
        for k, c in enumerate(self.copies):
            out["copies"].append({"species": sorted({s for s, *_ in c["fits"]}), "shadow": self.piles[c["q"]]["shadow"],
                                  "cp": c.get("cp", c["tile_cp"]), "hp": c.get("hp"), "kg": c.get("kg"), "m": c.get("m"),
                                  "name": c["name"],
                                  "levels": sorted({lv for _, lv, _ in c["fits"]}),
                                  "ivs": sorted({v for *_, v in c["fits"]}) if len({v for *_, v in c["fits"]}) <= 4 else None,
                                  "on": on.get(k, []), "skip": c.get("skip")})
        bars = self.bars()
        for q, p in self.piles.items():
            for x in p["sids"]:
                out["bars"][f"{x}{'|shadow' if p['shadow'] else ''}"] = bars[q]
        return out


def models():
    files = [newest(HERE, c) for c in COUNTERS]
    if not all(files):
        sys.exit(f"no DialgaDex counters yet ({' and '.join(COUNTERS)}): node {os.path.join(HERE, 'pull.mjs')}")
    return [roster.Model(json.load(open(f))) for f in files]


# ---------- the phone ----------

class Enough(Exception):
    """this tile's cap can't beat the 6th of any boss that asked: neither can the rest of the list"""


def by_cp(ts):
    """the tiles' CPs go down, top to bottom (a CP not read is passed over)"""
    cps = [cp for _, cp in ts if cp]
    return all(x >= y for x, y in zip(cps, cps[1:]))


def walk_pile(c, q, asked):
    """walk pile q's list from the top, sorted by CP, highest first. asked: the pairs that wanted it this round"""
    import base, search, taps, ui
    from tagsheet import search_exact
    w = c.walk[q]
    search_exact(q)
    ts = taps.settled_tiles()
    if not ts:
        log(f"  {q}: none")
        w["end"] = True
        return
    if not c.sorted or not by_cp(ts):  # a search keeps the list's sort: once is enough, unless it changed
        _, _, _, bounds = base.look()
        _, texts, _ = search.sort_down("COMBAT POWER", bounds)
        c.sorted = True
        if not by_cp([(n, cp) for n, cp, _, _ in ui.tiles(texts)]):
            raise Stop(f"{q}: sorted by Combat Power, but the CPs don't go down")
    passed = Counter((x["name"], x["tile_cp"]) for x in c.copies if x["q"] == q)

    def want(name, cp):
        if passed[(name, cp)] > 0:  # opened before: walk_list passes it over
            return True
        if not c.beats(q, cp, asked):
            w["next_cp"] = cp
            raise Enough()
        return True

    def visit(i, name, cp):
        try:
            info, texts, _ = base.open_checked(i, name, cp, name_ok=True)
            one = read_copy(c, q, c.piles[q], info, texts, name, cp)
            c.copies.append(one)
            lvs = "/".join(map(str, sorted({lv for _, lv, _ in one["fits"]})))
            log(f"  {name} CP{one['cp']}: level {lvs}, IVs {'sure' if one['ivs_sure'] else str(len(one['fits'])) + ' fits'}")
        except Skip as e:
            log(f"  {name} CP{cp}: passed ({e})")
            c.copies.append({"q": q, "name": name, "tile_cp": cp, "skip": str(e), "fits": []})  # not opened again on a carry-on
        base.back_to_list()
        return False

    try:
        if search.walk_list(visit, want=want, passed=passed):
            w["end"] = True
    except Enough:
        pass


def read_copy(c, q, p, info, texts, name, tile_cp):
    """the opened page -> a copy dict, or None (not this pile's, or nothing fits its CP and HP)"""
    import base, powerup, pokedb
    if base.is_shadow(texts) != p["shadow"]:
        raise Skip(f"{'not ' if p['shadow'] else ''}a shadow, but in the {q} search")
    cp, hp = info["cp"] or tile_cp, info["hp"]
    _, lvs = powerup.cost_levels(texts, cp)
    got = fits(p["sids"], cp, hp, lvs or None)
    if not got and lvs:
        got = fits(p["sids"], cp, hp)  # a cost misread: CP and HP alone
    if not got:
        raise Skip(f"no level and IVs give CP{cp} {hp} HP")
    kg, m = (base.OPENED.get("who") or (None,) * 4)[2:]
    known = [r for r in pokedb.find(cp=cp, hp=hp)
             if r.get("atk") is not None and base.same_pokemon((cp, hp, kg, m), (r["cp"], r["hp"], r["kg"], r["m"]))]
    if len(known) == 1:
        sure = [f for f in got if f[2] == (known[0]["atk"], known[0]["def"], known[0]["sta"])]
        got = sure or got
    if len({f[2] for f in got}) > 1 and c.could_help(q, got):
        try:
            base.open_appraisal()
            ivs, raws = base.appraise()
            ivs = base.exact_ivs(sorted({s for s, *_ in got}), cp, hp, ivs, raws)
            got = [f for f in got if f[2] == tuple(ivs)] or got
        except Skip as e:
            log(f"  appraisal: {e}: its best fit counts")
    return {"q": q, "name": name, "tile_cp": tile_cp, "cp": cp, "hp": hp, "kg": kg, "m": m, "fits": got,
            "ivs_sure": len({f[2] for f in got}) == 1}


def cmd_count(c, resume, out_dir):
    import home, search
    home.start()  # opens the phone and takes its lock, as every script does
    who = home.trainer()
    if resume:
        j = json.load(open(resume))
        if j["trainer"] != who:
            raise Stop(f"{resume} is {j['trainer']}'s count, but {who} is signed in")
        c.load(j)
        log(f"carrying on: {len(c.copies)} copies opened before")
    search.to_search_list()  # (trainer() can end on the map)
    path = os.path.join(out_dir, "copies.json")
    log(f"stopped? carry on with: raidteam.py count {path}" + (f" --limit {c.limit}" if c.limit else ""))
    for rnd in range(1, 500):
        need = c.needs()
        if not need:
            break
        log(f"round {rnd}: {len(need)} piles to walk, {len(c.copies)} copies opened so far")
        for q in need:
            asked = c.wanted(q)
            if not asked:
                continue
            log(f"{q}: {len(asked)} bosses could use one")
            walk_pile(c, q, asked)
            json.dump(c.state(who), open(path, "w"), indent=0)
    if c.sorted:  # other scripts walk the list as it's sorted: back to Recent, newest first, the game's own
        import base
        search.sort_recent(base.look()[3])
    return who


def report(c, who, out_dir):
    t = c.teams(who)
    json.dump(t, open(os.path.join(out_dir, "teams.json"), "w"), indent=1)
    keep = [x for x in t["copies"] if x["on"]]
    lines = [f"# /raidteam: {who}'s 6 per raid boss, at today's levels", "",
             f"Counted {t['counted']}. {len(t['copies'])} copies opened, {len(keep)} on some team.", "",
             "## On a team", ""]
    for x in sorted(keep, key=lambda x: -len(x["on"])):
        lines.append(f"- {x['name']} CP{x['cp']} ({'/'.join(x['species'])}, level {'/'.join(map(str, x['levels']))}): "
                     f"{len(x['on'])} teams, e.g. {', '.join(x['on'][:4])}")
    lines += ["", "## Every boss", ""]
    for k, team in t["bosses"].items():
        lines.append(f"- {k}: " + ", ".join(f"{e['attacker']} CP{t['copies'][e['copy']]['cp']} ({e['rating']:.1f})"
                                            for e in team) + (f"  [only {len(team)}]" if len(team) < TEAM else ""))
    p = os.path.join(out_dir, "report.md")
    open(p, "w").write("\n".join(lines) + "\n")
    return p, lines


def script(a):
    import base, ui
    ms = models()
    c = Count(ms, Rater(), a.limit)
    try:
        if a.cmd == "count":
            if not ui.ANDROID:
                sys.exit("Android only for now: POGO_PHONE=android")
            base.new_run_dir(RUNS, suffix="raidteam")
            who = cmd_count(c, a.copies, base.RUN_DIR)
            out = base.RUN_DIR
        else:
            path = a.copies or newest(HERE, "runs/*-raidteam/copies.json")
            if not path:
                sys.exit("no count yet: raidteam.py count")
            j = json.load(open(path))
            if j.get("limit") != a.limit:
                sys.exit(f"{path} counted with --limit {j.get('limit')}: report it with the same")
            c.load(j)
            who, out = j["trainer"], os.path.dirname(path)
        p, lines = report(c, who, out)
        print("\n".join(lines[:8]))
        print(f"report: {p}")
    finally:
        c.rater.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("count", "report"))
    ap.add_argument("copies", nargs="?", help="count: carry on from this copies.json. report: which (default newest)")
    ap.add_argument("--limit", type=int, help="only the first N bosses of each pull (a test)")
    a = ap.parse_args()
    if a.cmd == "count":
        import session
        session.main(script, a)
    else:
        script(a)


if __name__ == "__main__":
    main()
