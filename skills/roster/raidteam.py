#!/usr/bin/env python3
"""/raidteam: the signed-in account's best 6 raid attackers against every released raid boss like a 4-star raid's
or higher, at the level and IVs its copies have today (the user, 2026-11-17). Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 raidteam.py count [copies.json] [--limit N]
                                       count whoever is signed in; with a copies.json, carry on from it.
                                       --limit N: only the first N bosses (a test)
  python3 raidteam.py report [copies.json]   the teams again (Mac only)
  POGO_PHONE=android caffeinate -dimsu python3 raidteam.py keep [teams.json] [--limit N]
                                       every copy on a team: a favorite, its trade and Transfer tags off. Default the
                                       signed-in account's newest whole count. --limit N: at most N copies. A whole
                                       count (no --limit) runs this at its end
  pogo.py raidteam count                     the same, through the front door

What it's for: a Pokémon on some team is a favorite, whatever its IVs (a Mighty one, a traded one powered up long
ago). One that falls off every team, because something better got powered up, is judged again and can be traded or
transferred. A better copy that isn't powered up yet doesn't push anything out: only what each copy is today counts.

Bosses: roster.real_boss() and released, in both DialgaDex pulls (Party Power off, a party of 2: a team in either
counts). Every attacker on a boss's list counts, legendary, shadow and mega too: these are the account's own teams. A
mega is a copy of its species, at that copy's level and IVs, one mega per team. Ratings are DialgaDex's own (rate.mjs):
best moves with Elite TMs, so a copy's real moves don't count. Only the attackers on DialgaDex's lists (80 deep) count.

How it counts. A pile is one storage search: the species' dex number, its form terms, and shadow or !shadow. Its list
is sorted by CP, highest first, and walked from the top. A tile's CP caps the copy's level and IVs together: per IV
mix, no level higher than the one that mix reaches at that CP (ceiling()). The best rating of those caps the copy's.
Once that cap can't beat a boss's 6th, no copy further down can either, and the walk stops. Like roster.py it goes
round by round: each boss asks for the first pile on its list whose cap still beats its 6th, and those piles are
walked, until no boss asks.
Fewer opens: once no 3★ or lower copy (or 2★ or lower) under this CP could beat any boss's 6th, the pile's search
takes a star term (4*, or 3*,4*): the rest of its list is only copies that could. Fewer searches: from round 2, piles
not searched yet go 8 at a time in one search (`123,456,...&!shadow`, sorted by CP). Its top tile's CP is the most
any of them has, and a pile whose copies at that CP can't beat any 6th needs no search of its own.
An opened copy: CP, HP and the power-up cost on the page's top (no drag) give the level and the IVs that fit
(powerup.cost_levels). The database (pokedb) may know its IVs. Still more than one fit, and the best of them could beat
some boss's 6th: the appraisal gives them.

Output in runs/<time>-raidteam/: copies.json (every copy opened, saved after each pile: a stopped count carries on
from it), teams.json (../shared/raidteams.py reads it, for the door and /ivc) and report.md. teams.json: per boss its 6; every copy opened, with the
bosses it's on; per pile, the lowest CP a copy could make some team at (bar), and where its walk took a star term
(stars). A copy under its pile's bar can't be on
any team. One over it that isn't among the opened ones came or grew after the count.

Keep: the bulk taggers (cleantrades, tradeable tag, specieswise) tag whole searches without opening a page, so they can't
ask raidteams.py. Every one of their searches leaves out favorites: a team member made a favorite is safe from all of
them. Each one is found by its dex number, shadow or not and its exact CP, and told apart by HP, weight and height.
Favorite on, rules.RAID_OFF off. One with the user's own tag (verdict.OWN_TAGS: Old, Evo, GuaranteedLucky, Remote
Trade, RT) is passed over, traded or not: the door judges those. One powered up since the count isn't found: passed
over too (the door and /ivc still keep it). Done ones go in kept.json beside teams.json, so a rerun skips them.
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
FULL = 45  # the highest IV sum
STEPS = ((0, 3), (4, 7), (8, 11), (12, 15))  # ceiling(): defense and HP IVs, 4 at a time
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


def top_at(b, ivs, cp):
    """the highest level these IVs give a CP of cp or less at, or None"""
    lo, hi = 0, len(pvp.LEVELS) - 1
    if pvp.cp(b, ivs, pvp.LEVELS[0]) > cp:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if pvp.cp(b, ivs, pvp.LEVELS[mid]) <= cp else (lo, mid - 1)
    return pvp.LEVELS[lo]


_CEIL = {}


def ceiling(sid, cp, smax=FULL):
    """[(level, ivs)]: the best of their ratings is at least what any copy of sid with a CP of cp or less and an IV
    sum of smax or less rates. Per attack IV and 4-wide steps of defense and HP: the highest level the step's lowest
    IVs reach under cp, with its highest IVs (that fit smax). A copy's level can't be higher, nor its IVs, and a
    rating only grows with both. Tighter than a 15/15/15 at the 0/0/0's level: a strong copy at that CP sits lower.
    No CP: level 50"""
    k = (sid, cp, smax)
    if k not in _CEIL:
        b, out = stats(sid), set()
        for a in range(16):
            for d0, d1 in STEPS:
                for h0, h1 in STEPS:
                    if a + d0 + h0 > smax:
                        continue
                    lv = pvp.LEVELS[-1] if not cp else top_at(b, (a, d0, h0), cp)
                    if lv is not None:
                        out.add((lv, (a, min(d1, smax - a - h0), min(h1, smax - a - d0))))
        _CEIL[k] = [x for x in sorted(out) if not any(y != x and below(x, y) for y in out)]
    return _CEIL[k]


def below(x, y):
    """(level, ivs) x rates no higher than y: no higher a level, no higher an IV"""
    return x[0] <= y[0] and all(i <= j for i, j in zip(x[1], y[1]))


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

    def loose_asks(self, m, b, q, cp):
        return [(m.A[i], top_level(m.sid[i], cp), HUNDO) for i in self.entries(m, b, q)]

    def cap_asks(self, m, b, q, cp, smax=FULL):
        return [(m.A[i], lv, ivs) for i in self.entries(m, b, q) for lv, ivs in ceiling(m.sid[i], cp, smax)]

    def best(self, m, b, asks):
        return max((r or 0 for r in self.rater.rate(m.data["party"], b, asks)), default=0)

    def over(self, m, b, q, cp, r, smax=FULL):
        """could a copy of pile q with this CP or less (IV sum smax or less) rate over r against this boss? A
        15/15/15 at the 0/0/0's level first (one ask), then ceiling()'s (a few hundred)"""
        return self.best(m, b, self.loose_asks(m, b, q, cp)) > r and self.best(m, b, self.cap_asks(m, b, q, cp, smax)) > r

    def warm_over(self, wants):
        """[(m, b, q, cp, r, smax)]: everything over() will ask for these, in two lines to rate.mjs"""
        self.rater.warm([(m.data["party"], b, self.loose_asks(m, b, q, cp)) for m, b, q, cp, r, smax in wants])
        self.rater.warm([(m.data["party"], b, self.cap_asks(m, b, q, cp, smax)) for m, b, q, cp, r, smax in wants
                         if self.best(m, b, self.loose_asks(m, b, q, cp)) > r])

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

    def beats(self, q, cp, pairs=None, smax=FULL):
        """the pairs (of these, else all listing q) whose 6th a copy of pile q with this CP (and an IV sum of smax or
        less) could still beat"""
        pairs = self.listing(q) if pairs is None else pairs
        self.warm_sixths(pairs)
        self.warm_over([(m, b, q, cp, self.sixth(m, b), smax) for m, b in pairs])
        return [(m, b) for m, b in pairs if self.over(m, b, q, cp, self.sixth(m, b), smax)]

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
        """pile -> the lowest CP a copy of it could make some team at today (None: none could). Two answers, the higher
        counts. A 15/15/15 at the 0/0/0's level: its cap only changes where some form's 0/0/0 CP is, and grows with
        the CP: the first of those whose cap beats some 6th (every pile a step at a time together, one line to rate.mjs
        a step). And a walk that stopped: at the count's end no boss asks for its next copy (needs()), so nothing at
        that CP or under can make a team. ceiling()'s own halving search would cost minutes"""
        self.warm_sixths()
        cps = {q: sorted({pvp.cp(stats(x), (0, 0, 0), lv) for x in p["sids"] if x in pvp.SPECIES for lv in pvp.LEVELS})
               for q, p in self.piles.items()}
        lst = {q: self.listing(q) for q in self.piles}
        loose = lambda qcs: self.rater.warm([(m.data["party"], b, self.loose_asks(m, b, q, cp)) for q, cp in qcs for m, b in lst[q]])
        hit = lambda q, cp: any(self.best(m, b, self.loose_asks(m, b, q, cp)) > self.sixth(m, b) for m, b in lst[q])
        loose([(q, cps[q][-1]) for q in self.piles if cps[q]])
        span = {q: [0, len(cps[q]) - 1] for q in self.piles if cps[q] and hit(q, cps[q][-1])}
        while any(lo < hi for lo, hi in span.values()):
            loose([(q, cps[q][(lo + hi) // 2]) for q, (lo, hi) in span.items() if lo < hi])
            for q, sp in span.items():
                lo, hi = sp
                if lo < hi:
                    mid = (lo + hi) // 2
                    sp[:] = [lo, mid] if hit(q, cps[q][mid]) else [mid + 1, hi]
        out = {q: cps[q][span[q][0]] if q in span else None for q in self.piles}
        for q, w in self.walk.items():
            if out[q] is not None and not w["end"] and w["next_cp"]:
                out[q] = max(out[q], w["next_cp"] + 1)
        return out

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
        out["stars"] = {}  # [[smax, cp]]: a pile walked with a star term from that CP down: no copy at that CP or
        # under with an IV sum of smax or less can make a team (it was left out of the search)
        for q, p in self.piles.items():
            for x in p["sids"]:
                key = f"{x}{'|shadow' if p['shadow'] else ''}"
                out["bars"][key] = bars[q]
                if self.walk[q].get("stars"):
                    out["stars"][key] = self.walk[q]["stars"]
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
    """the tiles' CPs go down, top to bottom (a CP not read is passed over, and so is one misread: shiny sparkles by
    a CP2850 read as 987, Pixel 2026-11-18)"""
    cps = [cp for _, cp in ts if cp]
    down = lambda xs: all(x >= y for x, y in zip(xs, xs[1:]))
    return down(cps) or len(cps) > 3 and any(down(cps[:i] + cps[i + 1:]) for i in range(len(cps)))


def sorted_tiles(c, typed):
    """type the search, sort its list by CP once (a search keeps the list's sort) -> its first tiles [(name, cp)]"""
    import base, search, taps, ui
    from tagsheet import search_exact
    search_exact(typed)
    ts = taps.settled_tiles()
    if ts and (not c.sorted or not by_cp(ts)):
        _, _, _, bounds = base.look()
        _, texts, _ = search.sort_down("COMBAT POWER", bounds)
        c.sorted = True
        ts = [(ui.tile_name(n), cp) for n, cp, _, _ in ui.tiles(texts)]
        if not by_cp(ts):
            raise Stop(f"{typed}: sorted by Combat Power, but the CPs don't go down")
    return ts


IV_NAME = re.compile(r"(\d{2,3})(?!\d)")  # an /ivc name starts with its IV% ('96 D GGBI', '100 RT*')


def iv_pct(name):
    """an /ivc name's IV% (0-100), else None"""
    m = IV_NAME.match(name or "")
    return int(m.group(1)) if m and int(m.group(1)) <= 100 else None


def squash(name):
    """a name to match on: OCR drops or adds spaces ('96 D C*X' / '96 D C* X')"""
    return re.sub(r"\s+", "", name or "").lower()


def top(ts, key, n=TEAM):
    """the tiles [(name, cp)] whose key is among the n highest, and every one tied with the nth"""
    vals = sorted((key(t) for t in ts if key(t) is not None), reverse=True)
    if not vals:
        return []
    cut = vals[min(n, len(vals)) - 1]
    return [t for t in ts if key(t) is not None and key(t) >= cut]


def piles_in_order(c):
    """the piles, best first: by their best place on any boss's list (so the 6ths fill early, and later piles
    need fewer opens)"""
    rank = {}
    for m, b in c.pairs:
        for k, q in enumerate(c.ent[(id(m), id(b))]):  # (in list order)
            rank[q] = min(rank.get(q, k), k)
    return sorted(rank, key=rank.get)


def known_copy(c, q, name, cp):
    """pokedb's record of this tile: its nickname, CP and the pile's species, shadow or not, with its IVs -> a copy
    dict like read_copy's, or None (not known, more than one record, or it doesn't add up at this CP)"""
    import pokedb
    p = c.piles[q]
    base_of = lambda s: (s or "").removesuffix("_shadow")
    sids = {base_of(s) for s in p["sids"]}

    def shadow(r):
        try:
            return bool(json.loads(r.get("flags") or "{}").get("shadow"))
        except ValueError:
            return None
    rows = [r for r in pokedb.find(cp=cp) if r.get("atk") is not None and base_of(r["species"]) in sids
            and squash(r["nickname"]) == squash(name) and shadow(r) == p["shadow"]]
    if len(rows) != 1:
        return None
    r = rows[0]
    got = [f for f in fits(p["sids"], cp, r["hp"]) if f[2] == (r["atk"], r["def"], r["sta"])]
    if not got:
        return None
    return {"q": q, "name": name, "tile_cp": cp, "cp": cp, "hp": r["hp"], "kg": r["kg"], "m": r["m"], "fits": got,
            "ivs_sure": True, "from": "pokedb"}


def open_tiles(c, q, todo, past):
    """open these tiles [(name, cp)] of pile q, walking its list from the top as it's sorted. past(name, cp): the
    walk is past where they'd be (stop there, not at the list's end)"""
    import base, search
    left = Counter((squash(n), cp) for n, cp in todo)

    def want(name, cp):
        if not +left or past(name, cp):
            raise Enough()
        return left[(squash(name), cp)] > 0

    def visit(i, name, cp):
        left[(squash(name), cp)] -= 1
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
        search.walk_list(visit, want=want)
    except Enough:
        pass
    if +left:
        log(f"  {q}: not found on its list: {', '.join(f'{n} CP{cp}' for n, cp in +left)}")


def take(c, q, tiles, past, to_top=None):
    """these tiles of pile q count: the ones counted before are passed, pokedb's known ones are added without an
    open, and the rest are opened if a copy at their CP could still beat some boss's 6th"""
    have = Counter((squash(x["name"]), x["tile_cp"]) for x in c.copies if x["q"] == q)
    todo, known = [], 0
    for name, cp in tiles:
        k = (squash(name), cp)
        if have[k] > 0:
            have[k] -= 1
            continue
        one = known_copy(c, q, name, cp) if cp else None
        if one:
            c.copies.append(one)
            known += 1
            continue
        todo.append((name, cp))
    todo = [t for t in todo if c.beats(q, t[1])]
    log(f"  {len(tiles)} tiles: {known} known in pokedb, {len(todo)} to open")
    if todo:
        if to_top:
            to_top()
        open_tiles(c, q, todo, past)


def cp_pass(c, q):
    """pile q's top 6 by CP (and ties): the list sorted by CP, highest first. Its first screen holds them"""
    w = c.walk[q]
    if not c.beats(q, None):
        log(f"{q}: no copy of it could beat any boss's 6th")
        w["end"] = True
        return
    ts = sorted_tiles(c, q)
    if not ts:
        log(f"{q}: none")
        w["end"] = True
        return
    w["top_cp"] = max((cp for _, cp in ts[:3] if cp), default=None)  # the top row's best: one misread low can't hide it
    hi = top(ts, lambda t: t[1])
    log(f"{q}: top {len(hi)} by CP, CP{hi[0][1]} to CP{hi[-1][1]}")
    low = min(cp for _, cp in hi)
    take(c, q, hi, past=lambda n, cp: cp is not None and cp < low)
    w["cp_done"] = True


def name_pass(c, q, named):
    """pile q's top 6 by IV% (and ties), from its /ivc names: the list sorted by Name, where they come first.
    named: the list is sorted by Name already. -> named"""
    import base, search
    from tagsheet import search_exact
    w = c.walk[q]
    if not c.beats(q, w.get("top_cp")):
        log(f"{q}: no copy at its top CP{w.get('top_cp')} could beat any boss's 6th: no IV names needed")
        w["end"] = True
        return named
    if named:
        ts, _ = search.run_search(q, iv_only=True)
    else:
        search_exact(q)
        path, texts, bounds = search.sort_by_name(base.look()[3])
        ts, _ = search.read_results(q, path, texts, bounds, iv_only=True)
        named = True
    hi = top(ts, lambda t: iv_pct(t[0]))
    if not hi:
        log(f"{q}: no IV names")
        w["end"] = True
        return named
    log(f"{q}: top {len(hi)} by IV name, {max(iv_pct(n) for n, _ in hi)}% down to {min(iv_pct(n) for n, _ in hi)}%")
    plain = [0]

    def past(n, cp):  # past the IV names: 3 plain names in a row (one misread IV name isn't the end)
        plain[0] = plain[0] + 1 if iv_pct(n) is None else 0
        return plain[0] >= 3
    take(c, q, hi, past, to_top=lambda: search_exact(q))  # back to the list's top (a search keeps its sort)
    w["end"] = True
    return named


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
    piles = piles_in_order(c)
    log(f"{len(piles)} piles: each one's top {TEAM} by CP, then its top {TEAM} by IV name")
    for q in piles:  # sorted by CP once, for all of them
        if not c.walk[q]["end"] and not c.walk[q].get("cp_done"):
            cp_pass(c, q)
            json.dump(c.state(who), open(path, "w"), indent=0)
    named = False
    for q in piles:  # then by Name once
        if not c.walk[q]["end"]:
            named = name_pass(c, q, named)
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


def member_key(x):
    return f"{'/'.join(x['species'])}|{x['shadow']}|{x['cp']}|{x['hp']}|{x['kg']}|{x['m']}"


def cmd_keep(t, path, limit=None):
    """every copy on a team in teams dict t (from path): a favorite, rules.RAID_OFF off. -> how many made favorites"""
    import base, search, verdict
    from rules import RAID_OFF
    from savedsearch import results
    from taps import details
    from tagsheet import search_exact, tag_chips, favorite
    done_path = os.path.join(os.path.dirname(path), "kept.json")
    done = set(json.load(open(done_path))) if os.path.exists(done_path) else set()
    todo = [x for x in t["copies"] if x["on"] and x.get("cp") and member_key(x) not in done]
    log(f"keep: {len(todo)} copies on a team to make favorites ({len(done)} done before)")
    own = {ui_key(x) for x in verdict.OWN_TAGS}
    made = 0
    for x in todo:
        if limit is not None and made >= limit:
            log(f"--limit {limit} reached")
            break
        q = f"{pvp.SPECIES[x['species'][0]]['dex']}&{'shadow' if x['shadow'] else '!shadow'}&cp{x['cp']}"
        search.to_search_list()
        search_exact(q)
        if not results():
            log(f"  {x['name']} CP{x['cp']} ({q}): none: powered up since the count, or gone")
            continue
        want = (x["cp"], x["hp"], x["kg"], x["m"])
        hit = False
        for info, texts, bounds, seen in details(key=lambda i: (i["cp"], i["hp"], i["name"])):
            base.OPENED["who"] = base.who(info)  # (the swipe moved here on purpose: the star and tags check this one)
            if not base.same_pokemon(base.who(info), want):
                continue
            hit = True
            mine = [c for c in tag_chips(texts) if ui_key(c) in own]
            if mine:
                log(f"  {x['name']} CP{x['cp']}: has your tag {', '.join(mine)}: passed over (the door judges it)")
            else:
                favorite(info, texts, RAID_OFF)
                made += 1
            break
        base.go("close", "list")
        if not hit:
            log(f"  {x['name']} CP{x['cp']} ({q}): no copy with its HP, weight and height: passed over")
            continue
        done.add(member_key(x))
        json.dump(sorted(done), open(done_path, "w"), indent=0)
    log(f"keep: {made} made favorites")
    return made


def ui_key(s):
    return re.sub(r"[^A-Z]", "", s.upper())


def keep_script(a):
    import base, home, raidteams
    base.new_run_dir(RUNS, suffix="raidkeep")
    home.start()
    who = home.trainer()
    path = a.copies
    if path:
        t = json.load(open(path))
        if t["trainer"] != who:
            raise Stop(f"{path} is {t['trainer']}'s count, but {who} is signed in")
    else:
        t = raidteams.newest(who)[0]
        if t is None:
            raise Stop(f"no whole count for {who} yet: raidteam.py count (no --limit) first")
        path = raidteams.path_of(who)
    cmd_keep(t, path, a.limit)


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
        if a.cmd == "count" and not a.limit:  # a whole count: its team members become favorites, for the bulk taggers
            cmd_keep(c.teams(who), os.path.join(out, "teams.json"))
    finally:
        c.rater.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("count", "report", "keep"))
    ap.add_argument("copies", nargs="?", help="count: carry on from this copies.json. report: which (default newest). "
                                              "keep: this teams.json (default the newest whole count)")
    ap.add_argument("--limit", type=int, help="count, report: only the first N bosses of each pull (a test). "
                                              "keep: at most N copies")
    a = ap.parse_args()
    if a.cmd == "keep":
        import ui
        if not ui.ANDROID:
            sys.exit("Android only for now: POGO_PHONE=android")
        import session
        session.main(keep_script, a)
    elif a.cmd == "count":
        import session
        session.main(script, a)
    else:
        script(a)


if __name__ == "__main__":
    main()
