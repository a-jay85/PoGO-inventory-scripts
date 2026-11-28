#!/usr/bin/env python3
"""Evolving the Pokémon whose detail page is open: read the EVOLVE row, tap it, read YES, tap it, wait out the
animation. /evo evolves a whole list with it, /ivc an xxs one along its line.

Only two looks: the EVOLVE row moves with the page's rows, and YES moves with the box (0.60, 0.70, 0.74 seen, with NO
right under it).
"""
import re, time

import ui
import base
import pokedb
from base import Stop, log, keep_capture, look
from taps import exact, press, yes_no, row_of

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
    return yes_no(texts, "WANT TO EVOLVE")


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
    row = lambda seen: evolve_row(seen[1]) if seen[0] == "detail" else None
    screen, texts, _, bounds = base.settle(look, row, timeout=None, gap=0.05, tries=6)  # 6 looks, 0.05 s apart
    got = row((screen, texts))
    if not got:
        return None
    info = ui.detail_info(texts)
    name = info["name"]
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
    # its weight, height and CP all change, and no look follows (speed): the old record goes, and the evolved one
    # is added the next time any script opens it
    pokedb.gone(base.who(info), "evolved")
    time.sleep(ANIMATION)
    return bounds


def evolved():
    """after evolve_one's YES: the evolved one's page, read once it holds still -> (info, texts). It becomes the
    opened one (base.OPENED), so the tags and name that follow check against it"""
    info, texts, _ = base.steady_detail()
    base.OPENED["who"] = base.who(info)
    for k in ("page", "top"):  # (its candy count changed)
        base.OPENED.pop(k, None)
    return info, texts
