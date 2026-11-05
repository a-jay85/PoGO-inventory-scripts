#!/usr/bin/env python3
"""Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer.

  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py [--limit N]
  caffeinate -dimsu python3 cleantrades.py [--limit N]    the iPhone, through iPhone Mirroring
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py --look    only step 2, and it only reads: CANCEL every time
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py evo       steps 1 and 3
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py fix       #Transfer&traded + a trade evolution: Transfer -> Evo
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py transfer [--limit N]   step 2 for all of #Transfer
                                          (catches up the ones tagged before every tagger powered them up first)

Start with Pokémon GO on the Pokémon screen. Four steps, always in this order:
 1. Shortcuts PvpC1 and PvpC2 -> tag PvpC. Shortcut IV Check -> tag IVC. A shortcut this account doesn't have is
    skipped. This goes first: Clean Trades only shows untagged ones (!#), so these drop out of it.
 2. Clean Trades + &countcandyxl0-359 (under 360 Candy XL). Each one is opened and POWER UP tapped: the dialog's
    "CP a -> b" and Stardust cost narrow its level. Each + (one more power-up) shows new totals that narrow it
    more. At level 14, 19, 22 or 30 (or the half level after) it gets 1-2 power-ups in one go, to reach 15, 20, 23
    or 31: the next XL-on-transfer tier
    (~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md). Anything else: CANCEL. Never below 1,000,000 Stardust.
 3. CyrillJan only (HashTagAJay doesn't need the XP): Clean Trades + a trade evolution (free once traded: Kadabra, Machoke, Graveler, Haunter, Boldore, Gurdurr,
    Karrablast, Shelmet, Phantump, Pumpkaboo) -> tag Evo. Not the base forms (Abra...).
 4. Clean Trades -> tag Transfer.
Before step 2, the ones that must not get Transfer leave the pile: Clean Trades &xxl, traded or not -> favorite, and no
step here touches an XXL one (&!xxl). Clean Trades &!traded&xxs -> renamed xxs, tagged IVC (sizes.py); Clean Trades &!traded&!shadow + a trade evolution -> tag GIV.
Tagging: the shortcut's search + &!#<tag> (PvpC1, PvpC2 and Clean Trades as they are: they already exclude tagged ones), long press, SELECT ALL, TAG (n). n must equal the search's count, and
afterwards the same search must come back empty.
--limit N powers up at most N Pokémon (the tagging still runs). Log in runs/<time>/.
Every script that tags Transfer runs step 2 on that pile first (power_pile): tradeable.py too.

Which account: the storage max over the empty search, over 10,000 is HashTagAJay. evo and fix stop on HashTagAJay.
--limit reached: the rest weren't checked, so Clean Trades isn't tagged Transfer that run. A "count..." term eats any
text after it, so the XL part always goes last. On the Pixel, HashTagAJay's PvpC1 search fills the bar.
iPhone: tagging ran 2026-10-19, the power-up walk and swipe haven't yet. The first time, run --look, then --limit 1.
"""
import math, os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, Skip, log, keep_capture, go, look, wait_for
import search, session
import pvp
import powerup
from taps import Pass, next_one
from savedsearch import run_shortcut, tag_pile, long_search
from powerup import Unsure, power_up
from rules import CLEAN, TRANSFER, EVO, TRADE_EVOS, EVO_FOR, UNDER_360_XL


TAGGING = [("PvpC1", "PvpC"), ("PvpC2", "PvpC"), ("IV Check", "IVC")]
BIG = 10_000  # storage max: HashTagAJay 13,000, CyrillJan 7,875 (2026-10-22)


def account():
    """which account, by the storage max over the empty search ('7874 / 7875'): HashTagAJay's is thousands higher"""
    for _ in range(3):
        search.clear_search()
        for _ in range(8):
            time.sleep(0.3)
            texts = look()[1]
            got = [int(m.group(1).replace(",", "")) for t in texts if t[1] < 0.15
                   and (m := re.fullmatch(r"\d[\d,]{2,}\s*/\s*(\d[\d,]{2,})\W?", t[4].strip()))]  # (not the 10/12 shortcuts)
            # \W?: on the iPhone the bar's edge can read as a '|' stuck on the end ('12900/12900|')
            if len(got) == 1:
                who = "HashTagAJay" if got[0] > BIG else EVO_FOR
                log(f"storage {got[0]:,}: {who}")
                return who
    keep_capture("account")
    raise Stop("can't read the storage max, so can't tell which account this is")


def power_walk(limit, query=None):
    """open each Clean Trades one (query: each one in this typed search) with under 360 XL and power up those right
    under a tier. -> how many got it, or None if --limit stopped it"""
    under = UNDER_360_XL + "&!xxl"  # (an XXL one stays: no power-ups for a transfer)
    if not (long_search(query + under) if query else run_shortcut(CLEAN, under)):
        log(f"no {query or CLEAN} ones under 360 XL")
        return 0
    go("tile 1", "detail")
    seen, done, passed, t_start, again = set(), 0, 0, time.time(), False
    unseen = lambda t: (lambda n: (n["name"], n["cp"], n["hp"]))(ui.detail_info(t)) not in seen
    while True:
        t0 = time.time()
        for _ in range(10):  # right after a swipe the CP sparkles in and can read blank
            _, texts, _, _ = wait_for("detail")
            info = ui.detail_info(texts)
            if info["cp"] is not None:
                break
            time.sleep(0.2)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:  # a read mid-swipe can look like another one while the page hasn't moved: one more swipe
            if again or not next_one(None, unseen, poll=search.POLL):
                log("swiped back onto one already seen: end of the list")
                break
            again = True
            continue
        again = False
        seen.add(me)
        if done >= limit:
            log(f"--limit {limit} reached")
            return None  # (the rest weren't checked)
        try:
            try:
                taps = power_up(info, texts)
            except Unsure as e:  # mostly a read while the page still slid: one more go on a fresh look
                log(f"  {e}: looking again")
                time.sleep(0.5)
                texts = wait_for("detail")[1]
                info = {**info, **{k: v for k, v in ui.detail_info(texts).items() if v is not None}}
                taps = power_up(info, texts)
        except Pass as e:
            passed += 1
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        else:
            done += 1
            info2 = ui.detail_info(wait_for("detail")[1])
            seen.add((info2["name"], info2["cp"], info2["hp"]))
            log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {taps} power-up(s)  ({time.time() - t0:.1f}s)")
        if not next_one(None, unseen, poll=search.POLL):
            break
    log(f"powered up {done}, passed {passed}, {time.time() - t_start:.0f}s")
    go("close", "list")
    return done


def power_pile(query, limit):
    """power_walk for a pile about to be tagged Transfer. Running out of Stardust only ends the power-ups.
    -> False if --limit stopped it (the rest weren't checked: don't tag them yet)"""
    try:
        if power_walk(limit, query) is None:
            log(f"--limit {limit}: the rest of {query} weren't checked, so they aren't tagged Transfer")
            return False
    except Stop as e:
        if "Stardust" not in str(e):
            raise
        log(f"stopped powering up: {e}")
        if look()[0] != "list":
            go("close", "list")
    return True


def untraded(who):
    """the user's rules: an XXL one in Clean Trades, traded or not, is a favorite (2026-11-04). A never-traded one
    never gets Transfer (2026-10-31). xxs: renamed and tagged IVC (sizes.py). A trade evolution (not a shadow: it can't be traded): GIV, on HashTagAJay only (it goes
    to EVO_FOR, who wants the XP; HashTagAJay doesn't, 2026-11-02). Both drop out of Clean Trades (!#)"""
    import sizes  # (sizes imports this file)
    sizes.walk(lambda: run_shortcut(CLEAN, "&xxl&!favorite"), "xxl", 10 ** 9)
    for size in sizes.NAMES:
        sizes.walk(lambda: run_shortcut(CLEAN, f"&!traded&{size}"), size, 10 ** 9)
    if who != EVO_FOR:
        tag_pile(CLEAN, "GIV", f"&!traded&!shadow&!xxl&{TRADE_EVOS}")


def script(a):
    limit = session.limit(a)
    base.start()  # from anywhere, Pokémon GO closed too
    search.to_search_list()
    who = None if LOOK else account()
    if who != EVO_FOR and ("evo" in a or "fix" in a):
        raise Stop(f"signed in as {who!r}: only {EVO_FOR} tags free evolutions Evo")
    if LOOK:
        power_walk(limit)
        return
    if "evo" in a:  # steps 1 and 3: a PvpC/IVC one tagged Evo first would drop out of its shortcut (!#)
        for name, tag in TAGGING:
            tag_pile(name, tag)
        tag_pile(CLEAN, EVO, f"&!xxl&{TRADE_EVOS}")
        return
    if "transfer" in a:  # every Transfer one: the cheap jump to an XL tier before it's transferred
        power_pile(f"#{TRANSFER}", limit)
        return
    if "fix" in a:  # Transfer tags given before the Evo step: traded trade evolutions go Transfer -> Evo
        tag_pile(TRANSFER, EVO, off=[TRANSFER], query=f"#{TRANSFER}&traded&!xxl&{TRADE_EVOS}")
        return
    for name, tag in TAGGING:  # first: Clean Trades (!#) must only see what's left untagged after these
        tag_pile(name, tag)
    untraded(who)  # before the power-ups: these won't be transferred
    try:
        if power_walk(limit) is None:
            log(f"--limit {limit}: the rest weren't checked, so Clean Trades isn't tagged Transfer")
            return
    except Stop as e:
        if "Stardust" not in str(e):
            raise
        log(f"stopped powering up: {e}")
        if look()[0] != "list":
            go("close", "list")
    if who == EVO_FOR:
        tag_pile(CLEAN, EVO, f"&!xxl&{TRADE_EVOS}")  # first: these drop out of Clean Trades (!#)
    tag_pile(CLEAN, TRANSFER, "&!xxl")


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x not in ("--limit", "--look", "evo", "fix", "transfer") and not x.isdigit() for x in a):
        sys.exit(__doc__)
    LOOK = "--look" in a
    powerup.LOOK = LOOK  # power_up reads it there
    base.new_run_dir(os.path.join(HERE, "runs"))
    session.main(script, a)
