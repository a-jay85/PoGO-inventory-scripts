#!/usr/bin/env python3
"""/ivc's rules for an xxs one in #IVC that isn't a top IV copy (the user, 2026-11-27). A top IV copy (any /ivc keep:
a spot, a gym spot, 98%+, a raid team) is kept first, by sort.py: its /ivc name with xxs on the end, never evolved
(it may need a move it learns by evolving). Both accounts. For the rest, plan() says how far to evolve and the final
tag:

  traded (either account): evolve to the stop. A fork or a special need -> Evo (IVC off). The end -> Transfer.
  untraded, HashTagAJay: it holds (or ties) a small-side record, or some stage of its line would set a sure one or
    fill an empty xxs Pokédex entry -> evolve to the stop. A fork or a special need -> Evo. The end -> GIV, named xxs.
    Else -> GIV, named xxs (for now: the user may change it if CyrillJan has the platinum xxs medal).
  untraded, CyrillJan: some stage of its line (itself too) would set a sure record or fill an empty xxs entry in
    HashTagAJay's Pokédex -> GIV, named xxs. Else some later stage would set a sure record in CyrillJan's own ->
    evolve to the stop. A fork or a special need -> Evo. The end -> GIV, named xxs. Else -> Transfer.

The stop: the first stage with two or more evolutions (a fork: the user picks), or whose evolution needs more than
candy (an item, a quest, a buddy walk, a gender, a trade: gamedata.evolve_cost), or the end of the line. "Its line" is
every species it can still evolve into, past a fork too (the whole line counts, the user 2026-11-27), each one's size
worked out by evosize.py. A record counts only when it's sure.

Unsure (tag None: it's left as it is, IVC on, for the not-sure list): a "nothing found" answer (CyrillJan's Transfer,
HashTagAJay's plain GIV) that rests on data not read yet (HashTagAJay's xxs page never read, a species of its line with
no dex_records row), and a GIV for one that can't be traded (a shadow,
a mythical, Gimmighoul, Gholdengo: can_trade() says).

  python3 xxs.py plan <account> <species> <kg> <m> [traded]   -> the plan for one
  python3 xxs.py test                                          -> run the examples
"""
import os, sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import pvp, evosize, rules

TAKER, GIVER = rules.TAKER, rules.GIVER
NAME = "xxs"


def can_trade(sid, shadow):
    """can it go to the other account at all"""
    tags = pvp.SPECIES[sid.removesuffix("_SHADOW")].get("tags") or []
    return not shadow and not pvp.is_shadow(sid) and dex(sid) not in rules.NEVER_TRADED and "mythical" not in tags


@dataclass
class Plan:
    path: list  # the species to evolve into, in order (empty: no evolving)
    tag: str  # its final tag: rules.EVO, 'Transfer' or 'GIV', or None: unsure, left as it is
    name: str = None  # the nickname to give it, or None to leave it
    candy: int = 0  # what the evolving costs
    why: list = field(default_factory=list)


def chain(sid, gender=None):
    """-> (the stages it evolves through to its stop, why it stops: 'end', 'fork' or what the next one needs). gender
    ('male', 'female' or None: not read): an evolution only the other gender gets is the end (a male Combee)"""
    path, cur, seen = [], sid, {sid}
    while True:
        kids = pvp.evolutions(cur)
        if not kids:
            return path, "end"
        if len(kids) > 1:
            return path, "fork"
        cost = pvp.evolve_cost(cur, kids[0])
        if cost is None:
            return path, "no cost in the game data"
        if gender and any(n.startswith("gender ") and n.split()[1].lower() != gender for n in cost["needs"]):
            return path, "end"
        if cost["needs"]:
            return path, ", ".join(cost["needs"])
        if kids[0] in seen:
            return path, "end"
        seen.add(kids[0])
        path.append(kids[0])
        cur = kids[0]


def path_candy(sid, path):
    total, cur = 0, sid
    for s in path:
        total += pvp.evolve_cost(cur, s)["candy"]
        cur = s
    return total


def line(sid):
    """every species it can still become, past forks too (not itself)"""
    return [s for s in pvp.family(sid) if s != sid]


def dex(sid):
    return pvp.SPECIES[sid]["dex"]


def gains(sid, kg, m, stages, records, missing):
    """what each stage would give one account: a sure small-side record (records: {dex: dex_records row}) or an empty
    xxs entry (missing: its xxs page's missing dex numbers, None: not read). -> ['Ivysaur: shortest', ...]"""
    out = []
    for s in stages:
        name = pvp.SPECIES[s]["speciesName"]
        if missing is not None and dex(s) in missing:
            out.append(f"{name}: empty xxs entry")
        rec = records.get(dex(s))
        if rec is None:
            continue
        size = (m - evosize.ROUND, m + evosize.ROUND, kg - evosize.ROUND, kg + evosize.ROUND) if s == sid \
            else evosize.after(sid, s, kg, m)
        if size:
            out += [f"{name}: {w}" for w in evosize.sure_small(size, rec)]
    return out


def evolve(sid, why, end_tag, end_name, gender=None):
    """evolve to the stop: a fork or a special need -> Evo, the end -> end_tag"""
    path, stop = chain(sid, gender)
    if stop == "end":
        return Plan(path, end_tag, end_name, path_candy(sid, path), why + ["end of its line"])
    return Plan(path, rules.EVO, None, path_candy(sid, path), why + [f"stops before a {stop}" if stop == "fork"
                                                                       else f"next needs {stop}"])


def unread(sid, records, missing, stages):
    """what's not read yet that a Transfer would rest on -> a reason, or None"""
    if missing[TAKER] is None:
        return "HashTagAJay's xxs page not read (pogo.py dex xxs)"
    no_row = [pvp.SPECIES[s]["speciesName"] for s, acct in stages if dex(s) not in records[acct]]
    return f"no record box read for {', '.join(no_row[:3])}" if no_row else None


def plan(account, sid, kg, m, traded, records, missing, shadow=False, gender=None):
    """records, missing: {account: dex_records rows by dex number}, {account: the xxs page's missing numbers or None}.
    gender: 'male', 'female' or None (not read)"""
    p = judge(account, sid, kg, m, traded, records, missing, gender)
    if p.tag == "GIV" and not can_trade(sid, shadow):
        return Plan(p.path, None, None, p.candy, p.why + ["but it can't be traded: unsure, by hand"])
    return p


def judge(account, sid, kg, m, traded, records, missing, gender):
    if traded:
        return evolve(sid, ["traded"], "Transfer", None, gender)
    if account == TAKER:
        here = evosize.holds_small(kg, m, records[TAKER].get(dex(sid)) or {})
        got = [f"holds {w}" for w in here] + gains(sid, kg, m, line(sid), records[TAKER], missing[TAKER])
        if got:
            return evolve(sid, got, "GIV", NAME, gender)
        if why := unread(sid, records, missing, [(s, TAKER) for s in line(sid)]):
            return Plan([], None, None, 0, [f"unsure: {why}"])
        return Plan([], "GIV", NAME, 0, ["no record or xxs entry on HashTagAJay: GIV for CyrillJan"])
    there = gains(sid, kg, m, [sid] + line(sid), records[TAKER], missing[TAKER])
    if there:
        return Plan([], "GIV", NAME, 0, [f"for HashTagAJay: {', '.join(there[:3])}"])
    mine = gains(sid, kg, m, line(sid), records[GIVER], None)
    if mine:
        return evolve(sid, mine, "GIV", NAME, gender)
    if why := unread(sid, records, missing, [(s, TAKER) for s in [sid] + line(sid)] + [(s, GIVER) for s in line(sid)]):
        return Plan([], None, None, 0, [f"unsure: {why}"])
    return Plan([], "Transfer", None, 0, ["no record on either account"])


def load():
    """(records, missing) for both accounts, from the Pokémon database and the newest xxs page read"""
    import pokedb
    sys.path.insert(0, os.path.join(HERE, "..", "dex"))
    import dex as dexpage
    records = {a: pokedb.records(a) for a in (TAKER, GIVER)}
    missing = {}
    for a in (TAKER, GIVER):
        got, _ = dexpage.latest("xxs", a)
        missing[a] = set(got) if got is not None else None
    return records, missing


def test():
    bad = 0

    def check(what, got, want):
        nonlocal bad
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {what}: {got}" + ("" if ok else f" (want {want})"))

    box = lambda kg, m: {"kg_min": kg, "kg_max": 99, "m_min": m, "m_max": 9}
    none = {TAKER: {}, GIVER: {}}
    unread = {TAKER: None, GIVER: None}
    p = lambda *a: (lambda r: (r.path, r.tag, r.name))(plan(*a))
    check("chain bulbasaur", chain("BULBASAUR_NORMAL"), (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "end"))
    check("chain eevee", chain("EEVEE_NORMAL"), ([], "fork"))
    check("chain feebas", chain("FEEBAS_NORMAL"), ([], "quest, buddy km"))
    check("chain poliwag", chain("POLIWAG_NORMAL"), (["POLIWHIRL_NORMAL"], "fork"))
    check("chain combee, male", chain("COMBEE_NORMAL", "male"), ([], "end"))
    check("chain combee, female", chain("COMBEE_NORMAL", "female"), ([], "gender FEMALE"))
    check("traded male combee", p(TAKER, "COMBEE_NORMAL", 3.0, 0.3, True, none, unread, False, "male"), ([], "Transfer", None))
    check("candy", path_candy("BULBASAUR_NORMAL", ["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"]), 125)
    check("traded, to the end", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, True, none, unread),
          (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "Transfer", None))
    check("traded, fork", p(TAKER, "POLIWAG_NORMAL", 5.0, 0.3, True, none, unread), (["POLIWHIRL_NORMAL"], rules.EVO, None))
    check("HTAJ, nothing", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, {TAKER: {2: box(1, .1), 3: box(1, .1)}, GIVER: {}},
                             {TAKER: set(), GIVER: None}), ([], "GIV", "xxs"))
    check("HTAJ, nothing but page unread", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, none, unread), ([], None, None))
    recs = {TAKER: {1: box(2.0, 0.2), 2: box(8.0, 0.9), 3: box(0.5, 0.1)}, GIVER: {}}
    check("HTAJ, Ivysaur record", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, recs, unread),
          (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "GIV", "xxs"))
    check("HTAJ, empty xxs entry", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, none, {TAKER: {3}, GIVER: None}),
          (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "GIV", "xxs"))
    check("HTAJ, holds its own", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, {TAKER: {1: box(3.0, 0.5)}, GIVER: {}},
                                    unread), (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "GIV", "xxs"))
    check("CJ, HTAJ record -> GIV", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False, recs, unread), ([], "GIV", "xxs"))
    check("CJ, HTAJ xxs entry -> GIV", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False, none, {TAKER: {1}, GIVER: None}),
          ([], "GIV", "xxs"))
    mine = {TAKER: {1: box(1.0, 0.1), 2: box(1.0, 0.1), 3: box(1.0, 0.1)}, GIVER: {3: box(90, 1.9)}}
    check("CJ, own Venusaur record", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False, mine, unread),
          (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "GIV", "xxs"))
    check("CJ, own record past a fork", p(GIVER, "POLIWAG_NORMAL", 5.0, 0.3, False,
                                         {TAKER: {}, GIVER: {186: box(99, 9)}}, unread), (["POLIWHIRL_NORMAL"], rules.EVO, None))
    read = {TAKER: set(), GIVER: None}
    check("CJ, nothing anywhere", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False,
                                    {TAKER: mine[TAKER], GIVER: {2: box(1.0, 0.1), 3: box(1.0, 0.1)}}, read),
          ([], "Transfer", None))
    check("CJ, HTAJ xxs page unread: unsure", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False,
                                                {TAKER: mine[TAKER], GIVER: {2: box(1.0, 0.1), 3: box(1.0, 0.1)}},
                                                unread), ([], None, None))
    check("CJ, a stage with no box read: unsure", p(GIVER, "BULBASAUR_NORMAL", 3.0, 0.3, False,
                                                    {TAKER: mine[TAKER], GIVER: {2: box(1.0, 0.1)}}, read),
          ([], None, None))
    check("HTAJ shadow, GIV: unsure", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, False, {TAKER: {2: box(1, .1), 3: box(1, .1)},
                                         GIVER: {}}, {TAKER: set(), GIVER: None}, True), ([], None, None))
    check("traded shadow: Transfer still", p(TAKER, "BULBASAUR_NORMAL", 3.0, 0.3, True, none, unread, True),
          (["IVYSAUR_NORMAL", "VENUSAUR_NORMAL"], "Transfer", None))
    check("can't trade Gimmighoul", can_trade("GIMMIGHOUL_NORMAL", False), False)
    check("can trade Bulbasaur", can_trade("BULBASAUR_NORMAL", False), True)
    print("all xxs cases right" if not bad else f"{bad} wrong")
    return bad


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["test"]:
        sys.exit(test())
    if len(a) in (5, 6) and a[0] == "plan":
        r = plan(a[1], a[2], float(a[3]), float(a[4]), a[5:] == ["traded"], *load())
        print(f"evolve into: {' -> '.join(r.path) or 'nothing'} ({r.candy} candy), then {r.tag}"
              f"{f', named {r.name}' if r.name else ''}: {'; '.join(r.why)}")
    else:
        sys.exit(__doc__)
