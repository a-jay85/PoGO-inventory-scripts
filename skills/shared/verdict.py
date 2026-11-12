#!/usr/bin/env python3
"""The final tag for a Pokémon that just fell short of a keeper, judged right where it was judged (no Nope).

  python3 verdict.py tables [CyrillJan|HashTagAJay]   the species lists a judge for that account would read now

A script that decides "not a keeper" (pvpc, ivc, fallen) reads what it can on the detail page into Facts and
calls final_tag(facts, tables). The answer is one of:
  tag     put these tags on (and the source tag IVC / PvpC off); `name` too when it's set
  keep    it belongs after all: star on (98%+, or a gym defender in its species' top 20)
          (a shiny one that doesn't belong is a `tag` with star on: shiny())
  unsure  leave it exactly as it is (tags, name). It goes on the not-sure list with why, for a rule offline
Transfer only comes out when every rule above it was checked and none fits: a fact that didn't read, or a species list
that's missing, gives unsure, never Transfer.

The order is tradeable.py's (its docstring has the reasons), judged for the other account, the one it would be traded
to. Signed in as CyrillJan (the pile goes to HashTagAJay):
  GuaranteedLucky > Luckydex > Old > 2XL (a raid attacker's line only) > Reroll > GIV > xxs > XLX > GIV
  (evolved, Dynamax, Tandemaus) > GIV (far) > Transfer
Signed in as HashTagAJay (the pile goes to CyrillJan):
  GuaranteedLucky > Old > GIV (medal) > 2XL > GIV > xxs > XLX > GIV (evolved, Dynamax) > GIV (trade evolution) >
  GIV (far) > Transfer
  (its raid GIV: a new copy gets into one of CyrillJan's /roster teams, or within 15% of the #6: giver_species())
Before all of them: a special trade (trades.py's legendary rules, else unsure), a traded one (Transfer), an untraded
shadow, costume or background one (odd_one: the user's rules for each; a shadow's Transfer becomes GuaranteedLucky or
Old when its catch date fits, no purify: shadow_transfer), and a lucky one, traded or not (lucky()).
A costume one (the user, 2026-11-02): 93%+ is named and a favorite, traded or not. Else the usual rules, but if its plain
form evolves and it can't (no Evolve button: dead_end), only as its own species: CyrillJan's raid list and 2XL go by
its own place in DialgaDex's tops (raid_self), and no trade-evolution GIV.
Before everything: an XXL one, traded or not, is a favorite and its trade, Transfer and IVC tags come off (xxl(), the user
2026-11-04: it has value in showcases). Every Transfer for an untraded one goes through transfer() last: an xxs one gets IVC instead, a trade evolution
(free to evolve once traded) GIV, signed in as HashTagAJay only (only CyrillJan wants the XP, the user 2026-11-02).
Then one whose family has an evolution over 100 candy (Magikarp, Snom, Noibat: rules.COSTLY_LINES) GIV, either account
(the user 2026-11-12; not a shadow, and CyrillJan's untraded trade evolutions still get Transfer). The user's own tags first: untraded with Old, Evo or GuaranteedLucky,
those stay and only IVC / PvpC comes off; traded, the "trade it" tags (TRADE_TAGS) come off. The species lists come
from tradeable.py's taker_species() and giver_species(), the same ones its tag searches use. Neither account's have an age
limit: the newest saved copy is used, however old (the user, 2026-11-04 and 2026-11-06).
"""
import datetime, os, re, sys
from dataclasses import dataclass, field, replace

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "cleanup"))
import pvp
from base import ALWAYS_KEEP  # an IV sum of 98%+ never loses its star
import tradeable as tr  # builds the species lists
import rules  # the numbers and lists: one copy, there
from rules import GIVER, TAKER, XL_CAP, XLX_FOR
from ivc import GYM_DEFENDERS, make_name as ivc_name
from rules import NAMES as SIZE_NAMES  # a never-traded XXS one gets this name and IVC
from rules import xxl_off
from rules import EVO, EVO_FOR, TRADE_EVOS, COSTLY_LINES  # traded + a free trade evolution: Evo, on EVO_FOR's account

TO = {GIVER: TAKER, TAKER: GIVER}
OLD_DAYS = int(re.search(r"\d+", rules.OLD_AGE).group())
LUCKY_YEARS = rules.LUCKY_YEARS
# GIV (medal), from rules.py's MEDALS: dex -> (size it needs, or None; fits(kg); the kg range that reads right)
MEDALS = {min(tr.dexes_of(q)): (("xxs", "xs") if "xxs,xs" in q else None, fits, rules.MEDAL_KG[name])
          for name, q, fits in rules.MEDALS}
FUSED = ("kyurem_black", "kyurem_white", "necrozma_dusk_mane", "necrozma_dawn_wings")  # trades.py: can't be traded
TRADE_BY_HAND = {"meltan", "melmetal"}  # mythical, but trades.py retags them like a legendary
OWN_TAGS = ("Old", EVO, "GuaranteedLucky")  # untraded with one of these: it stays, only IVC / PvpC comes off
TRADE_TAGS = ("GIV", "XLX", "2XL", "Reroll", "Old", "Special", "GuaranteedLucky")  # "trade it": off a traded one
IGNORED_TAGS = ("CPD",)  # as if these tags weren't there: no rule reads them, none takes them off (the user, 2026-11-05)
OVER_93 = 42  # a costume one at 93%+ (42 of 45) is named and a favorite (the user, 2026-11-02)
TRADE_EVO_DEX = {int(d) for d in TRADE_EVOS.split(",")}  # evolve free once traded
COSTLY_DEX = {int(d) for d in COSTLY_LINES.split(",")}  # a family with an evolution over 100 candy


@dataclass
class Facts:
    """what the script read. None = couldn't read it (then any rule that needs it answers unsure)"""
    account: str = None  # signed in: CyrillJan or HashTagAJay
    sids: list = None  # the species it could be (ui.species_for); more than one that disagree -> unsure
    iv_sum: int = None  # from the appraisal (0-45)
    ivs: tuple = None  # (attack, defense, HP), for what purifying would make it
    traded: bool = None
    caught: datetime.date = None
    gender: str = None  # 'male', 'female', or '' for a genderless one
    shiny: bool = False  # shiny, costume, background: None = its search failed
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
    evolves: bool = None  # an Evolve button under Power Up (None: that part of the page didn't show)
    far: bool = None  # caught 100 km+ away (the run's one 'distance100-' search)
    gym_top20: bool = None  # a gym defender: top 20 CP or IV of its species (its search)
    iv_top: bool = None  # a lucky one: top 5 IV of its line's non-shadow ones, 6 if it can mega (/ivc's sort)
    pure_top: bool = None  # a shadow: a non-shadow spot of its line once purified (/ivc's sort; None: nobody checked)
    pvp_judged: bool = False  # /pvpc already found it's no PvP keeper
    ivc_judged: bool = False  # /ivc or /ivc is judging it: IVC is the tag coming off
    other_tags: list = field(default_factory=list)  # the user's tags besides the one this script works on


@dataclass
class Verdict:
    kind: str  # 'tag', 'keep' or 'unsure'
    tags: tuple = ()
    why: str = ""
    name: str = None  # a new nickname to type, when set
    off: tuple = ()  # the user's tags to take off too (IVC / PvpC always comes off)
    purify: bool = False  # purify it first
    clear: bool = False  # clear its name too
    star: bool = False  # a tag answer: star on too (a shiny one)


def tag(*tags, why, name=None, off=(), purify=False, clear=False):
    return Verdict("tag", tags, why, name, off, purify, clear)


def unsure(why):
    return Verdict("unsure", (), why)


# ---------- the species lists ----------

_TABLES = {}


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
        why = sp["why"] if to == TAKER else {s: ("GIV", r) for s, r in sp["why"].items()}
        _TABLES[to] = {"to": to, "why": why, "lucky": sp.get("lucky", {}), "evolved": sp["evolved"],
                       "no_dmax": set(sp.get("no_dmax", ())), "xl_full": sp["xl_full"],
                       "giv_for_taker": set(rules.GIV_FOR_TAKER), "from": sp["from"],
                       "raid": set(tr.pve(m)[0]),  # in DialgaDex's top PVE_TOP vs some boss, or evolves into one
                       "raid_self": {s for s in tr.raid_tops(m)[0] if s in m.by}}  # in some top as itself
    return _TABLES[to]


# ---------- the rules ----------

def canon(t):
    """a tag as read ('GUARANTEEDLUCKY') -> its name ('GuaranteedLucky'), when it's one the rules know"""
    # letters only: the page's reader drops digits, so 2XL reads as XL
    key = lambda s: re.sub(r"[^A-Z]", "", s.upper())
    return next((x for x in OWN_TAGS + TRADE_TAGS if key(x) == key(t)), t.strip())


def final_tag(f, t, today=None):
    """f: Facts. t: tables(TO[f.account]). -> Verdict"""
    f = replace(f, other_tags=[x for x in f.other_tags if x.strip().upper() not in IGNORED_TAGS])
    if f.size == "xxl":  # first: shiny() below hides a traded one's tags, and no other rule applies
        return xxl(f)
    if not f.shiny:
        return usual(f, t, today)
    # a traded one's tags all come off. An untraded one that already has Remote Trade or RT has what the rule gives it
    tags = [] if f.traded else [x for x in f.other_tags if re.sub(r"[^A-Z]", "", x.upper()) not in ("REMOTETRADE", "RT")]
    return shiny(f, usual(replace(f, other_tags=tags), t, today))


def xxl(f):
    """an XXL one, traded or not (the user's rule, 2026-11-04): never traded or transferred, it has value in showcases.
    A favorite, with its trade, Transfer and IVC tags off. Its name stays. Other tags stay"""
    return Verdict("keep", (), "XXL: a favorite, for showcases", off=xxl_off(f.other_tags))


def shiny(f, v):
    """a shiny one (the user's rule, 2026-11-03): judged like any other first. If it doesn't qualify, its name goes
    back to the default and it's a favorite. Traded, all its tags come off. Untraded, it gets Remote Trade and RT.
    (On its way to /ivc or /pvpc to be judged, it goes there first)"""
    if v.kind != "tag" or "IVC" in v.tags and not f.ivc_judged or "PvpC" in v.tags and not f.pvp_judged:
        return v
    why = f"shiny, doesn't qualify ({v.why})"
    if f.traded:
        return Verdict("tag", (), why, off=tuple(canon(x) for x in f.other_tags), clear=True, star=True)
    return Verdict("tag", ("Remote Trade", "RT"), why, clear=True, star=True)


def usual(f, t, today=None):
    """final_tag's rules, for all but what a shiny one gets in the end"""
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
    # shadow, lucky, costume, background: their own rules (odd_one) when untraded. Traded, the usual traded rules
    for k in ("shiny", "costume", "background"):
        if getattr(f, k) is None:
            return unsure(f"{k} or not: not read")
    odd = [k for k in ("shadow", "lucky", "costume", "background") if getattr(f, k)]
    if f.traded is None:
        return unsure("traded or not not read")
    if odd and not f.traded and kinds & {"legendary", "ultrabeast", "mythical"}:
        return unsure(f"{', '.join(odd)} special trade: by hand")
    if f.caught is None:
        return unsure("catch date not read")
    old = (today - f.caught).days >= OLD_DAYS

    # special trades: trades.py's rules for legendaries, Ultra Beasts, Meltan and Melmetal. The rest by hand
    if f.gigantamax:
        return unsure("Gigantamax: a special trade, by hand")
    if "legendary" in kinds or "ultrabeast" in kinds or "mythical" in kinds:
        if "mythical" in kinds and sid not in TRADE_BY_HAND:
            return unsure("mythical: can't be traded, by hand")
        if f.size is None or f.size in SIZE_NAMES:  # trades.py passes over an xxs one
            return unsure(f"special trade, size {f.size or 'not read'}: by hand")
        if f.traded:
            return tag("Spot Transfer", why="traded special trade: a spot transfer", off=strip)
        if sid in FUSED:
            return unsure("fused: can't be traded")
        return tag("Remote Trade", "RT", *(("Old",) if old else ()), why="untraded special trade: a remote trade")

    # a gym defender may still be top 20 CP or IV of its species (/ivc's gym rule), traded or not
    if sid in GYM_DEFENDERS:
        if f.gym_top20 is None:
            return unsure("gym defender: top 20 not checked")
        if f.gym_top20:
            name = ivc_name(tuple(f.ivs), f.shadow, (f.size or "").upper(), lucky=f.lucky, gym=True) if f.ivs else None
            return Verdict("keep", (), "gym defender: top 20 CP or IV", name=name)

    if f.costume and f.iv_sum >= OVER_93:  # (traded or not)
        if f.ivs is None:
            return unsure("costume 93%+: IVs not read (for its name)")
        name = ivc_name(tuple(f.ivs), f.shadow, (f.size or "").upper(), lucky=f.lucky,
                        legendary=bool(kinds & {"legendary", "ultrabeast", "mythical"}), gym=sid in GYM_DEFENDERS)
        return Verdict("keep", (), f"costume, {round(f.iv_sum / 45 * 100)}%: named and a favorite", name=name)
    if f.lucky:
        return lucky(f, sid, dexn, strip)
    if odd and not f.traded and (v := odd_one(f, t, sid, odd, today)):
        return v
    dead = dead_end(f, sid)
    if f.traded:
        if f.account == EVO_FOR and dexn in TRADE_EVO_DEX and not dead_end(f, sid):
            return tag(EVO, why="traded: evolves for free", off=strip)
        return tag("Transfer", why="traded: can't trade again", off=strip)
    if LUCKY_YEARS[0] <= f.caught.year <= LUCKY_YEARS[1]:
        return tag("GuaranteedLucky", why=f"untraded, caught {f.caught.year}: lucky once traded")

    if "missing" in t:
        return unsure(f"no species lists for {to}: {t['missing']}")
    why = t["why"].get(sid)
    if dead and to == GIVER and sid not in t["raid_self"]:
        why = None  # (CyrillJan's list counts a species whose evolution is a raid attacker: this one can't evolve)

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
    if v := two_xl(f, t, sid):
        return v

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
    if f.account != EVO_FOR and dexn in TRADE_EVO_DEX and not dead:  # (before the distance, so a failed distance
        # search doesn't matter). Only toward EVO_FOR: HashTagAJay doesn't need the XP (the user, 2026-11-02)
        return tag("GIV", why="untraded: evolves free once traded")
    if f.far is None:
        return unsure("distance not checked")
    if f.far:
        return tag("GIV", why="caught 100 km+ away")
    return transfer(f, sid, "no rule wants it")


def two_xl(f, t, sid):
    """2XL (a Friendship Friday trade: a sure 2 Candy XL) when this account has under XL_CAP Candy XL of the family.
    The same rule costume or not (the user, 2026-11-02). On CyrillJan only a raid attacker's line gets it: those need
    XL for their top levels. Never an xxs one (an XXL one never gets here). -> Verdict, or None for the next rule"""
    raid = t["raid_self"] if dead_end(f, sid) else t["raid"]
    if f.size in ("xxl", "xxs") or (f.account == GIVER and sid not in raid):
        return None
    if f.candy_xl is None:
        return unsure("Candy XL not read")
    if f.candy_xl < XL_CAP:
        return tag("2XL", why=f"under {XL_CAP} Candy XL: a Friendship Friday trade")
    return None


def transfer(f, sid, why, off=(), purify=False, clear=False):
    """Transfer, unless it's untraded and (the user's rules, 2026-10-31, for every Transfer):
      an xxs one -> IVC, named xxs (/ivc counts that name as done)
      one that evolves free once traded (TRADE_EVOS) -> GIV, signed in as HashTagAJay only (it goes to EVO_FOR,
      who wants the XP; HashTagAJay doesn't, the user 2026-11-02). A shadow can't be traded: it never is
      one whose family has an evolution over 100 candy (COSTLY_LINES: Magikarp, Snom, Noibat, ...) -> GIV, either
      account (the user, 2026-11-12). Not a shadow, and not a trade evolution on EVO_FOR (that rule stays). XLX and
      every other rule come before this, as before
    The size comes first, as in final_tag's order. A size that didn't read gives unsure, never Transfer"""
    if not f.traded:
        if f.size is None:
            return unsure(f"{why}, but size not read (an untraded xxs one gets IVC)")
        if f.size in SIZE_NAMES:
            return tag("IVC", why=f"never traded {f.size.upper()} (else Transfer: {why})", name=SIZE_NAMES[f.size],
                       off=off)
        if f.account != EVO_FOR and not f.shadow and pvp.SPECIES[sid]["dex"] in TRADE_EVO_DEX and not dead_end(f, sid):
            return tag("GIV", why=f"untraded, evolves free once traded (else Transfer: {why})", off=off, clear=clear)
        dexn = pvp.SPECIES[sid]["dex"]
        if not f.shadow and dexn in COSTLY_DEX and not (f.account == EVO_FOR and dexn in TRADE_EVO_DEX):
            return tag("GIV", why=f"untraded, its line has an evolution over 100 candy (else Transfer: {why})", off=off,
                       clear=clear)
    return tag("Transfer", why=why, off=off, purify=purify, clear=clear)


def lucky(f, sid, dexn, strip):
    """a lucky one, traded or not (the user's rule, 2026-10-30): in the top 5 IV of its line's non-shadow ones (6 if
    the line can mega evolve, ties keep) it stays. Out of that, one with a PvP top-100 IV goes to /pvpc, which compares
    it with the ones you own. The rest: name cleared, Transfer (door.py checks the power-up first). A traded one that
    evolves for free gets Evo instead. Only /ivc ranks it: from anywhere else it goes to IVC, name cleared, and
    /ivc ranks it next"""
    if f.iv_top is None:
        if f.ivc_judged:
            return unsure("lucky: /ivc couldn't rank it (no IV in its name)")
        return tag("IVC", why="lucky: /ivc ranks it against its line", off=strip, clear=True)
    if f.iv_top:
        return Verdict("keep", (), "lucky: a top IV of its line")
    if not f.pvp_judged:
        if f.ivs is None:
            return unsure("lucky: IVs not read")
        name, _ = pvp.make_name(sid, tuple(f.ivs), min(f.levels) if f.levels else None)
        if name:
            return tag("PvpC", why=f"lucky, out of the top IV, but PvP {name}: /pvpc judges it", off=strip)
    if f.traded and f.account == EVO_FOR and dexn in TRADE_EVO_DEX:
        return tag(EVO, why="traded lucky, out of the top IV and PvP: evolves for free", off=strip)
    return transfer(f, sid, "lucky: out of the top IV and PvP", off=strip, clear=True)


def plain_evolves(sid):
    return bool(pvp.SPECIES[sid].get("family", {}).get("evolutions"))  # (Unown has no family: 2026-11-02)


def dead_end(f, sid):
    """a costume one whose plain form evolves, but it can't (no Evolve button): judged as its own species only, for
    raids and PvP (the user, 2026-11-02)"""
    return bool(f.costume) and f.evolves is False and plain_evolves(sid)


def odd_one(f, t, sid, odd, today):
    """an untraded shadow, costume or background one (the user's rules, 2026-10-29; 360+ Candy XL, 2026-10-30).
    -> Verdict, or None: a costume one goes on to the usual rules once its Evolve button is read"""
    if "background" in odd:
        return Verdict("keep", (), "a special background: a favorite")
    if "shadow" in odd and "costume" in odd:
        return unsure("shadow costume: by hand")
    if odd == ["costume"]:
        if plain_evolves(sid) and f.evolves is None:
            return unsure("costume: its plain form evolves, Evolve button not read")
        return None  # the usual rules (a costume one that can't evolve: as its own species, dead_end)
    if "missing" in t:
        return unsure(f"{odd[0]}: no species lists for {t['to']}: {t['missing']}")
    # shadow (it can't be traded)
    if f.ivs is None:
        return unsure("shadow: IVs not read")
    pure = sum(min(15, i + 2) for i in f.ivs)
    if pure >= ALWAYS_KEEP:
        return Verdict("keep", (), f"shadow, purified {round(pure / 45 * 100)}%: a favorite")
    if f.pure_top:
        return Verdict("keep", (), "shadow raid attacker, a top IV once purified: a favorite")
    if sid in t["raid"] and f.pure_top is None:
        return unsure("shadow raid attacker: top 6 IV once purified? not checked")
    if f.candy_xl is None:
        return unsure("shadow: Candy XL not read")
    if f.candy_xl < XL_CAP:
        return shadow_transfer(f, sid, f"shadow, under {XL_CAP} Candy XL: purify and transfer", today, purify=True)
    return shadow_transfer(f, sid, f"shadow, {XL_CAP}+ Candy XL: transfer, no purify", today)


def shadow_transfer(f, sid, why, today, purify=False):
    """a shadow's Transfer (the user, 2026-11-08): a catch date that would get GuaranteedLucky or Old gets that tag
    instead, and it isn't purified (the user purifies by hand). Anything else transfer() gives (IVC for xxs) stays"""
    v = transfer(f, sid, why, purify=purify)
    if v.tags != ("Transfer",):
        return v
    if LUCKY_YEARS[0] <= f.caught.year <= LUCKY_YEARS[1]:
        return tag("GuaranteedLucky", why=f"shadow, caught {f.caught.year}: lucky once purified and traded (else {why})")
    if (today - f.caught).days >= OLD_DAYS:
        return tag("Old", why=f"shadow, caught {(today - f.caught).days} days ago (else {why})")
    return v


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
