#!/usr/bin/env python3
"""Evolve every free trade evolution tagged Evo, as fast as the game lets it. CyrillJan on the Pixel only: the Mac stays
free, and HashTagAJay doesn't need the XP.

  POGO_PHONE=android caffeinate -dimsu python3 evo.py [--limit N] [--dry-run]

Signed in as HashTagAJay: it switches to CyrillJan first, and the phone stays on CyrillJan after. A Lucky Egg is up to
the user: switch first (pogo.py account CyrillJan), pop it, then run this.

The search is rules.EVO + evolve + traded + !xxl + rules.TRADE_EVOS (dex numbers), sorted by RECENT. An evolved one isn't one
of those numbers any more, so it drops out, and the top tile is the next one each time.

For each one: open the top tile, read the EVOLVE row, tap it, YES, wait for the animation, back to the list.
It stops rather than guesses:
- A cost on the EVOLVE row: this search should only find free ones, so no candy is ever spent.
- No EVOLVE row: the list still shows an evolved one. It searches again once, then stops.
- A screen it doesn't know after the animation (keeps a capture in the run folder).

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
from taps import exact, press, reopen_top, settled_tiles
from tagsheet import search_exact
from rules import EVO, EVO_FOR, TRADE_EVOS

SEARCH = f"#{EVO}&evolve&traded&!xxl&{TRADE_EVOS}"  # an XXL one stays as it is (the user, 2026-11-05)
EVOLVE_WAIT = 45  # seconds from YES to the evolved one's page


def evolve_row(texts):
    """the detail page's EVOLVE button -> (box, cost). cost: the number on its row, 0 when none shows. None: no button
    (MEGA EVOLVE starts MEGA)"""
    btn = [t for t in texts if ui.norm(t[4]).startswith("EVOLVE") and t[1] > 0.4]
    if not btn:
        return None
    b = btn[0]
    row = [t for t in texts if abs((t[1] + t[3] / 2) - (b[1] + b[3] / 2)) < 0.015 and t[0] >= b[0]]
    nums = [int(n) for t in row for n in re.findall(r"\d+", t[4])]
    return b, max(nums, default=0)


def wait_box():
    """after the EVOLVE tap: the YES / NO box -> (texts, bounds). Never wait_for here: it says NO to this box"""
    for _ in range(30):
        time.sleep(0.1)
        _, texts, _, bounds = look()
        if len(exact(texts, "YES")) == 1 and len(exact(texts, "NO")) == 1:
            return texts, bounds
    keep_capture("nobox")
    raise Stop("no YES / NO box after EVOLVE")


def wait_evolved(name):
    """after YES: the page of the evolved one, which has no EVOLVE row. Logs each new kind of screen on the way"""
    t0, end, seen = time.time(), time.time() + EVOLVE_WAIT, None
    while time.time() < end:
        time.sleep(0.1)
        try:
            screen, texts, _, bounds = look()
        except ui.Refused:
            continue
        if screen != seen:
            seen = screen
            log(f"  {time.time() - t0:.1f}s: {screen}: {ui.summary(texts, 80)}")
        if screen == "detail" and not evolve_row(texts) and any(ui.norm(t[4]).startswith("POWER UP") for t in texts):
            log(f"  {name}: evolved in {time.time() - t0:.1f}s")
            return
    keep_capture("afterevolve")
    raise Stop(f"{name}: no evolved page {EVOLVE_WAIT} s after YES, last screen {seen}: check by hand")


def evolve_one(dry):
    """on the page of one to evolve. -> False when it has no EVOLVE row"""
    for _ in range(10):  # the page slides in
        screen, texts, _, bounds = look()
        got = evolve_row(texts) if screen == "detail" else None
        if got:
            break
        time.sleep(0.1)
    else:
        return False
    name = ui.detail_info(texts)["name"]
    box, cost = got
    if cost:
        keep_capture("cost")
        raise Stop(f"{name}: its EVOLVE costs {cost}: this search should only find free ones")
    press(box, bounds)
    texts, bounds = wait_box()
    if dry:
        log(f"  DRY: {ui.summary(texts, 200)}")
        press(exact(texts, "NO")[0], bounds)
        return True
    press(exact(texts, "YES")[0], bounds)
    wait_evolved(name)
    return True


def script(limit, dry):
    if not ui.ANDROID:
        raise Stop("evo.py is Pixel only: POGO_PHONE=android")
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
    search.sort_by("RECENT", bounds)
    base.go("tile 1", "detail")
    done, retried = 0, False
    t0 = time.time()
    while done < limit:
        if not evolve_one(dry):
            if retried:
                keep_capture("noevolve")
                raise Stop("the top tile has no EVOLVE row, after a new search too")
            log("  no EVOLVE row: the list didn't update. Searching again")
            retried = True
            base.go("close", "list")
            search_exact(SEARCH)
            if not settled_tiles():
                break
            base.go("tile 1", "detail")
            continue
        retried = False
        done += 1
        log(f"{done} done, {(time.time() - t0) / done:.1f}s each")
        if dry or done >= limit or not reopen_top():
            break
    log(f"done: {done} {'looked at' if dry else 'evolved'}")


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=10 ** 9, help="at most N evolutions this run")
    ap.add_argument("--dry-run", action="store_true", help="the top one, up to the YES / NO box, then NO")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android")
    session.main(script, a.limit, a.dry_run)


if __name__ == "__main__":
    main()
