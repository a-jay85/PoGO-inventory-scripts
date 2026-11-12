#!/usr/bin/env python3
"""Evolve every free trade evolution tagged Evo, as fast as the game lets it. CyrillJan on the Pixel only: the Mac stays
free, and HashTagAJay doesn't need the XP.

  POGO_PHONE=android caffeinate -dimsu python3 evo.py [--limit N] [--dry-run] [--here] [--candy]

Signed in as HashTagAJay: it switches to CyrillJan first, and the phone stays on CyrillJan after. A Lucky Egg is up to
the user: switch first (pogo.py account CyrillJan), pop it, then run this.

The search is rules.EVO + evolve + traded + !xxl + rules.TRADE_EVOS (dex numbers), sorted by RECENT. An evolved one isn't one
of those numbers any more, so it drops out, and the top tile is the next one each time.

For each one: read the EVOLVE row, tap it, read YES, tap it, wait out the animation, X, the top tile. Only two looks: the
EVOLVE row moves with the page's rows, and YES moves with the box (0.60, 0.70, 0.74 seen, with NO right under it).
It stops rather than guesses:
- A cost on the EVOLVE row: this search should only find free ones, so no candy is spent unless --candy says so.
- No EVOLVE row: the list is empty, still shows an evolved one, or a tap was lost. It searches again once, then stops.
- Anything else in the way after the animation (a level-up, a medal) shows up as no EVOLVE row: the same new search, then
  a stop with a capture in the run folder.

--here starts from the Pokémon list on screen (a tag's list, your own search) as it is. It doesn't check the account.
--dry-run goes as far as the YES / NO box for the top one and taps NO. It still taps the phone.
Log in runs/<time>-android/log.txt.
"""
import argparse, os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture, look
import search, session, home, account
from taps import exact, press, settled_tiles, row_of
from tagsheet import search_exact
from rules import EVO, EVO_FOR, TRADE_EVOS

SEARCH = f"#{EVO}&evolve&traded&!xxl&{TRADE_EVOS}"  # an XXL one stays as it is (the user, 2026-11-05)
ANIMATION = 18.3  # YES to the evolved one's page: 18.2 s, every species (the user's run, 2026-11-05)
SETTLE = 0.4  # after a tap, for the page or box to stop moving: one look then is enough (each look is about 0.4 s)


def evolve_row(texts):
    """the detail page's EVOLVE button -> (box, cost). cost: the number on its row, 0 when none shows. None: no button
    (MEGA EVOLVE starts MEGA)"""
    btn = [t for t in texts if ui.norm(t[4]).startswith("EVOLVE") and t[1] > 0.4]
    if not btn:
        return None
    nums = [int(n) for t in row_of(texts, btn[0], past=False) for n in re.findall(r"\d+", t[4])]
    return btn[0], max(nums, default=0)


def box_key(texts):
    """the "want to evolve" box: where YES and NO are. None while it isn't there yet. A Power Up box has YES / NO too:
    never that one"""
    yes, no = exact(texts, "YES"), exact(texts, "NO")
    if len(yes) != 1 or len(no) != 1 or "WANT TO EVOLVE" not in ui.joined(texts):
        return None
    return round(yes[0][1], 2), round(no[0][1], 2)


def wait_box():
    """after the EVOLVE tap: the "want to evolve" box -> (texts, bounds). Its height changes (Karrablast's has a league
    warning), so YES is read once two looks agree on where it is, as mega.py does: a tap while the box grows can miss.
    Never wait_for here: it says NO to this box"""
    time.sleep(SETTLE)
    got, texts, bounds = base.steady(box_key, tries=30, gap=0.05)
    if got is None:
        keep_capture("nobox")
        raise Stop("no 'want to evolve' box after EVOLVE")
    return texts, bounds


def evolve_one(dry, candy):
    """on the page of one to evolve, or just tapped. -> the page's bounds, or None when it has no EVOLVE row. Its place
    moves with the page's rows (0.863 to 0.948), so it's read each time"""
    time.sleep(SETTLE)
    for _ in range(6):
        screen, texts, _, bounds = look()
        got = evolve_row(texts) if screen == "detail" else None
        if got:
            break
        time.sleep(0.05)
    else:
        return None
    name = ui.detail_info(texts)["name"]
    box, cost = got
    if cost and not candy:
        keep_capture("cost")
        raise Stop(f"{name}: its EVOLVE costs {cost}: this search should only find free ones (--candy spends it)")
    log(f"  {name}: EVOLVE at {box[1]:.3f}, {cost} candy")
    press(box, bounds)
    texts, bounds = wait_box()
    if dry:
        log(f"  DRY: {ui.summary(texts, 200)}")
        press(exact(texts, "NO")[0], bounds)
        return bounds
    press(exact(texts, "YES")[0], bounds)
    time.sleep(ANIMATION)
    return bounds


def script(limit, dry, here, candy):
    if not ui.ANDROID:
        raise Stop("evo.py is Pixel only: POGO_PHONE=android")
    if here:
        session.ready()
        if look()[0] == "detail":  # left open on one: its list is under it
            base.go("close", "list")
    else:
        who = home.trainer()
        if who != EVO_FOR:
            account.switch(EVO_FOR)
        base.start()
        search_exact(SEARCH)
        if not settled_tiles():
            log(f"nothing in {SEARCH}")
            return
        _, texts, _, bounds = look()
        log(f"{SEARCH}: {search.result_count(texts)} to evolve")
        search.sort_recent(bounds)
    screen, texts, _, bounds = look()
    if not ui.tiles(texts):
        keep_capture("nolist")
        raise Stop(f"no Pokémon list on screen ('{screen}')")
    spot = ui.tiles(texts)[0][2:]  # the top tile. It doesn't move while the list stays at the top
    base.go("tile 1", "detail")
    done, retried = 0, False
    t0 = time.time()
    while done < limit:
        page = evolve_one(dry, candy)
        if not page:
            if here:
                log("no EVOLVE row: the list on screen is done, or something's in the way")
                keep_capture("noevolve")
                break
            if retried:
                keep_capture("noevolve")
                raise Stop("the top tile has no EVOLVE row, after a new search too")
            log("  no EVOLVE row: searching again")  # the list is empty, didn't update, or a tap was lost
            retried = True
            if look()[0] != "list":
                base.go("close", "list")
            search_exact(SEARCH)
            if not settled_tiles():
                break
            base.go("tile 1", "detail")
            continue
        retried = False
        done += 1
        log(f"{done} done, {(time.time() - t0) / done:.1f}s each")
        if dry or done >= limit:
            break
        base.tap_x(page)  # no looks here: the next page's read checks it all, as the taps can do no harm
        time.sleep(0.45)
        base.click(*spot, page)
    log(f"done: {done} {'looked at' if dry else 'YES tapped'}")


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=10 ** 9, help="at most N evolutions this run")
    ap.add_argument("--dry-run", action="store_true", help="the top one, up to the YES / NO box, then NO")
    ap.add_argument("--candy", action="store_true", help="evolve the ones that cost candy too")
    ap.add_argument("--here", action="store_true", help="the list on screen: no account check, search or sort")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android")
    session.main(script, a.limit, a.dry_run, a.here, a.candy)


if __name__ == "__main__":
    main()
