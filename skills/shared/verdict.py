#!/usr/bin/env python3
"""The final tag for a Pokémon that just fell short of a keeper, judged right where it was judged (no Nope).

  python3 verdict.py tables [CyrillJan|HashTagAJay]   the species lists a judge for that account would read now

A script that decides "not a keeper" (pvpc, ivc, fallen) reads what it can on the detail page into Facts and
calls final_tag(facts, tables). The answer is one of:
  tag     put these tags on (and the source tag IVC / PvpC off); `name` too when it's set
  keep    it belongs after all: star on (98%+, a gym defender in its species' top 20, or on its holder's own
          raid team: raidteams.py, right after the user's own tags, traded or not)
          (a shiny one that doesn't belong is a `tag` with star on: shiny())
  unsure  leave it exactly as it is (tags, name). It goes on the not-sure list with why, for a rule offline
Transfer only comes out when every rule above it was checked and none fits: a fact that didn't read, or a species list
that's missing, gives unsure, never Transfer.

The order is tradeable.py's (its docstring has the reasons), judged for the other account, the one it would be traded
to. Signed in as CyrillJan (the pile goes to HashTagAJay):
  GuaranteedLucky > Luckydex > Old > 2XL (a raid attacker's line or a Dynamax one) > Reroll (HashTagAJay needs it: a
  strong line or raid attacker, a ★100% hole, PvP, a lucky family under 348 candy, Tandemaus) > GIV (pattern
  collection) > xxs > GIV (level 26+) > GIV (evolved, Dynamax) > GIV (far) > GIV (can Dynamax, account short of candy)
  > GIV (CyrillJan has under 348 Candy of the family, or under 360 Candy XL of a team line: the trade's candy,
  giver_short. A team line: a species of the family on Team Future, Ideal, or a CyrillJan Team Available or Potential; a Team
  Future/Ideal #1 pick's line wants 360 Candy XL for each 100 CyrillJan has of it, up to 5: tradeable.team_xl_need)
  > Transfer
Signed in as HashTagAJay (the pile goes to CyrillJan or the user's wife's account, judged for any account):
  regional (not from San Francisco) or Spinda: unsure (by hand) > GuaranteedLucky > Old > GIV (medal) > 2XL > Reroll > GIV > xxs > GIV (level 26+) >
  GIV (evolved, 10/12 km egg family, Smeargle, gym defender line, Dynamax) > GIV (trade evolution) > GIV (far) >
  GIV (can Dynamax, account short of candy) > GIV (a Team Future/Ideal line under its bar: team_short) > Transfer
  (Reroll: a strong line (tradeable.strong_lines: on the ideal raid team, or a gym defender's line), DialgaDex top 6
  vs some 4-star+ boss, Master League top 20. CyrillJan's Reroll, only for a 100 HashTagAJay still needs (the user,
  2026-11-20): on the ideal team or HashTagAJay's top 6 only as a mega doesn't count, nor a family HashTagAJay has 5 100s
  of. HashTagAJay's Reroll for a raid reason, only while the line could make one of CyrillJan's Team Potentials (the user,
  2026-11-22: tradeable.no_team_b), and one in only as a mega only till CyrillJan has a 100 of it (tradeable.giver_100).
  HashTagAJay's Reroll too for a line that could make one of CyrillJan's own Team Potentials, IVs rolled new by the
  trade (the user, 2026-11-23: tradeable.giver_team).
  GIV at level 26+ both ways (was XLX, the user 2026-11-19): giver_species())
A Dynamax one (both accounts): 2XL, then GIV (level 26+, then the rest). One that only can Dynamax (or evolves into one that can) gets GIV
while the account holding it has rules.DMAX_CANDY Candy or less, or XL_CAP + one Max Move's Candy XL or less, of
the family (dmax_short, the user 2026-11-16). With more of both and no other rule, Transfer
Before all of them: a special trade (special(): the user, 2026-11-19), a traded one (Transfer), an untraded
shadow, costume or background one (odd_one: the user's rules for each; a shadow's Transfer becomes GuaranteedLucky or
Old when its catch date fits, no purify: shadow_transfer; a strong line's shadow is never purified, and gets Special
where it would get Transfer), and a lucky one, traded or not (lucky(); a lucky costume or background one that would
be Transfer gets its name cleared and a favorite instead).
A special trade not kept (the user, 2026-11-19), its star off and its name back to the default:
  untraded legendary or Ultra Beast: Remote Trade + RT. Traded: Spot Transfer
  mythical: caught in a raid (the door's one `mythical&raid` search) can't be traded: Spot Transfer. Else a one- or
  two-time one (Mew, Celebi, ...): a favorite, kept. Meltan and Melmetal: the legendary rules,
  but a traded Meltan gets plain Transfer (the user, 2026-11-24)
  shiny (any): untraded Remote Trade + RT; traded, a favorite with no tags
A costume one that's a favorite already, traded or not (costume_fav(): the user, 2026-11-19, lucky remote trades bring
rare costumes): it stays a favorite, its name back to the default, never Transfer or a trade tag. One that isn't (an
event's, there are many) gets the rules below.
A costume one (the user, 2026-11-02): 93%+ is named and a favorite, traded or not. Else the usual rules, but if its plain
form evolves and it can't (no Evolve button: dead_end), only as its own species: CyrillJan's raid list and 2XL go by
its own place in DialgaDex's tops (raid_self), and no trade-evolution GIV.
Before everything: an XXL one, traded or not, is a favorite and its trade, Transfer and IVC tags come off (xxl(), the user
2026-11-04: it has value in showcases). Every Transfer for an untraded one goes through transfer() last: an xxs one gets IVC instead, a trade evolution
(free to evolve once traded) GIV, signed in as HashTagAJay only (only CyrillJan wants the XP, the user 2026-11-02).
Then one whose family has an evolution over 100 candy (Magikarp, Snom, Noibat: rules.COSTLY_LINES) GIV, either account
(the user 2026-11-12; not a shadow, and CyrillJan's untraded trade evolutions still get Transfer). The user's own tags first: untraded with Old, Evo, GuaranteedLucky, Remote Trade or RT,
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
import search  # dexes_of, dex_numbers
from rules import GIVER, TAKER, XL_CAP, XLX, XLX_FOR, OLD_XLX
from ivc import GYM_DEFENDERS, make_name as ivc_name
from rules import NAMES as SIZE_NAMES  # a never-traded XXS one gets this name and IVC
from rules import xxl_off
from rules import EVO, EVO_FOR, TRADE_EVOS, COSTLY_LINES  # traded + a free trade evolution: Evo, on EVO_FOR's account

TO = {GIVER: TAKER, TAKER: GIVER}
OLD_DAYS = int(re.search(r"\d+", rules.OLD_AGE).group())
LUCKY_YEARS = rules.LUCKY_YEARS
# GIV (medal), from rules.py's MEDALS: dex -> (size it needs, or None; fits(kg); the kg range that reads right)
MEDALS = {min(search.dexes_of(q)): (("xxs", "xs") if "xxs,xs" in q else None, fits, rules.MEDAL_KG[name])
          for name, q, fits in rules.MEDALS}
FUSED = ("kyurem_black", "kyurem_white", "necrozma_dusk_mane", "necrozma_dawn_wings")  # trades.py: can't be traded
TRADE_BY_HAND = {"meltan", "melmetal"}  # mythical, but trades.py retags them like a legendary
OWN_TAGS = ("Old", EVO, "GuaranteedLucky")  # untraded with one of these: it stays, only IVC / PvpC comes off
TRADE_TAGS = ("GIV", "XLX", "2XL", "Reroll", "Old", "Special", "GuaranteedLucky")  # "trade it": off a traded one
# the user's remote-trade stock (2026-11-13): RT is the whole group they'd part with, the game's own Remote Trade tag the
# ones a partner can see now (some RT ones go without it, hidden from a partner with nothing worth having). Untraded:
# it stays, like Old. Traded: it can't trade again, so both come off
REMOTE_TAGS = ("Remote Trade", "RT")
OWN_TAGS += REMOTE_TAGS
TRADE_TAGS += REMOTE_TAGS
IGNORED_TAGS = ("CPD",)  # as if these tags weren't there: no rule reads them, none takes them off (the user, 2026-11-05)
OVER_93 = 42  # a costume one at 93%+ (42 of 45) is named and a favorite (the user, 2026-11-02)
TRADE_EVO_DEX = search.dex_numbers(TRADE_EVOS)  # evolve free once traded
COSTLY_DEX = search.dex_numbers(COSTLY_LINES)  # a family with an evolution over 100 candy


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
    favorite: bool = False  # its star is on (read for a costume one only; None = not read)
    background: bool = False
    gigantamax: bool = False
    dynamax: bool = False
    size: str = None  # 'xxs', 'xs', 'xl', 'xxl', or '' for none
    kg: float = None
    candy_xl: int = None  # this account's Candy XL of the family
    candy: int = None  # this account's Candy of the family, read on the page (the Dynamax rule asks)
    xl: int = None  # the same account's Candy XL, the count itself (candy_xl is only under XL_CAP or not)
    levels: list = None  # the levels it can be at, from the power-up cost
    evolves: bool = None  # an Evolve button under Power Up (None: that part of the page didn't show)
    far: bool = None  # caught 100 km+ away (the run's one 'distance100-' search)
    gym_top20: bool = None  # a gym defender: top 20 CP or IV of its species (its search)
    iv_top: bool = None  # a lucky one: in /ivc's spots for its line (strong: top 5/6 IV or the best lucky; weak: top IV)
    pure_top: bool = None  # a shadow: a non-shadow spot of its line once purified (/ivc's sort; None: nobody checked)
    pvp_judged: bool = False  # /pvpc already found it's no PvP keeper
    ivc_judged: bool = False  # /ivc or /ivc is judging it: IVC is the tag coming off
    other_tags: list = field(default_factory=list)  # the user's tags besides the one this script works on
    raid_team: object = ()  # raidteams.on_team: the bosses whose team it's on ([] none, () no count), None not sure
    raid: bool = None  # caught in a raid (the door's `mythical&raid` search: mythicals only)


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
    unstar: bool = False  # a tag answer: star off too (a special trade not kept)


def tag(*tags, why, name=None, off=(), purify=False, clear=False, unstar=False):
    return Verdict("tag", tags, why, name, off, purify, clear, unstar=unstar)


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
        _TABLES[to] = {"to": to, "why": sp["why"], "lucky": sp.get("lucky", {}), "evolved": sp["evolved"],
                       "hard": sp.get("hard", {}), "by_hand": set(sp.get("by_hand", ())),
                       "no_dmax": set(sp.get("no_dmax", ())), "xl_full": sp["xl_full"], "dmax": sp.get("dmax", {}),
                       "team_xl": sp.get("team_xl", {}), "team_line": sp.get("team_line"),
                       "from": sp["from"],
                       "raid": set(tr.pve(m)[0]),  # in DialgaDex's top PVE_TOP vs some boss, or evolves into one
                       "strong": set(tr.strong_lines(m)),  # a strong line's species (its shadows: never purified)
                       "raid_self": {s for s in tr.raid_tops(m)[0] if s in m.by}  # in some top as itself
                       | (set(tr.giver_team(m)) if to == GIVER else set())}  # or on a CyrillJan Team Potential
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
    if f.sids and all(pvp.SPECIES.get(s, {}).get("dex") in rules.NO_SHINY for s in f.sids):
        f = replace(f, shiny=False)  # no shiny released: a None or True read is a misread
    if f.size == "xxl":  # first: shiny() below hides a traded one's tags, and no other rule applies
        return xxl(f)
    if not f.shiny:
        return usual(f, t, today)
    # a traded one's tags all come off. An untraded one that already has Remote Trade or RT has what the rule gives it
    tags = [] if f.traded else [x for x in f.other_tags if canon(x) not in REMOTE_TAGS]
    return shiny(f, usual(replace(f, other_tags=tags), t, today))


def xxl(f):
    """an XXL one, traded or not (the user's rule, 2026-11-04): never traded or transferred, it has value in showcases.
    A favorite, with its trade, Transfer and IVC tags off. Its name stays. Other tags stay"""
    return Verdict("keep", (), "XXL: a favorite, for showcases", off=xxl_off(f.other_tags))


def shiny(f, v):
    """a shiny one (the user's rule, 2026-11-03): judged like any other first. If it doesn't qualify, its name goes
    back to the default and it's a favorite. Traded, all its tags come off. Untraded, it gets Remote Trade and RT.
    (On its way to /ivc or /pvpc to be judged, it goes there first)"""
    if f.costume and f.favorite or v.kind != "tag" or "IVC" in v.tags and not f.ivc_judged or "PvpC" in v.tags and not f.pvp_judged:
        return v
    why = f"shiny, doesn't qualify ({v.why})"
    if f.traded:
        return Verdict("tag", (), why, off=tuple(canon(x) for x in f.other_tags), clear=True, star=True)
    return tag("Remote Trade", "RT", why=why, clear=True, unstar=True)  # (star off: the user, 2026-11-19)


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
    # on the holder's own raid team (raidteams.py): a favorite, traded or not, before every Transfer and GIV
    if f.raid_team is None:
        return unsure("raid team: not in the count, and its CP could make a team")
    if f.raid_team:
        return Verdict("keep", (), f"on a raid team: {', '.join(f.raid_team[:3])}"
                                   f"{f' and {len(f.raid_team) - 3} more' if len(f.raid_team) > 3 else ''}", off=strip)
    # shadow, lucky, costume, background: their own rules (odd_one) when untraded. Traded, the usual traded rules
    for k in ("shiny", "costume", "background"):
        if getattr(f, k) is None:
            return unsure(f"{k} or not: not read")
    odd = [k for k in ("shadow", "lucky", "costume", "background") if getattr(f, k)]
    if f.traded is None:
        return unsure("traded or not not read")
    if odd and not f.traded and kinds & {"legendary", "ultrabeast", "mythical"}:
        return unsure(f"{', '.join(odd)} special trade: by hand")
    if f.costume and (v := costume_fav(f, sid, kinds, strip)):  # (before the special trades and Transfer)
        return v
    if f.caught is None:
        return unsure("catch date not read")
    old = (today - f.caught).days >= OLD_DAYS

    # special trades (the user, 2026-11-19): star off, name back to the default
    if f.gigantamax:
        return unsure("Gigantamax: a special trade, by hand")
    if "legendary" in kinds or "ultrabeast" in kinds or "mythical" in kinds:
        return special(f, sid, kinds, strip)

    # a gym defender may still be top 20 CP or IV of its species (/ivc's gym rule), traded or not
    if sid in GYM_DEFENDERS:
        if f.gym_top20 is None:
            return unsure("gym defender: top 20 not checked")
        if f.gym_top20:
            name = ivc_name(tuple(f.ivs), f.shadow, (f.size or "").upper(), lucky=f.lucky, gym=True) if f.ivs else None
            return Verdict("keep", (), "gym defender: top 20 CP or IV", name=name)

    if f.costume and f.iv_sum >= OVER_93:  # (traded or not)
        return costume_93(f, sid, kinds, strip)
    if f.lucky:
        return lucky(f, sid, dexn, strip)
    if odd and not f.traded and (v := odd_one(f, t, sid, odd, today)):
        return v
    dead = dead_end(f, sid)
    if f.traded:
        if f.account == EVO_FOR and dexn in TRADE_EVO_DEX and not dead_end(f, sid):
            return tag(EVO, why="traded: evolves for free", off=strip)
        return tag("Transfer", why="traded: can't trade again", off=strip)
    if to == GIVER and sid in t.get("by_hand", ()):  # (before Old: an old regional is still the user's to tag)
        return unsure("regional or Spinda: likely a special trade, by hand")
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
        return tag(XLX, why=f"level {min(f.levels)}+", off=(OLD_XLX,))

    if sid in t["evolved"]:
        return tag("GIV", why=t["evolved"][sid])
    if sid in t["hard"]:  # (HashTagAJay's side only: a 10 or 12 km egg's family, Smeargle, a gym defender's line)
        return tag("GIV", why=t["hard"][sid])
    if f.dynamax:  # a real Dynamax one, either account (the user, 2026-11-16)
        return tag("GIV", why="untraded Dynamax")
    if f.account != EVO_FOR and dexn in TRADE_EVO_DEX and not dead:  # (before the distance, so a failed distance
        # search doesn't matter). Only toward EVO_FOR: HashTagAJay doesn't need the XP (the user, 2026-11-02)
        return tag("GIV", why="untraded: evolves free once traded")
    if f.far is None:
        return unsure("distance not checked")
    if f.far:
        return tag("GIV", why="caught 100 km+ away")
    if v := dmax_short(f, t, sid):  # (after the GIVs that need no count read)
        return v
    if to == TAKER and (v := giver_short(f, t)):
        return v
    if to != TAKER and (v := team_short(f, t)):  # (CyrillJan's: in giver_short, after its under-XL_CAP one)
        return v
    return transfer(f, sid, "no rule wants it")


def giver_short(f, t):
    """CyrillJan's pile (untraded: a traded one never gets here): GIV while CyrillJan has under LUCKY_CANDY Candy of
    the family, or under XL_CAP Candy XL of a team line (t['team_line']: a species of the family on Team Future, Team
    Ideal or one of CyrillJan's Team Availables or Potentials, tradeable.team_lines; the user, 2026-11-23: no trade for
    any other line's XL). The trade pays the sender 2-4 Candy and a Candy XL, a transfer 1 Candy
    (rules.TRADE_SENDER_CANDY; the user, 2026-11-23). A Team Future/Ideal #1 pick's line wants XL_CAP for each 100
    CyrillJan has of it, up to TEAM_SLOTS (t['team_xl']: tradeable.team_xl_need; the user, 2026-11-23). None: not short"""
    line = t.get("team_line")
    if line is None or any(s in line for s in f.sids):
        if f.candy_xl is None:
            return unsure("Candy XL not read")
        if f.candy_xl < XL_CAP:
            if line is None:
                return unsure(f"under {XL_CAP} Candy XL, and no raid team count for {GIVER}: a team line or not")
            return tag("GIV", why=f"{f.account} has under {XL_CAP} Candy XL of a team line: the trade's XL")
    if v := team_short(f, t):
        return v
    if f.candy is None:
        return unsure("Candy not read")
    if f.candy < rules.LUCKY_CANDY:
        return tag("GIV", why=f"{f.account} has {f.candy} Candy of the family, under {rules.LUCKY_CANDY}: the trade's candy")
    return None


def team_short(f, t):
    """either account (the user, 2026-11-23): GIV while the account holding it has under its line's Team Future/Ideal
    bar of Candy XL (t['team_xl']: XL_CAP for each 100 it has of the #1 pick, up to TEAM_SLOTS:
    tradeable.team_xl_need). The trade gives the sender a Candy XL, a transfer none. None: no bar, or over it"""
    team = t.get("team_xl", {})
    if any(s in team and team[s] is None for s in f.sids):
        return unsure("a Team Future/Ideal pick's line: its 100s not counted (tradeable.py team100)")
    if not (bars := [team[s] for s in f.sids if s in team]):
        return None
    bar, pick, n = max(bars)
    if f.xl is None:
        return unsure("Candy XL not read")
    if f.xl < bar:
        return tag("GIV", why=f"{f.account} has {n} 100s of {pick}'s line (Team Future/Ideal): wants {bar} Candy XL, "
                              f"has {f.xl}")
    return None


def special(f, sid, kinds, strip):
    """a legendary, mythical or Ultra Beast one not kept (the user, 2026-11-19): star off, name back to the default.
    A mythical caught in a raid can't be traded: Spot Transfer. Any other mythical (Mew, Celebi, ...: one- or
    two-time ones) is a favorite, kept. A legendary or Ultra Beast (and Meltan, Melmetal): untraded Remote Trade + RT,
    traded Spot Transfer. A traded Meltan: plain Transfer (the user, 2026-11-24: plenty of Meltan Candy)"""
    if "mythical" in kinds and sid not in TRADE_BY_HAND:
        if f.raid is None:
            return unsure("mythical: caught in a raid or not, not read")
        if not f.raid:
            return Verdict("keep", (), "mythical, not from a raid: a one- or two-time one, kept")
        return tag("Spot Transfer", why="mythical from a raid: can't be traded", off=strip, clear=True, unstar=True)
    if f.traded and sid == "meltan":  # (before the size: no trade, so an xxs one is no matter)
        return tag("Transfer", why="traded Meltan: plenty of its Candy", off=strip, clear=True, unstar=True)
    if f.size is None or f.size in SIZE_NAMES:  # trades.py passes over an xxs one
        return unsure(f"special trade, size {f.size or 'not read'}: by hand")
    if f.traded:
        return tag("Spot Transfer", why="traded special trade: a spot transfer", off=strip, clear=True, unstar=True)
    if sid in FUSED:
        return unsure("fused: can't be traded")
    return tag("Remote Trade", "RT", why="untraded special trade: a remote trade", clear=True, unstar=True)


def dmax_short(f, t, sid):
    """one that can Dynamax (or evolves into one that can), but isn't a Dynamax one: GIV while the account holding it
    is short of that family's Candy (DMAX_CANDY or less) or Candy XL (XL_CAP + one Max Move's XL, or less). With
    both over, no rule wants it for this and it goes on to the rest (the user, 2026-11-16). None: not one of these"""
    need = t.get("dmax", {}).get(sid)
    if need is None:
        return None
    if f.candy is None or f.xl is None:
        return unsure("can Dynamax: Candy or Candy XL not read")
    if f.candy <= rules.DMAX_CANDY or f.xl <= need:
        return tag("GIV", why=f"can Dynamax: {f.candy} Candy, {f.xl} Candy XL "
                              f"(wants over {rules.DMAX_CANDY} and {need})")
    return None


def two_xl(f, t, sid):
    """2XL (a Friendship Friday trade: a sure 2 Candy XL) when this account has under XL_CAP Candy XL of the family.
    The same rule costume or not (the user, 2026-11-02). On CyrillJan only a raid attacker's line gets it: those need
    XL for their top levels, and a Dynamax one (Max Moves cost Candy XL: 2XL, then GIV at level 26+, then GIV, the user 2026-11-16).
    Never an xxs one (an XXL one never gets here). -> Verdict, or None for the next rule"""
    raid = t["raid_self"] if dead_end(f, sid) else t["raid"]
    if f.size in ("xxl", "xxs") or (f.account == GIVER and sid not in raid and not f.dynamax):
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
      account (the user, 2026-11-12). Not a shadow, and not a trade evolution on EVO_FOR (that rule stays). GIV at 26+ and
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


def costume_93(f, sid, kinds, strip=()):
    """a costume one at 93%+ (the user, 2026-11-02): named and a favorite, traded or not"""
    if f.ivs is None:
        return unsure("costume 93%+: IVs not read (for its name)")
    name = ivc_name(tuple(f.ivs), f.shadow, (f.size or "").upper(), lucky=f.lucky,
                    legendary=bool(kinds & {"legendary", "ultrabeast", "mythical"}), gym=sid in GYM_DEFENDERS)
    return Verdict("keep", (), f"costume, {round(f.iv_sum / 45 * 100)}%: named and a favorite", name=name, off=strip)


def costume_fav(f, sid, kinds, strip):
    """a costume one on no raid team that's a favorite already, traded or not, lucky, shadow or shiny too (the user,
    2026-11-19: lucky remote trades bring rare costumes): it stays a favorite, its name back to the default (93%+:
    costume_93's name), never Transfer or a trade tag. -> Verdict, or None: not a favorite, the usual rules (an
    event's costume: there are many)"""
    if f.favorite is None:
        return unsure("costume: a favorite or not not read")
    if not f.favorite:
        return None
    if f.iv_sum >= OVER_93:
        return costume_93(f, sid, kinds, strip)
    return Verdict("tag", (), "costume, a favorite already: stays one, name back to the default, never traded or "
                              "transferred", off=strip, clear=True, star=True)


def lucky(f, sid, dexn, strip):
    """a lucky one, traded or not (the user's rule, 2026-10-30): in /ivc's spots for its line it stays: on a strong
    line the top 5 IV of its non-shadow ones (6 if the line can mega evolve), on a weak family only its top IV (the
    user, 2026-11-19: strong = on the ideal raid team, sort.strong; no lucky spot of its own), ties keep. Out of that, one with a PvP
    top-100 IV goes to /pvpc, which compares it with the ones you own. The rest: name cleared, Transfer (door.py checks
    the power-up first). A costume or background one never gets that Transfer: name cleared and a favorite (the user,
    2026-11-18). A traded one that evolves for free gets Evo instead. Only /ivc ranks it: from anywhere else it goes to IVC, name cleared, and
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
    v = transfer(f, sid, "lucky: out of the top IV and PvP", off=strip, clear=True)
    odd = [k for k in ("costume", "background") if getattr(f, k)]
    if v.tags == ("Transfer",) and odd:  # (the user, 2026-11-18): never Transfer, a favorite with its name cleared
        return Verdict("tag", (), f"lucky {' '.join(odd)}, out of the top IV and PvP: a favorite, name cleared",
                       off=strip, clear=True, star=True)
    return v


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
    if sid in t.get("strong", ()):  # never purified: GuaranteedLucky or Old if it fits, else Special (the user, 2026-11-19)
        v = shadow_transfer(f, sid, "shadow in a strong line: never purified", today)
        if v.tags == ("Transfer",):
            return tag("Special", why=v.why + ": Special, never Transfer")
        return replace(v, unstar=True) if v.tags in (("GuaranteedLucky",), ("Old",)) else v
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
