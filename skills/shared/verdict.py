#!/usr/bin/env python3
"""The final tag for a Pokémon that just fell short of a keeper, judged right where it was judged (no Nope).

  python3 verdict.py tables [CyrillJan|HashTagAJay]   the species lists a judge for that account would read now

A script that decides "not a keeper" (pvpc, ivc, ivcsort, fallen) reads what it can on the detail page into Facts and
calls final_tag(facts, tables). The answer is one of:
  tag     put these tags on (and the source tag IVC / PvpC off); `name` too when it's set
  keep    it belongs after all: star on (98%+, or a gym defender in its species' top 20)
  unsure  leave it exactly as it is (tags, name). It goes on the not-sure list with why, for a rule offline
Transfer only comes out when every rule above it was checked and none fits: a fact that didn't read, or a species list
that's missing, gives unsure, never Transfer.

The order is tradeable.py's (its docstring has the reasons), judged for the other account, the one it would be traded
to. Signed in as CyrillJan (the pile goes to HashTagAJay):
  GuaranteedLucky > Luckydex > Old > Reroll > GIV > XXL/xxs > XLX > GIV (evolved, Dynamax, Tandemaus) > GIV (far) >
  Transfer
Signed in as HashTagAJay (the pile goes to CyrillJan):
  GuaranteedLucky > Old > GIV (medal) > 2XL > GIV > XXL/xxs > XLX > GIV (evolved, Dynamax) > GIV (far) > Transfer
Before all of them: a special trade (trades.py's legendary rules, else unsure), a kind the user sorts by hand (unsure
until they give rules), a traded one (Transfer). The user's own tags first: untraded with Old, Evo or GuaranteedLucky,
those stay and only IVC / PvpC comes off; traded, the "trade it" tags (TRADE_TAGS) come off. The species lists come
from tradeable.py's taker_species() and giver_species(), the same ones its plan uses; one saved more than STALE_DAYS
ago counts as missing.
"""
import datetime, os, re, sys, time
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "cleanup"))
import pvp
from base import ALWAYS_KEEP  # an IV sum of 98%+ never loses its star
import tradeable as tr  # the order, the numbers and the species lists: one copy, there
from tradeable import GIVER, TAKER, XL_CAP, XLX_FOR
from ivc import GYM_DEFENDERS
from sizes import NAMES as SIZE_NAMES  # a never-traded XXL/XXS one gets this name and IVC
from cleantrades import EVO, EVO_FOR, TRADE_EVOS  # traded + a free trade evolution: Evo, on EVO_FOR's account

TO = {GIVER: TAKER, TAKER: GIVER}
OLD_DAYS = int(re.search(r"\d+", tr.OLD_AGE).group())
LUCKY_YEARS = (2016, 2020)  # an untraded catch from these years is lucky once traded (tradeable.py's NOPE_OLD)
# GIV (medal), from tradeable.py's MEDALS: dex -> (size it needs, or None; fits(kg); the kg range that reads right)
MEDALS = {min(tr.dexes_of(q)): (("xxs", "xs") if "xxs,xs" in q else None, fits, tr.MEDAL_KG[name])
          for name, q, fits in tr.MEDALS}
FUSED = ("kyurem_black", "kyurem_white", "necrozma_dusk_mane", "necrozma_dawn_wings")  # trades.py: can't be traded
TRADE_BY_HAND = {"meltan", "melmetal"}  # mythical, but trades.py retags them like a legendary
OWN_TAGS = ("Old", EVO, "GuaranteedLucky")  # untraded with one of these: it stays, only IVC / PvpC comes off
TRADE_TAGS = ("GIV", "XLX", "2XL", "Reroll", "Old", "Special", "GuaranteedLucky")  # "trade it": off a traded one
STALE_DAYS = 7  # a species list older than this counts as missing


@dataclass
class Facts:
    """what the script read. None = couldn't read it (then any rule that needs it answers unsure)"""
    account: str = None  # signed in: CyrillJan or HashTagAJay
    sids: list = None  # the species it could be (ui.species_for); more than one that disagree -> unsure
    iv_sum: int = None  # from the appraisal (0-45)
    traded: bool = None
    caught: datetime.date = None
    gender: str = None  # 'male', 'female', or '' for a genderless one
    shiny: bool = False
    lucky: bool = False
    shadow: bool = False
    costume: bool = False
    background: bool = False
    gigantamax: bool = False
    dynamax: bool = False
    size: str = None  # 'xxs', 'xs', 'xl', 'xxl', or '' for none
    kg: float = None
    candy_xl: int = None  # this account's Candy XL of the family
    levels: list = None  # the levels it can be at, from the power-up cost
    far: bool = None  # caught 100 km+ away (the run's one 'distance100-' search)
    gym_top20: bool = None  # a gym defender: top 20 CP or IV of its species (its search)
    other_tags: list = field(default_factory=list)  # the user's tags besides the one this script works on


@dataclass
class Verdict:
    kind: str  # 'tag', 'keep' or 'unsure'
    tags: tuple = ()
    why: str = ""
    name: str = None  # a new nickname to type, when set
    off: tuple = ()  # the user's tags to take off too (IVC / PvpC always comes off)


def tag(*tags, why, name=None, off=()):
    return Verdict("tag", tags, why, name, off)


def unsure(why):
    return Verdict("unsure", (), why)


# ---------- the species lists ----------

_TABLES = {}


def stale(files, now=None):
    """{what: file} -> 'what (n days)' for each file saved more than STALE_DAYS ago"""
    now = now or time.time()
    return [f"{k} ({days:.0f} days)" for k, p in files.items()
            if p and os.path.exists(p) and (days := (now - os.path.getmtime(p)) / 86400) > STALE_DAYS]


def tables(to):
    """the species lists for judging a pile that goes to `to`, loaded once a run. None if a file is missing (then
    every species rule answers unsure). Each has 'to' and, if missing, 'missing'"""
    if to not in _TABLES:
        m = tr.Model()
        try:
            sp = tr.taker_species(m) if to == TAKER else tr.giver_species(m)
        except (tr.NoData, SystemExit, OSError) as e:  # (pve() exits with no DialgaDex counters; no runs folder)
            _TABLES[to] = {"to": to, "missing": str(e)}
            return _TABLES[to]
        if old := stale(sp["from"]):
            _TABLES[to] = {"to": to, "missing": f"older than {STALE_DAYS} days: {', '.join(old)}"}
            return _TABLES[to]
        why = sp["why"] if to == TAKER else {s: ("GIV", r) for s, r in sp["why"].items()}
        _TABLES[to] = {"to": to, "why": why, "lucky": sp.get("lucky", {}), "evolved": sp["evolved"],
                       "no_dmax": set(sp.get("no_dmax", ())), "xl_full": sp["xl_full"],
                       "giv_for_taker": set(tr.GIV_FOR_TAKER), "from": sp["from"]}
    return _TABLES[to]


# ---------- the rules ----------

def canon(t):
    """a tag as read ('GUARANTEEDLUCKY') -> its name ('GuaranteedLucky'), when it's one the rules know"""
    return next((x for x in OWN_TAGS + TRADE_TAGS if x.upper() == t.strip().upper()), t.strip())


def final_tag(f, t, today=None):
    """f: Facts. t: tables(TO[f.account]). -> Verdict"""
    today = today or datetime.date.today()
    if f.account not in TO:
        return unsure(f"signed in as {f.account!r}")
    to = TO[f.account]
    if f.iv_sum is None:
        return unsure("no appraisal")
    if f.iv_sum >= ALWAYS_KEEP:
        return Verdict("keep", (), f"{round(f.iv_sum / 45 * 100)}%: 98%+ never goes")
    if not f.sids:
        return unsure("species not read")
    if len(f.sids) > 1:  # (two forms of one dex too: the species lists go by form)
        return unsure(f"could be {', '.join(f.sids)}")
    sid = f.sids[0]
    dexn = pvp.SPECIES[sid]["dex"]
    kinds = set(pvp.SPECIES[sid].get("tags") or [])

    # the user's own tags: untraded, one that says where it goes stays (only IVC / PvpC comes off). Traded, the
    # "trade it" ones come off (it can't trade again) and it's judged on
    strip = ()
    if f.other_tags:
        names = [canon(x) for x in f.other_tags]
        if f.traded is None:
            return unsure(f"has your tag {', '.join(names)}, traded or not not read")
        if rest := [x for x in names if x not in (TRADE_TAGS if f.traded else OWN_TAGS)]:
            return unsure(f"has your tag {', '.join(rest)}")
        if not f.traded:
            return tag(why=f"keeps your tag {', '.join(names)}")
        strip = tuple(names)
    # by hand: the user sorts these (rules to come, kind by kind)
    for k in ("shadow", "lucky", "costume", "background"):
        if getattr(f, k):
            return unsure(f"{k}: no rule yet")
    if f.traded is None:
        return unsure("traded or not not read")
    if f.caught is None:
        return unsure("catch date not read")
    old = (today - f.caught).days >= OLD_DAYS

    # special trades: trades.py's rules for legendaries, Ultra Beasts, Meltan and Melmetal. The rest by hand
    if f.shiny or f.gigantamax:
        return unsure("shiny or Gigantamax: a special trade, by hand")
    if "legendary" in kinds or "ultrabeast" in kinds or "mythical" in kinds:
        if "mythical" in kinds and sid not in TRADE_BY_HAND:
            return unsure("mythical: can't be traded, by hand")
        if f.size is None or f.size in SIZE_NAMES:  # trades.py passes over an XXL/xxs one
            return unsure(f"special trade, size {f.size or 'not read'}: by hand")
        if f.traded:
            return tag("Spot Transfer", why="traded special trade: a spot transfer", off=strip)
        if sid in FUSED:
            return unsure("fused: can't be traded")
        return tag("Remote Trade", "RT", *(("Old",) if old else ()), why="untraded special trade: a remote trade")

    # a gym defender may still be top 20 CP or IV of its species (ivcsort's gym rule), traded or not
    if sid in GYM_DEFENDERS:
        if f.gym_top20 is None:
            return unsure("gym defender: top 20 not checked")
        if f.gym_top20:
            return Verdict("keep", (), "gym defender: top 20 CP or IV")

    if f.traded:
        if f.account == EVO_FOR and dexn in {int(d) for d in TRADE_EVOS.split(",")}:
            return tag(EVO, why="traded: evolves for free", off=strip)
        return tag("Transfer", why="traded: can't trade again", off=strip)
    if LUCKY_YEARS[0] <= f.caught.year <= LUCKY_YEARS[1]:
        return tag("GuaranteedLucky", why=f"untraded, caught {f.caught.year}: lucky once traded")

    if "missing" in t:
        return unsure(f"no species lists for {to}: {t['missing']}")
    why = t["why"].get(sid)

    if to == TAKER and why and why[0] == "Luckydex":
        g = t["lucky"].get(sid, "")
        if g and f.gender is None:
            return unsure("gender not read (Luckydex wants one gender)")
        if not g or g == f.gender:
            return tag("Luckydex", why=why[1])
    if old:
        return tag("Old", why=f"untraded, caught {(today - f.caught).days} days ago")
    if f.size is None:
        return unsure("size not read")

    if to == GIVER:
        if dexn in MEDALS and (MEDALS[dexn][0] is None or f.size in MEDALS[dexn][0]):
            _, fits, (lo, hi) = MEDALS[dexn]
            if f.kg is None or not lo <= f.kg <= hi:
                return unsure(f"medal one, weight read {f.kg}")
            if fits(f.kg):
                return tag("GIV", why=f"medal: {f.kg} kg")
        if f.size not in ("xxl", "xxs"):
            if f.candy_xl is None:
                return unsure("Candy XL not read")
            if f.candy_xl < XL_CAP:
                return tag("2XL", why=f"under {XL_CAP} Candy XL: a Friendship Friday trade")

    if why and why[0] in ("Reroll", "GIV"):
        return tag(why[0], why=why[1])
    if f.size in SIZE_NAMES:
        return tag("IVC", why=f"never traded {f.size.upper()}", name=SIZE_NAMES[f.size])

    if not f.levels or min(f.levels) < XLX_FOR[to] <= max(f.levels):
        return unsure(f"level {f.levels or '?'}: can't tell if it's {XLX_FOR[to]}+")
    if min(f.levels) >= XLX_FOR[to]:
        return tag("XLX", why=f"level {min(f.levels)}+")

    if sid in t["evolved"]:
        return tag("GIV", why=t["evolved"][sid])
    if f.dynamax and (to == TAKER or sid in t["no_dmax"]):
        return tag("GIV", why="untraded Dynamax")
    if to == TAKER and sid in t["giv_for_taker"]:
        return tag("GIV", why=f"{sid}: wanted by {TAKER}")
    if f.far is None:
        return unsure("distance not checked")
    if f.far:
        return tag("GIV", why="caught 100 km+ away")
    return tag("Transfer", why="no rule wants it")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] != "tables":
        sys.exit(__doc__)
    t = tables(a[1] if len(a) > 1 else TAKER)
    if "missing" in t:
        sys.exit(t["missing"])
    print(f"for {t['to']}: {len(t['why'])} species by tag, {len(t['evolved'])} evolved GIV, "
          f"{len(t['no_dmax'])} with no Dynamax one, {len(t['xl_full'])} dex numbers at 360+ Candy XL")
    for k, v in t["from"].items():
        print(f"  {k}: {v}")
