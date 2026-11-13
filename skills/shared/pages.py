#!/usr/bin/env python3
"""Whole screens that belong to one script, and the way out of each, for every other script. /trade's lobby left up,
/gift's gift list, /gymfeed's gym: whichever script runs next gets out the way the owner does.

Each screen's reader lives here, and its owner's own classify calls it, so there is one copy of each. The way out is
the tap its owner already uses to leave it. home.unstick (every script's step out of a screen it doesn't know) tries
popups.py, then these, then Back (Android) or opening the game again (iPhone). A script's own screens never get here:
its own classify knows them first.

Only taps that leave: X, the trade's exit door, NO, CANCEL, the YES on "cancel this trade?", RECENT in the trade's
sort menu, CAN RECEIVE A GIFT in the gift sort menu. Never CONFIRM, never the trade warning's YES, never BATTLE.
No trade can be live on the phone: /trade holds the phone's lock (session.ready) for its whole run.

Not here: /dex's pages (Pixel only: Back leaves them), the account switch's screens (Back, and never near SIGN OUT),
the gym's berry menu (Back).

  python3 pages.py <png>...     which page each screenshot shows, and where its way out would tap (nothing is tapped)
"""
import re, sys, time

import ui
import base

EXIT_DOOR = (0.09, 0.115)  # the trade's exit door, top left: leave the trade
GYM_SORT_BUTTON = (0.85, 0.93)  # the gym badge list's sort button, bottom right; its menu's X sits in the same spot
CP_RE = re.compile(r"^\W*[cC][pP]\s*\d{2,4}\W*$")
# '0d 3h 7m' on a gym Pokémon's page. OCR reads any 0 as O: 'Od 3h 7m.', 'Od 12h Om'
DEFEND_RE = re.compile(r"\b[0-9O]+d\s*[0-9O]+h\s*[0-9O]+m")
AGAIN_WINDOW, MAX_AGAIN = 60, 6  # the same page left this many times within this many seconds: the way out doesn't work
left = {}  # page name -> the times it was left lately


def words(texts):
    return {ui.norm(t[4]) for t in texts}


def label(texts, word):
    return next((t for t in texts if ui.norm(t[4]) == word), None)


def center(t):
    return t[0] + t[2] / 2, t[1] + t[3] / 2


# ---------- /trade's screens ----------

def trade_leave(texts):
    """'Do you want to cancel this trade?' after the exit door: YES / NO"""
    return "CANCEL THIS TRADE" in ui.joined(texts)


def trade_warning(texts):
    """'Are you sure you want to trade?' before the confirm screen"""
    return "ARE YOU SURE YOU WANT TO TRADE" in ui.joined(texts)


def confirm_label(texts):
    """the trade's CONFIRM button (CANCEL once tapped), left of the middle"""
    for t in texts:
        if t[0] < 0.3 and 0.45 < t[1] < 0.6 and ui.norm(t[4]) in ("CONFIRM", "CANCEL"):
            return t
    return None


def trade_confirm(texts):
    # one stray letter after KM is OCR's: the Pixel read '4,083.8 kml' (2026-11-13: /trade stopped, 'screen is lobby')
    return bool(confirm_label(texts)) and any(re.search(r"\d\s*KM[A-Z|]?$", ui.up(t)) for t in texts)


def trade_sortmenu(texts):
    """the trade picker's sort menu"""
    w = words(texts)
    return "RECENT" in w and any(x.startswith("COMBAT POWER") for x in w)


def trade_waiting(texts):
    j = ui.joined(texts)
    return "WAITING FOR" in j and "TRADING" in j


def trade_lobby(texts):
    """in the trade, nothing picked: "Waiting for ... to select their Pokémon", picker button below"""
    return bool(re.search(r"\bME LV", ui.joined(texts)))


def trade_picker(texts):
    """the trade's Pokémon list: only a POKÉMON header (storage has TAGS and EGGS tabs beside it). The SPECIAL TRADES
    REMAINING line shows only while no search is on: the picker keeps the last search between trades. A pile search can
    leave fewer than 3 tiles, or none: then the distance search in the bar vouches for it. (The iPhone can read the
    header POKÉMONI)"""
    raw, w, j = [ui.up(t) for t in texts], words(texts), ui.joined(texts)
    return "SPECIAL TRADES REMAINING" in j or bool(w & {"POKMON", "POKMONI"}) and not w & {"TAGS", "EGGS"} and (
        sum(bool(re.fullmatch(r"CP\s*\d+", r.replace("С", "C"))) for r in raw) >= 3 or "FAVORITE" in w
        or "DISTANCE" in j or "COUNTCANDY" in j)


def trade_select(texts):
    """a Pokémon picked in the trade, NEXT under it"""
    return "NEXT" in words(texts) and any(re.search(r"CP\s*\d+\s*>", ui.up(t)) for t in texts)


def trade_detail(texts):
    """a Pokémon's info over the confirm screen (its card tapped): CP 434 > CP 407 - 509, no NEXT"""
    return any(re.search(r"CP\s*\d+\s*>\s*CP\s*\d+\s*-\s*\d+", ui.up(t)) for t in texts)


def trade_result(texts):
    """after a trade: the Pokémon that came, with its STARDUST and candy"""
    w = words(texts)
    return "STARDUST" in w and ("POWER UP" in w or any("CANDY" in x for x in w))


def trade_gift(texts):
    """a friend's gift box over their page, as /trade reads it"""
    w, j = words(texts), ui.joined(texts)
    return "OPEN" in w and ("GREETINGS FROM" in j or "SENT" in j)


# ---------- /gift's screens ----------

def gift_picker(texts):
    return "WHICH GIFT" in ui.joined(texts)


def gift_preview(texts):
    return "ADD STICKER" in ui.joined(texts) and "SEND" in words(texts)


def gift_popup(texts):
    """(a long title cuts the line short: 'Greetings fro..', crecos1's Yacht Club gift, 2026-11-07)"""
    return "GREETINGS FRO" in ui.joined(texts) and "OPEN" in words(texts)


def lucky_trade(texts):
    """a friend's Lucky Trade request over their page: its X shows the page"""
    return "REVIEW LUCKY" in ui.joined(texts)


def raid(texts):
    """a raid's gym screen (2026-10-27: a friend-row tap opened one). Its X leaves; never BATTLE"""
    return "REMOTE RAID PASS" in ui.joined(texts) and "BATTLE" in words(texts)


def buddy(texts):
    """the buddy's history page (a stray tap on the ME tab's buddy): its X goes back"""
    return "TOTAL DAYS SPENT TOGETHER" in ui.joined(texts)


def trainer_code(texts):
    """(a tap on our own picture in the friend list)"""
    j = ui.joined(texts)
    return "TRAINER CODE" in j and "2D CODE" in j


def gift_list_scrolled(texts):
    """the gift list scrolled past its header: two columns of city lines ('Chicago, IL, United States'). (Letters: the
    profile's ME tab has two columns of numbers like '145,619,768')"""
    cities = [t for t in texts if t[1] > 0.12 and t[4].count(",") >= 1 and len(t[4]) > 8
              and re.search(r"[^\W\d_]{3}", t[4])]
    return "SEND GIFT" not in ui.joined(texts) and {t[0] < 0.4 for t in cities} == {True, False} and len(cities) >= 3


def gift_sortmenu(texts):
    j = ui.joined(texts)
    return "CAN RECEIVE A GIFT" in j and "FRIENDSHIP LEVEL" in j


def ribbon(texts):
    """a friend's level ribbon on the friendship meter -> GOOD / GREAT / ULTRA / BEST / FOREVER, or None"""
    for t in texts:
        m = re.fullmatch(r"(GOOD|GREAT|ULTRA|BEST|FOREVER) FRIEND", ui.up(t))
        if m and 0.2 < t[1] < 0.36:
            return m.group(1)
    return None


def friend_page(texts):
    """a friend's page: SEND GIFT, LOCAL / REMOTE TRADE, BATTLE. Its X goes back to the Friends tab. A trade's late
    'expired' box lands here after its OK, over any script (2026-11-08: /cleantrades stopped on it)"""
    return "SEND GIFT" in ui.joined(texts)


def friend_meter(texts):
    """a friend's friendship meter (a tap on their hearts)"""
    return "BONUS" in words(texts) or "MORE FRIENDSHIP POINT" in ui.joined(texts) or bool(ribbon(texts))


# ---------- /gymfeed's screens ----------

def gym_sortmenu(texts):
    w = words(texts)
    return "DEFENDING" in w and any(x.startswith("NAME") for x in w) and "RECENT" in w


def gym_badge(texts):
    j = ui.joined(texts)
    return "TIME DEFENDING" in j or "TOTAL GYM ACTIVITY" in j


def gym_badgelist(texts):
    return any(ui.norm(t[4]) == "GYM BADGES" and t[1] < 0.15 for t in texts)


def gym_feed(texts):
    """a gym defender's page, its defending time at the top"""
    return any(DEFEND_RE.search(t[4]) and t[1] < 0.22 for t in texts)


def gym_view(texts):
    """inside a gym: CP labels over its Pokémon, the gym's name across the top"""
    return any(CP_RE.match(t[4].strip()) and 0.3 < t[1] < 0.66 for t in texts) \
        and any(t[1] < 0.18 and t[2] > 0.15 for t in texts if not CP_RE.match(t[4]))


def gym_view_alone(texts):
    """a gym, for the other scripts: a Pokémon list's CP labels look the same, and a gym never has a search bar"""
    return gym_view(texts) and not any("SEARCH" in ui.up(t) for t in texts)


# ---------- the ways out ----------
# each: texts -> (fx, fy) to tap, or None when it can't be left from here (then Back / reopen, as before)

def x_button(texts):
    return base.X_BUTTON


def leave_trade_yes(texts):
    t = label(texts, "YES")
    return center(t) if t else None


def warning_no(texts):
    t = label(texts, "NO")  # (its YES goes on to the confirm screen: never tapped here)
    return center(t) if t else None


def confirm_out(texts):
    """takes back a CONFIRM that landed (CANCEL), else the exit door. (Change Pokémon went back to the list, and the
    list's X back to this screen while the pick stood: the two went round for minutes)"""
    t = confirm_label(texts)
    return center(t) if t and ui.norm(t[4]) == "CANCEL" else EXIT_DOOR


def recent(texts):
    t = label(texts, "RECENT")
    return center(t) if t else None


def can_receive(texts):
    """the gift sort menu's row (OCR can glue its round pick button on: 'OCAN RECEIVE A GIFT')"""
    t = next((t for t in texts if re.fullmatch(r"[OQCD]? ?CAN RECEIVE A GIFT", ui.norm(t[4]))), None)
    return center(t) if t else None


# order: the more particular first (a trade's warning and confirm screens show a Pokémon's CP too)
PAGES = (
    ("trade: cancel this trade?", trade_leave, leave_trade_yes),
    ("trade: are you sure?", trade_warning, warning_no),
    ("trade: confirm", trade_confirm, confirm_out),
    ("trade: sort menu", trade_sortmenu, recent),
    ("trade: waiting", trade_waiting, lambda texts: EXIT_DOOR),
    ("trade: lobby", trade_lobby, lambda texts: EXIT_DOOR),
    ("trade: Pokémon list", trade_picker, x_button),
    ("trade: picked", trade_select, x_button),
    ("trade: Pokémon info", trade_detail, x_button),
    ("trade: result", trade_result, x_button),
    ("gift: gift list", gift_picker, x_button),
    ("gift: preview", gift_preview, x_button),
    ("gift: gift box", gift_popup, x_button),
    ("trade: gift box", trade_gift, x_button),
    ("gift: Lucky Trade request", lucky_trade, x_button),
    ("gift: raid", raid, x_button),
    ("gift: buddy history", buddy, x_button),
    ("gift: trainer code", trainer_code, x_button),
    ("gift: gift list (scrolled)", gift_list_scrolled, x_button),
    ("gift: sort menu", gift_sortmenu, can_receive),
    ("gift: friend page", friend_page, x_button),
    ("gift: friendship meter", friend_meter, x_button),
    ("gymfeed: sort menu", gym_sortmenu, lambda texts: GYM_SORT_BUTTON),
    ("gymfeed: badge", gym_badge, x_button),
    ("gymfeed: badge list", gym_badgelist, x_button),
    ("gymfeed: defender", gym_feed, x_button),
    ("gymfeed: gym", gym_view_alone, x_button),
)


def which(texts):
    """the page on this screen -> (name, (fx, fy)), or None. (fx, fy) is None when it's known but has no way out here"""
    for name, test, out in PAGES:
        if test(texts):
            return name, out(texts)
    return None


def step_out(texts, bounds):
    """one tap out of another script's page, if this is one. -> its name, or None. Raises Stop when the same page
    keeps coming back"""
    got = which(texts)
    if not got or not got[1]:
        return None
    name, (fx, fy) = got
    now = time.time()
    recent_ = left[name] = [t for t in left.get(name, []) if now - t < AGAIN_WINDOW] + [now]
    if len(recent_) > MAX_AGAIN:
        base.keep_capture("page")
        raise base.Stop(f"left the {name} page {MAX_AGAIN} times in {AGAIN_WINDOW}s and it keeps coming back: "
                        f"{ui.summary(texts, 120)}")
    base.log(f"  on another script's page ({name}): its way out")
    base.click(fx, fy, bounds, fuzz=0.004)
    time.sleep(1.5)
    return name


if __name__ == "__main__":
    for png in sys.argv[1:]:
        got = which(ui.ocr(png))
        print(f"{png}: " + (f"{got[0]} -> {got[1]}" if got else "no page"))
