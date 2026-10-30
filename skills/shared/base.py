#!/usr/bin/env python3
"""The shared tapper: screen reading, taps, timing, run folders and logging, and the detail-screen steps (appraise,
tags, star, rename, Nope) every skill's script uses. One copy in memory per run: scripts `import base`, so all of
them share one RUN_DIR and one last_tap. /pvpc's own walk is ../pvpc/run.py.
"""
import contextlib, json, math, os, random, re, shutil, subprocess, sys, time
from collections import Counter

import ui, pvp
from ui import Refused, Moving

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(os.path.dirname(HERE), "pvpc", "runs")  # where a run that doesn't pick its own folder logs
RUN_DIR = os.path.join(RUNS, time.strftime("%Y%m%d-%H%M%S"))
ALWAYS_KEEP = 44  # IV sum of 98%: 98% and 100% (a shadow: once purified) never get Nope, traded or transferred


class Stop(Exception):
    """something unexpected: stop the whole run"""


class Skip(Exception):
    """not sure about this one: leave it for a human"""


GYM = "in a gym"  # the Skip for a Pokémon defending a gym: not counted toward MAX_SKIPS_IN_A_ROW


class Lost(Stop):
    """the screen isn't the one expected (a tap didn't land, or landed late). Mid-Pokémon, a walk can back out
    with recover() and go on; anywhere else it stops the run like any Stop"""


MAX_LOST = 15  # backed out this many times in one run: something's really off, stop (the 10-07 run had ~8)
lost = 0


@contextlib.contextmanager
def changing(what):
    """something on this Pokémon may have changed already: a lost screen from here on stops the run"""
    try:
        yield
    except Lost as e:
        raise Stop(f"{e} (while {what})") from e


# ---------- logging ----------

def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "log.txt"), "a") as f:
        f.write(line + "\n")


def keep_capture(tag):
    """copy the latest window capture into the run folder"""
    if os.path.exists(ui.CAP):
        os.makedirs(RUN_DIR, exist_ok=True)
        dst = os.path.join(RUN_DIR, f"{time.strftime('%H%M%S')}-{re.sub(r'[^A-Za-z0-9]+', '_', tag)}.png")
        shutil.copy(ui.CAP, dst)
        return dst


def new_run_dir(runs, d=None, suffix=""):
    """a new run folder in runs, named by the time (and suffix), or d if given"""
    global RUN_DIR
    if d:
        RUN_DIR = d
        os.makedirs(RUN_DIR, exist_ok=True)
        return RUN_DIR
    os.makedirs(runs, exist_ok=True)
    while True:  # the other phone's run may have started this same second: never share its folder
        RUN_DIR = os.path.join(runs, time.strftime("%Y%m%d-%H%M%S") + (f"-{suffix}" if suffix else ""))
        try:
            os.mkdir(RUN_DIR)
            return RUN_DIR
        except FileExistsError:
            time.sleep(1)


def newest(folder, pattern):
    """the newest file matching folder/pattern (dated names sort by date), or None"""
    import glob
    got = sorted(glob.glob(os.path.join(folder, pattern)))
    return got[-1] if got else None


def save(name, data):
    with open(os.path.join(RUN_DIR, name), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def load(name, default=None):
    path = os.path.join(RUN_DIR, name)
    if default is not None and not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


# ---------- human-ish timing ----------

# quick taps, as /ivcsort had them: 0.1-0.25s since the last one (screen reading counts toward it).
# The pause that looks like a person working something out is think(), on the appraisal only.
last_tap = 0.0
USER_IDLE = 10  # front() waits this long after the user's last key or click before taking the screen back


def tap_gap():
    """wait until a short random gap has passed since the last tap"""
    time.sleep(max(0.0, last_tap + random.uniform(0.1, 0.25) - time.time()))


def think():
    """on the appraisal: a short pause, like a glance at the bars (it was 2.5-5.5s, ~4.4s a Pokémon)"""
    time.sleep(random.uniform(0.7, 1.3))


# ---------- screen ----------

def look(where=None, remember=True):
    """capture and OCR the screen. -> (screen, texts, path, bounds). where(path, texts): the screen's name (default
    ui.classify, the storage screens; home.where and dex.where know more). remember: keep it for ui.plan() (/gift
    never taps a named button, so it skips that). Each look's capture and OCR seconds go to RUN_DIR/steps.txt"""
    t0 = time.time()
    path, bounds = ui.capture()
    t1 = time.time()
    texts = ui.ocr(path)
    if remember:
        ui.remember(path, texts, bounds)
    screen = where(path, texts) if where else ui.classify(texts)
    step(t0, t1, screen)
    return screen, texts, path, bounds


def step(t0, t1, screen):
    """one line in steps.txt: when, who looked, the screen, capture and OCR (+ classify) seconds, to see where a
    run's time goes. Only once the run folder is there (a log line or new_run_dir made it): a read-only look makes
    no folder"""
    if not os.path.isdir(RUN_DIR):
        return
    f = sys._getframe(2)  # step <- look <- the caller, past wrapping look()s and wait_for (it names who waited)
    while f.f_back and f.f_code.co_name in ("look", "<lambda>", "wait_for"):
        f = f.f_back
    with open(os.path.join(RUN_DIR, "steps.txt"), "a") as out:
        out.write(f"{time.strftime('%H:%M:%S', time.localtime(t0))}.{int(t0 % 1 * 10)} {f.f_code.co_name:12} {screen:10} "
                  f"cap {t1 - t0:.1f} ocr {time.time() - t1:.1f}\n")


def poll_gap(ios):
    """the pause between two looks while waiting for the screen. Android: none, a look itself takes ~0.35 s and
    waiting more saved nothing (search.POLL, measured 2026-10-23). ios: the iPhone's pause, as it always was"""
    return 0.0 if ui.ANDROID else ios


LOOK_S = 0.35  # about how long one Android look takes (capture + OCR)


def tries(n, ios):
    """the turns of a wait loop that reads the screen each turn. iPhone: n turns, ios seconds apart, the pause first
    (as it always was). Android: no pause, as many turns as fit in the time the n took there, n * (ios + LOOK_S),
    so a slow screen gets as long as before. Only for loops that just read until the screen is right (the turn
    number isn't used, and a turn never taps)"""
    if not ui.ANDROID:
        for i in range(n):
            time.sleep(ios)
            yield i
        return
    end, i = time.time() + n * (ios + LOOK_S), 0
    while i == 0 or time.time() < end:
        yield i
        i += 1


SIZE_CARD = (95, 206, 250)  # the card's sky blue


def size_record(path):
    """a 'New Size Record' card: it slides up over a Pokémon's detail page the first time it's opened after the
    record, and covers the bottom third. Its words fade in after it lands, so it's told by its blue: a row of it,
    edge to edge, where the detail page is white"""
    im = ui.Image.open(path).convert("RGB")
    W, H = im.size
    return all(sum(abs(a - b) for a, b in zip(im.getpixel((int(fx * W), int(0.78 * H))), SIZE_CARD)) < 30
               for fx in (0.05, 0.3, 0.5, 0.7, 0.95))


def size_title(texts):
    return next((t for t in texts if ui.norm(t[4]).startswith("NEW SIZE RECORD")), None)


def close_size_record(texts, path, bounds):
    """tap the card's own X, a pale circle at the bottom centre, under its height and weight lines. It sits about
    where the detail page's X does, so it's found on the picture, never guessed"""
    title = size_title(texts)
    low = max(t[1] + t[3] for t in texts if t[1] > title[1])  # the bottom of the card's last line (the weight)
    im = ui.Image.open(path).convert("RGB")
    W, H = im.size
    x, y0 = W // 2, int((low + 0.02) * H)
    bg = im.getpixel((x, y0))  # the card's blue
    ys = [y for y in range(y0, H) if sum(abs(a - b) for a, b in zip(im.getpixel((x, y)), bg)) > 60]
    ys = [y for i, y in enumerate(ys) if all(b - a < 0.01 * H for a, b in zip(ys[:i], ys[1:i + 1]))]  # the circle only
    if not ys or not 0.02 * H < ys[-1] - ys[0] < 0.12 * H:
        keep_capture("size_record")
        raise Lost("a New Size Record card is up and its X isn't where it should be")
    log("  a New Size Record card is up: closing it")
    click(0.5, (ys[0] + ys[-1]) / 2 / H, bounds)


def wait_for(*screens, timeout=10, capture=True, look=None, poll=None, catch=True, detail=False):
    """poll until one of the screens shows up. Brief unknown screens (animations) are fine. It always looks at least
    once, and once more after the time is up, then raises Lost.
    look: () -> (screen, texts, path, bounds) (default run.look). poll: seconds between looks (default poll_gap(0.12)).
    catch: a Refused look (window gone for a moment) is waited out; False: it's raised. capture: keep a capture
    when it gives up. detail: the error has the last screen's text even when it's a known screen"""
    see = look or globals()["look"]
    pause = poll_gap(0.12) if poll is None else poll
    end, last, nudges, cards, nos = time.time() + timeout, "?", 0, 0, 0
    while True:
        try:
            screen, texts, path, bounds = see()
        except Refused as e:  # window gone for a moment
            if not catch:
                raise
            last = str(e)
        else:
            if screen == "detail" and cards < 10 and size_record(path):
                cards += 1  # a "New Size Record" card slid up over the detail: it hides the candy and the X
                if size_title(texts):
                    close_size_record(texts, path, bounds)
                else:
                    time.sleep(0.3)  # still blank: its words and X are fading in
                end = max(end, time.time() + 3)
                continue
            if screen in screens:
                return screen, texts, path, bounds
            no = [t for t in texts if ui.up(t) == "NO"]
            if screen == "unknown" and no and nos < 2 and "WANT TO EVOLVE" in ui.joined(texts):
                nos += 1  # a late tap (the iPhone has sat on one ~4s) landed on EVOLVE: never evolve, say NO
                log("  an 'evolve?' box came up: NO")
                click(no[0][0] + no[0][2] / 2, no[0][1] + no[0][3] / 2, bounds)
                time.sleep(1.0)
                end = max(end, time.time() + 3)
                continue
            last = screen
            words = {ui.norm(t[4]) for t in texts}
            if "detail" in screens and screen == "unknown" and "STARDUST" in words and \
                    words & {"WEIGHT", "HEIGHT", "POWER UP"} and nudges < 3:
                nudges += 1  # a detail page left scrolled down (the HP line is off the top): pull it back up
                scroll(bounds, "drag", up=True)
                end = max(end, time.time() + 3)
                continue
            if screen == "unknown" or detail:
                last += ": " + ui.summary(texts, 200)
        if time.time() >= end:
            break
        time.sleep(pause)
    if capture:
        keep_capture("stuck")
    raise Lost(f"wanted {screens}, screen is {last}")


def idle_seconds():
    """seconds since the last real keyboard/mouse input on the Mac"""
    out = subprocess.run(["ioreg", "-c", "IOHIDSystem", "-d", "4"], capture_output=True, text=True).stdout
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    return int(m.group(1)) / 1e9 if m else 999


def front():
    """bring iPhone Mirroring forward. If the user switched to another app, wait until they've left the Mac
    alone for USER_IDLE seconds first, so their typing doesn't land on the phone.
    Android: adb never touches the Mac's mouse or keyboard, so just check the phone (and unlock it if it locked
    itself mid-run)."""
    if ui.ANDROID:
        try:
            return ui.android.ready()
        except ui.android.NotReady as e:
            if not session.locked():
                raise Stop(str(e))
        session.unlock()
        try:
            return ui.android.ready(force=True)
        except ui.android.NotReady as e:
            raise Stop(str(e))
    if ui.sh(ui.HELPER, "front").strip() != "iPhone Mirroring" and idle_seconds() < USER_IDLE:
        log(f"you're using the Mac: waiting until it's been idle {USER_IDLE}s")
        while idle_seconds() < USER_IDLE:
            time.sleep(1)
    for _ in range(3):  # the first open sometimes loses to whatever app had focus
        if ui.sh(ui.HELPER, "front").strip() == "iPhone Mirroring":
            return
        subprocess.run(["open", "-a", "iPhone Mirroring"])
        time.sleep(1.5)
    if ui.sh(ui.HELPER, "front").strip() != "iPhone Mirroring":
        raise Stop("can't bring iPhone Mirroring to the front")


def to_points(fx, fy, bounds):
    x, y, w, h = bounds
    return x + fx * w, y + fy * h


TAP_WOBBLE = 0.002  # every tap lands up to this far off (x; half in y), under the tightest fuzz (0.004, gift's X)


def click(fx, fy, bounds, gap=0.0, ms=None, fuzz=0.0, rest=0.0, bring_front=True, spaced=True, counted=True):
    """a tap at a spot (window fractions), not a named button: every skill's taps go through here.
    gap: at least this long since the last tap (two quick taps on the search bar would make a double-tap).
    ms: how long it holds (default ui.tap_ms(); 900 is a long press). fuzz: up to this much off in x, half that in y,
    on top of TAP_WOBBLE, which every tap gets so no two land on the same pixel.
    rest: seconds to wait after it, or a (lo, hi) range.
    bring_front: front() first (iPhone: a click while another app is in front only brings the window forward, and
    is lost). spaced: wait out tap_gap() and gap first. counted: it counts as the last tap for the next one's gap."""
    global last_tap
    if bring_front:
        front()
    fuzz = max(fuzz, TAP_WOBBLE)
    x, y = to_points(fx + random.uniform(-fuzz, fuzz), fy + random.uniform(-fuzz / 2, fuzz / 2), bounds)
    if spaced:
        tap_gap()
        time.sleep(max(0.0, last_tap + gap - time.time()))
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(ui.tap_ms() if ms is None else ms))
    if counted:
        last_tap = time.time()
    rest = random.uniform(*rest) if isinstance(rest, tuple) else rest
    if rest:
        time.sleep(rest)


def tap_box(t, bounds, dy=0.0, spread=0.0, **kw):
    """click() an OCR box (x, y, w, h, text): its middle (dy lower), or with spread anywhere within that much of the
    middle (0.15: 35-65% across and down). kw: click()'s"""
    fx = t[0] + t[2] * (random.uniform(0.5 - spread, 0.5 + spread) if spread else 0.5)
    fy = t[1] + t[3] * (random.uniform(0.5 - spread, 0.5 + spread) if spread else 0.5) + dy
    click(fx, fy, bounds, **kw)


def tap(target, dry=False):
    for _ in range(8):
        front()
        try:
            fx, fy, bounds, screen = ui.plan(target)
        except Moving:
            time.sleep(0.15)
            continue
        except Refused as e:
            if ("screen is 'unknown'" in str(e) or "found 0 matches" in str(e)) and _ < 7:  # caught mid-animation (a menu still opening)
                ui._seen = ui._older = None  # that look was mid-animation: don't reuse it
                time.sleep(0.4)
                continue
            keep_capture("refused")
            if "never-tap" in str(e):
                raise Stop(f"tap {target}: {e}")
            raise Lost(f"tap {target}: {e}")  # not there, or not on this screen
        if dry:
            px, py = to_points(fx, fy, bounds)
            log(f"DRY tap {target} on {screen} at {px:.0f},{py:.0f}")
            return
        click(fx, fy, bounds, bring_front=False)  # (front() ran at the top of this try)
        return
    raise Stop(f"tap {target}: screen never stopped moving")


def go(target, *screens):
    """a tap that moves to another screen: if it doesn't land, tap again (never used for tick boxes)"""
    for attempt in range(3):
        try:
            tap(target)
        except Stop:
            if not attempt:
                raise
            break  # button's gone: the last tap did land, the screen is just slow
        try:
            return wait_for(*screens, timeout=4, capture=False)
        except Stop:
            if ui.ANDROID:  # (POGO_SCRCPY=1) scrcpy's picture can lag or stall: check the phone's own screen before tapping again
                stuck = ui.android.fresh()
                try:
                    return wait_for(*screens, timeout=4, capture=False)
                except Stop:
                    if stuck:
                        raise Stop(f"tap {target}: scrcpy's picture was stuck, not sure where the phone is")
            if ui.ANDROID:  # a tap read as a long press: the list is in multi-select and won't open tiles
                path, bounds = ui.capture()
                if search.leave_multiselect(ui.ocr(path), bounds):
                    continue
            log(f"  tap {target} didn't land, again")
    return wait_for(*screens)


def key(name, cmd=False):
    front()
    ui.sh(ui.HELPER, "key", name, *(["cmd"] if cmd else []))
    time.sleep(random.uniform(0.08, 0.18))


def type_text(text):
    front()
    ui.sh(ui.HELPER, "type", text, "35", "80")
    time.sleep(random.uniform(0.1, 0.25))


def paste_text(text):
    """iPhone: the whole text in one cmd+V (Mirroring passes the Mac's clipboard to the phone), not a key at a time.
    -> what the Mac's clipboard held before: give it to restore_clipboard() once the text has landed (the phone
    can fetch the clipboard a moment after the cmd+V)"""
    front()
    old = subprocess.run(["pbpaste"], capture_output=True).stdout
    subprocess.run(["pbcopy"], input=text.encode())
    ui.sh(ui.HELPER, "key", "v", "cmd")
    time.sleep(random.uniform(0.1, 0.25))
    return old


def restore_clipboard(old):
    subprocess.run(["pbcopy"], input=old)


def scroll(bounds, how, up=False):
    """one screenful-ish down (or up) the list, from a random spot in the middle of the window"""
    front()
    fx, fy = random.uniform(0.3, 0.7), random.uniform(0.3, 0.45) if up else random.uniform(0.55, 0.7)
    x, y = to_points(fx, fy, bounds)
    dist = bounds[3] * random.uniform(0.3, 0.42) * (-1 if up else 1)
    if how == "wheel":
        ui.sh(ui.HELPER, "scroll", f"{x:.1f}", f"{y:.1f}", str(-int(dist)), str(random.randint(8, 16)))
    else:
        ui.sh(ui.HELPER, "drag", f"{x:.1f}", f"{y:.1f}", f"{x + random.uniform(-8, 8):.1f}", f"{y - dist:.1f}",
              str(random.randint(350, 600)))
    time.sleep(random.uniform(0.6, 0.9) if not ui.ANDROID else random.uniform(*LIST_SETTLE))  # let the list settle before reading it (adb's drag pauses before lifting, so it glides less)


# ---------- one Pokémon ----------

def is_tag(t, name):
    return ui.norm(t) == name.upper()


def appraise():
    """-> (verdict name or NOPE). Raises Skip if unsure. Leaves the appraisal open."""
    reads = []
    for _ in range(6):  # bars fill in with an animation: wait for two identical reads
        screen, texts, path, _ = wait_for("appraisal")
        ivs, raws = ui.bars(path, texts)
        reads.append((ivs, raws))
        if len(reads) >= 2 and reads[-1] == reads[-2] and ivs is not None:
            return ivs, raws
        time.sleep(0.25)
    keep_capture("bars")
    raise Skip(f"bars unreadable or unsteady: {reads[-1][1]}")


def back_to_list():
    """from appraisal, detail, menu or a gym defender's screen to the list, by the known-safe path"""
    screen = wait_for("appraisal", "detail", "menu", "gym", "list")[0]
    if screen == "appraisal":
        screen = go("dialog", "detail")[0]
    if screen == "menu":
        screen = go("close", "detail")[0]
    if screen in ("detail", "gym"):
        go("close", "list")
    wait_for("list")


def recover(e, what):
    """after a Lost mid-Pokémon: back out to the list by the known-safe path, so the walk can pass this one and
    go on. Stops instead on the tag sheet or the nickname box (backing out there could save a half-made change)"""
    global lost
    lost += 1
    keep_capture(f"lost-{what}")
    try:
        screen = look()[0]
    except Refused:
        screen = "?"  # back_to_list() below can't find a known screen either, and stops
    if screen in ("tags", "rename"):
        raise Stop(f"{e} (on the {screen} screen: not safe to back out)") from e
    if lost > MAX_LOST:
        raise Stop(f"{e} (lost the screen {lost} times this run)") from e
    log(f"LOST {what}: {e}. Backing out to the list and passing it")
    back_to_list()


def settle(read, ok, timeout=3):
    """keep reading until ok(value) or timeout: taps land faster than the screen redraws"""
    end = time.time() + timeout
    while True:
        v = read()
        if ok(v) or time.time() > end:
            return v
        time.sleep(0.1)


# ---------- which Pokémon is open ----------
# Tags, the star and the name may only change the Pokémon that was opened. A stray swipe on the detail screen
# slides to its neighbour, and the tag sheet doesn't show which one it's on: on 10-07 a Nope meant for
# Mewtwo CP2945 landed on Mewtwo CP2371. So each change checks CP and max HP before and after.
OPENED = {}  # "who": (CP, max HP, kg, m) read on the detail screen right after open_tile()


def number(s, unit):
    """'12.5 kg' -> 12.5 (a comma decimal too), None if it isn't that"""
    m = re.fullmatch(r"([\d.,]+)\s*" + unit, (s or "").strip())
    return float(m.group(1).replace(",", ".")) if m else None


def who(info):
    """CP, max HP, weight and height: raid twins often share CP and HP, but hardly ever weight and height too"""
    kg = next((v for v in (number(t, "kg") for t in info.get("texts", [])) if v is not None), None)
    m = next((v for v in (number(t, "m") for t in info.get("texts", [])) if v is not None), None)
    return info["cp"], info["hp"], kg, m


def same_pokemon(a, b):
    """two who() reads: the same Pokémon? Unread values, or a dropped CP digit ('CP62' for CP626), still match"""
    (c1, *r1), (c2, *r2) = a, b
    if any(x is not None and y is not None and x != y for x, y in zip(r1, r2)):
        return False
    return not (c1 and c2 and c1 != c2 and not (str(c1).startswith(str(c2)) or str(c2).startswith(str(c1))))


def detail_now():
    _, texts, _, _ = wait_for("detail")
    return ui.detail_info(texts)


def still_opened(what, info=None):
    """raise Stop unless the detail screen still shows the Pokémon that was opened. info: a read already made.
    Nothing opened through open_tile() yet: this read becomes the one to compare with"""
    info = info or detail_now()
    if not OPENED:
        OPENED["who"] = who(info)
        return
    now = who(info)
    if not same_pokemon(OPENED["who"], now):  # a read mid-slide: look again
        now = settle(lambda: who(detail_now()), lambda w: same_pokemon(OPENED["who"], w), timeout=2)
    if not same_pokemon(OPENED["who"], now):
        keep_capture("moved")
        say = lambda w: f"CP{w[0]} HP{w[1]} {w[2]}kg {w[3]}m"
        raise Stop(f"{what}: the screen shows {say(now)}, but {say(OPENED['who'])} was opened. "
                   f"It slid to another Pokémon: check that one's tags, star and name by hand")


def detail_tags():
    info = detail_now()
    still_opened("after the tags", info)
    return [ui.norm(t) for t in info["tags"]]


def detail_name():
    info = detail_now()
    still_opened("after the rename", info)
    return info["name"] or ""


def tick_tags():
    _, texts, path, _ = wait_for("tags")
    return {ui.norm(n): on for n, on in ui.ticked_tags(path, texts)}


def tag_sheet_step(up=False):
    """scroll the tag sheet a small step (a big one skips rows). -> did the rows move?"""
    _, before, _, bounds = wait_for("tags")
    a, b = (0.4, 0.62) if up else (0.62, 0.4)
    drag(0.3, a, 0.3, b, bounds)
    if ui.ANDROID:
        ui.android.fresh()
    _, after, _, _ = wait_for("tags")
    return [t[4] for t in after] != [t[4] for t in before]


def show_tag(T):
    """scroll the tag sheet until row T shows: down first, then back up. A long list hides tags past the first
    screen (HashTagAJay's GuaranteedLucky and Old). -> the showing rows' ticks, or None if the account has no T"""
    for up in (False, True):
        same = 0
        for _ in range(30):
            ticks = tick_tags()
            if T in ticks:
                return ticks
            if same >= 2:
                break
            same = 0 if tag_sheet_step(up) else same + 1
    return None


def row_name(s):
    """a tag sheet row's text -> its name, upper case (the icon by Remote Trade reads as a stray letter)"""
    return re.sub(r"^[A-Z] (?=[A-Z]{2})", "", ui.norm(s.lstrip("•· ")))


def tap_tag_row(T, name):
    """tap a row of the open tag sheet. A tag tap() doesn't know (GIV, RT ...) or with a never-tap button's word in it
    (Transfer, Remote Trade) is tapped by its own row, and only when two looks agree it's the tag sheet, standing
    still, with exactly one row that says just that"""
    if T in ui.CONFIRM_SCREENS and not any(z in T for z in ui.HAZARDS):
        return tap(name)
    seen = []
    for i in range(2):
        if i:
            time.sleep(0.4)
            if ui.ANDROID:
                ui.android.fresh()
        _, texts, _, bounds = wait_for("tags")
        rows = [t for t in texts if row_name(t[4]) == T]
        if len(rows) != 1:
            raise Stop(f"tag sheet: {len(rows)} rows read {name!r}, wanted 1")
        seen.append(rows[0])
    if abs(seen[0][0] - seen[1][0]) > 0.01 or abs(seen[0][1] - seen[1][1]) > 0.01:
        raise Stop(f"tag sheet: the {name} row moved between two looks")
    tap_box(seen[1], bounds)


def lift_tag_row(T):
    """Android: a tap on the last row showing, or the first one of a scrolled list (under the list's fades), doesn't
    take. Scroll it up (or down) a little first. At the list's top the down scroll changes nothing"""
    _, texts, _, _ = wait_for("tags")
    row = next((t for t in texts if row_name(t[4]) == T), None)
    if row and (row[1] > 0.7 or row[1] < 0.33):
        x, y = random.randint(650, 790), random.randint(1960, 2040)
        dy = -random.randint(370, 430)
        if row[1] < 0.33:  # (seen 2026-10-29: IVC at 28%, faded, two taps didn't untick it)
            y, dy = random.randint(1150, 1250), random.randint(280, 320)
        ui.android.shell(f"input swipe {x} {y} {x + random.randint(-8, 8)} {y + dy} {random.randint(520, 680)}")
        time.sleep(0.5)  # the loop below waits for the rows to hold still
        ui.android.fresh()  # a tap off a picture from before the scroll lands a row off (ticked PvpC for Nope)
        last = None
        for _ in range(8):  # then wait until the rows hold still
            _, texts, _, _ = wait_for("tags")
            ys = [round(t[1], 3) for t in texts]
            if ys == last:
                break
            last = ys
            time.sleep(0.3)


def high_iv(ivs=None, raws=None):
    """on the detail screen: 98%+ (a shadow: 98%+ once purified)? Appraises first unless the bars are given, and
    comes back to the detail screen. A bar between two values counts as the higher one. -> (keep?, ivs, raws, what)"""
    _, texts, _, _ = wait_for("detail")
    shadow = is_shadow(texts)
    if ivs is None:
        open_appraisal()
        try:
            ivs, raws = appraise()
        finally:
            go("dialog", "detail")
            # the appraisal fades out slowly and reads as the detail screen while it does: wait until its bars are gone
            for _ in range(20):
                _, texts, _, _ = wait_for("detail")
                if not {"ATTACK", "DEFENSE"} & {ui.norm(t[4]) for t in texts}:
                    break
                time.sleep(0.25)
    top =[min(15, max(v, math.floor(r + 0.7))) for v, r in zip(ivs, raws or ivs)]
    if shadow:
        top = [min(15, v + 2) for v in top]
    what = f"{'/'.join(map(str, ivs))}{' shadow' if shadow else ''}"
    return sum(top) >= ALWAYS_KEEP, ivs, raws, what


def tags_done():
    """DONE on the tag sheet. A Remote Trade tag on one caught under 30 days asks first ('This Pokémon will keep the
    Remote Trade tag'): OK keeps it"""
    try:
        return go("DONE", "detail")
    except Lost:
        _, texts, _, bounds = look()
        if not any("REMOTE TRADE TAG" in ui.norm(t[4]) for t in texts):
            raise
        ok = [t for t in texts if ui.norm(t[4]) == "OK"]
        if len(ok) != 1:
            raise Stop(f"the Remote Trade question: {len(ok)} OK buttons read")
        log("  the game: it can trade remotely in a while and keeps the Remote Trade tag: OK")
        tap_box(ok[0], bounds)
        return wait_for("detail")


def set_tags(on=(), off=(), only=False, ivs=None, raws=None):
    """tick the on tags and untick the off ones, leave the rest. only: afterwards the detail must show just the on tags.
    Nope never goes on a 98%+ one: it's appraised first (unless ivs/raws are given) and skipped if so"""
    still_opened("before the tags")
    if "NOPE" in {t.upper() for t in on}:
        keep, _, _, what = high_iv(ivs, raws)
        if keep:
            raise Skip(f"{what} is 98%+ (or purifies to it): never Nope")
    go("menu", "menu")
    go("TAG", "tags")
    missing = [t for t in on if show_tag(t.upper()) is None]
    if missing:  # this account may not have the tag: change nothing
        go("DONE", "detail")  # nothing ticked or unticked yet, so DONE changes nothing
        raise Skip(f"no {', '.join(missing)} tag on this account")
    names = {t.upper(): t for t in (*off, *on)}
    want = {**{t.upper(): False for t in off}, **{t.upper(): True for t in on}}  # unticks first
    with changing("ticking tags"):
        for T, v in want.items():
            ticks = show_tag(T)
            if ticks is None:  # an off tag this account doesn't have
                continue
            for _ in range(2):  # a tick only gets tapped again once a slow read has shown it didn't change
                if ticks.get(T) is not v:
                    if ui.ANDROID:
                        lift_tag_row(T)
                    tap_tag_row(T, names[T])
                    ticks = settle(tick_tags, lambda t: t.get(T) is v)
            if ticks.get(T) is not v:
                keep_capture("tags")
                raise Stop(f"tags didn't end up right: {ticks}")
        tags_done()
        ON, OFF = {t.upper() for t in on}, {t.upper() for t in off}
        good = lambda t: (sorted(t) == sorted(ON)) if only else (ON <= set(t) and not OFF & set(t))
        tags = settle(detail_tags, good)
        if not good(tags):
            keep_capture("tags")
            raise Stop(f"after DONE tags are {tags}, wanted {sorted(ON)} on{' only' if only else ''}, {sorted(OFF)} off")


def set_star(on):
    """favorite (on) or not. The star toggles, so it's only tapped when it's the other way"""
    _, texts, path, bounds = wait_for("detail")
    still_opened("before the star", ui.detail_info(texts))
    filled, spot = ui.star_filled(path, texts), ui.star_spot(texts)
    if filled is None and ui.ANDROID:  # the CP next to the star misread: look again at the phone's own screenshot
        path = ui.android.sharp()
        texts = ui.ocr(path)
        filled, spot = ui.star_filled(path, texts), ui.star_spot(texts)
    if filled is None:
        raise Skip("can't find the favorite star")
    if filled is not on:
        def read():
            _, texts, path, _ = wait_for("detail")
            still_opened("after the star", ui.detail_info(texts))
            f = ui.star_filled(path, texts)
            if f is None and ui.ANDROID:
                path = ui.android.sharp()
                f = ui.star_filled(path, ui.ocr(path))
            return f
        with changing("tapping the star"):
            if spot:
                search.click(*spot, bounds)  # tap() would read the CP again, and a 2nd read can miss it
            else:
                tap("star")
            if settle(read, lambda f: f is on, timeout=8 if ui.ANDROID else 3) is not on:  # a sharp() look takes ~2s
                keep_capture("star")
                raise Stop(f"tapped the star but it still looks {'empty' if on else 'filled'}")


def nope(mine, tags, only=True, ivs=None, raws=None):
    """swap this skill's tag (IVC or PvpC) for Nope. If the Pokémon has the other one too, only untick
    this skill's: the other skill judges it next and may still keep it. -> what was done, for the log"""
    other = "IVC" if mine.upper() == "PVPC" else "PvpC"
    if any(is_tag(t, other) for t in tags):
        set_tags(off=[mine])
        log(f"  has {other} too: unticked {mine} only, {other} decides")
        return f"left for {other}"
    set_tags(on=["Nope"], off=[mine], only=only, ivs=ivs, raws=raws)
    return "Nope"


def do_nope(tags, ivs=None, raws=None):
    return nope("PvpC", tags, ivs=ivs, raws=raws)


def same_name(got, want):
    """OCR mangles the v in Pvp (Pyp, PУp, PvP): be loose on the first three letters only"""
    got, want = (got or "").strip(), want.strip()
    ell = lambda s: re.sub(r"[1I|]", "l", s[3:]).lower()  # Leafeon's l in Eevee names can read as 1 or I
    return (len(got) == len(want) and ell(got) == ell(want)
            and re.fullmatch(r"P\S?p", got[:3], re.I) is not None)


def clear_name(ok=lambda g: bool(g) and not re.match(r"P\S?p ?[LGU]|\d", g)):
    """blank the nickname: the game shows the species name again. ok(name): the name read after OK is a species
    name (default: not a Pvp name and not starting with a digit like an /ivc name. Porygon2 is a species)"""
    still_opened("before the rename")
    go("pencil", "rename")
    with changing("clearing the name"):
        tap("field")
        time.sleep(0.3)
        for _ in range(2):
            key("a", cmd=True)
            key("delete")
            if not settle(field_text, lambda g: not g, timeout=1.5):
                break
        else:
            leave_rename("CANCEL")
            raise Stop(f"couldn't empty the nickname box (it shows {field_text()!r})")
        leave_rename("OK")
        got = settle(detail_name, ok)
        if not ok(got):
            keep_capture("rename")
            raise Stop(f"after OK the name reads {got!r}, wanted the species name")


def field_text():
    _, texts, _, _ = wait_for("rename")
    return ui.nickname_field(texts)[4].strip()


def leave_rename(button, name=None, same=same_name):
    """after typing, the first tap only ends editing: tap again until the dialog closes"""
    for _ in range(3):
        got = field_text() if name is not None else None
        if name is not None and not same(got, name):
            keep_capture("rename")
            raise Stop(f"nickname box changed to {got!r} before {button}")
        tap(button)
        try:
            wait_for("detail", timeout=3, capture=False)
            return
        except Stop:
            pass
    raise Stop(f"{button} didn't close the nickname dialog")


def do_rename(name, same=same_name):
    """same(read, wanted): how loosely the OCR of the name may match (each skill's names misread their own way)"""
    still_opened("before the rename")
    go("pencil", "rename")
    with changing("renaming"):
        tap("field")
        time.sleep(random.uniform(0.25, 0.4))  # field taking focus
        for attempt in range(2):
            key("a", cmd=True)
            key("delete")
            time.sleep(random.uniform(0.15, 0.25))  # typing straight after cmd+a once dropped the first letter
            type_text(name)
            got = settle(field_text, lambda g: same(g, name), timeout=1.5)
            if same(got, name):  # the typing itself is exact keycodes; only the reading is fuzzy
                break
            log(f"  field shows {got!r}, wanted {name!r}" + (", retyping" if attempt == 0 else ""))
        else:
            keep_capture("rename")
            leave_rename("CANCEL")
            raise Stop(f"couldn't get {name!r} into the nickname box")
        leave_rename("OK", name, same)
        got = settle(detail_name, lambda g: same(g, name))
        if not same(got, name):
            keep_capture("rename")
            raise Stop(f"after OK the name reads {got!r}, wanted {name!r}")


# ---------- the detail screen (shared with /ivc and /ivcsort) ----------

TYPES = {"NORMAL", "FIRE", "WATER", "GRASS", "ELECTRIC", "ICE", "FIGHTING", "POISON", "GROUND", "FLYING", "PSYCHIC",
         "BUG", "ROCK", "GHOST", "DRAGON", "DARK", "STEEL", "FAIRY"}


def steady_detail():
    """the screen slides in: wait for two reads that agree. The first one after open_tile() is the Pokémon that
    tags, star and name may change (OPENED)"""
    prev = None
    for _ in range(6):
        _, texts, path, _ = wait_for("detail")
        info = ui.detail_info(texts)
        now = (info["name"], info["cp"], info["hp"], tuple(info["tags"]))
        if now == prev:
            break
        prev = now
        time.sleep(0.15)
    OPENED.setdefault("who", who(info))
    return info, texts, path


def short(s):
    """for comparing two reads of a name: OCR adds or drops spaces and reads O as 0 ('84 A 0*' is '84 AO*')"""
    return re.sub(r"[.…]+$", "", (s or "").strip()).replace(" ", "").replace("0", "o").lower()


def opened_right(info, tile_name, tile_cp):
    """the detail is the tile that was tapped: same CP, and one name starts the other (tiles cut long names)"""
    if info["cp"] and info["cp"] != tile_cp:
        raise Skip(f"opened CP{info['cp']} but tile said CP{tile_cp}")
    a, b = short(info["name"]), short(tile_name)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def is_shadow(texts):
    return any(ui.norm(t[4]).startswith("PURIFY") for t in texts)


def extras(texts):
    """shadow, lucky and XXL/XXS badge from the detail screen"""
    words = [ui.norm(t[4]) for t in texts]
    lucky = any(w.startswith("LUCKY POK") for w in words)
    hp_line = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    dust = [t[1] for t in texts if ui.norm(t[4]) == "STARDUST"]
    bottom = min(dust) if dust else hp_line[1] + 0.2
    # the badge sits over the height on the right; "CANDY XL" is lower down, below STARDUST
    badge = {re.sub(r"[^A-Z]", "", t[4].upper()) for t in texts
             if hp_line[1] + 0.04 < t[1] < bottom and t[0] > 0.55}
    size = "XXL" if badge & {"XXL", "LXX"} else "XXS" if badge & {"XXS", "SXX"} else None
    if badge & {"XXL", "LXX"} and badge & {"XXS", "SXX"}:
        raise Skip(f"both size badges read: {badge}")
    return is_shadow(texts), lucky, size


def candy(texts):
    """the family's candy name: 'ABSOL CANDY' on one line, or the word right above CANDY (not CANDY XL)"""
    one = {re.sub(r"\s+CANDY$", "", ui.norm(t[4])) for t in texts if re.search(r"\S\s+CANDY$", ui.norm(t[4]))}
    if len(one) == 1:
        return one.pop()
    c = [t for t in texts if ui.norm(t[4]) == "CANDY"]
    if len(c) != 1:
        return None
    x, y, w, _ = c[0][:4]
    above = [t for t in texts if 0 < y - t[1] < 0.035 and t[0] < x + w and x < t[0] + t[2]]
    return ui.norm(max(above, key=lambda t: t[1])[4]) if above else None


def type_line(texts):
    """the types under the name ('ICE / FLYING'), between the HP line and STARDUST"""
    hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    words = lambda t: ui.norm(t[4]).replace("/", " ").split()
    for t in texts:
        if hp[1] < t[1] < hp[1] + 0.2 and words(t) and all(w in TYPES for w in words(t)):
            # the two types can come out as two texts: 'FLYING' and '/ STEEL'
            return {w for x in texts if abs(x[1] - t[1]) < 0.012 and words(x) and all(w in TYPES for w in words(x)) for w in words(x)}
    return set()


def can_have(sid, cp, hp):
    """some IVs at some level give this exact CP and HP: a CP too high for the earlier stages rules them out"""
    b = pvp.SPECIES[sid]["baseStats"]
    for lv in pvp.LEVELS:
        hs = [h for h in range(16) if pvp.hp(b, (0, 0, h), lv) == hp]
        if hs and any(pvp.cp(b, (a, d, h), lv) == cp for h in hs for a in range(16) for d in range(16)):
            return True
    return False


def species_from_candy(texts, cp, hp):
    """for a Pokémon whose name isn't its species (a nickname): the line from the candy name, the forms in it
    with the types shown, and of those the ones that can have this CP and HP. -> list of species, or Skip"""
    got = candy(texts)  # a line with a baby takes the next one's candy (Azurill: MARILL CANDY)
    lines = {pvp.root(s) for s in pvp.PLAIN if ui.norm(pvp.base_name(s)) == ui.norm(got or "")}
    if not lines:
        raise Skip(f"species unclear: candy reads {got!r}")
    seen = type_line(texts)
    # every form whose line starts there: tree() misses some (Alolan Raichu isn't among Pikachu's evolutions)
    forms = [s for s in pvp.PLAIN if pvp.root(s) in lines
             and {t.upper() for t in pvp.PLAIN[s]["types"] if t != "none"} == seen]
    sp = [s for s in forms if can_have(s, cp, hp)]
    if not sp:
        raise Skip(f"species unclear: no form in the {got} line has types {sorted(seen)} and CP{cp} {hp}HP")
    log(f"  {got} candy, {'/'.join(sorted(seen))}, CP{cp} {hp}HP: {sp}")
    return sp


def dynamax(texts):
    hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    return any(ui.norm(t[4]) in ("DYNAMAX", "GIGANTAMAX") and hp[1] < t[1] < hp[1] + 0.3 for t in texts)


LIST_SETTLE = (0.35, 0.5)  # Android: a list or grid holds still this soon after a drag (adb's drag pauses before
# lifting, so it doesn't glide on). Measured on the Pokémon list (scroll()); /gift and /dex scroll lists the same way


def drag(fx, fy, tx, ty, bounds, ms=None, settle=(0.7, 0.9), android_settle=None, bring_front=True, hold=None):
    """a finger drag from (fx, fy) to (tx, ty), window fractions, then wait for it to stop moving.
    ms: how long the drag takes (default 400-600). settle: (lo, hi) seconds after it. android_settle: on Android
    that instead (LIST_SETTLE for a list; None keeps settle there too). bring_front: front() first.
    hold: ms the finger holds still before it moves (default a few ms: a long press starts multi-select in the list)"""
    if bring_front:
        front()
    x1, y1 = to_points(fx, fy, bounds)
    x2, y2 = to_points(tx, ty, bounds)
    ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}",
          str(random.randint(400, 600) if ms is None else ms), *([str(int(hold))] if hold else []))
    time.sleep(random.uniform(*(android_settle if ui.ANDROID and android_settle else settle)))


def open_tile(i):
    """tap the tile. Now and then the detail opens already scrolled down to the moves: drag it back to the top,
    starting on the weight (no button there). A Pokémon defending a gym opens its gym screen instead (its CP there
    is lower than the tile's): Skip, and the caller backs out and passes it."""
    OPENED.clear()
    try:
        got = go(f"tile {i}", "detail", "gym")
    except Stop:
        screen, texts, _, bounds = look()
        words = {ui.norm(t[4]) for t in texts}
        kg = [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
        if screen != "unknown" or not {"WEIGHT", "STARDUST"} <= words or len(kg) != 1 \
                or any(re.search(r"\d+\s*/\s*\d+\s*HP", t[4]) for t in texts):
            raise
    else:
        if got[0] == "gym":
            raise Skip(GYM)
        return got
    log("  detail opened scrolled down, dragging it back to the top")
    x, y = kg[0][0] + kg[0][2] / 2, kg[0][1] + kg[0][3] / 2
    drag(x, y, x, min(y + random.uniform(0.45, 0.5), 0.85), bounds)
    return wait_for("detail")


def open_appraisal():
    go("menu", "menu")
    go("APPRAISE", "appraise-intro", "appraisal")
    go("dialog", "appraisal")


def appraisal_species(detail_texts):
    """the appraisal's 'This Meditite was caught on ...' line names the species whatever the nickname.
    detail_texts: the detail screen's, whose type line tells regional forms apart. Leaves the appraisal open"""
    for _ in range(6):
        _, texts, _, _ = wait_for("appraisal")
        m = re.search(r"\bThis (.+?) was\b", " ".join(t[4] for t in texts))
        if m:
            break
        time.sleep(0.25)
    else:
        raise Skip("species unclear: no 'This ... was' line on the appraisal")
    sp = ui.species_for(m.group(1), detail_texts)
    if not sp:
        raise Skip(f"species unclear: the appraisal says {m.group(1)!r}")
    log(f"  the appraisal names it {m.group(1)}: {sp}")
    return sp


def exact_ivs(sp, cp, hp, ivs, raws):
    """bar reading checked against CP and HP: the names depend on exact IVs"""
    crisp = all(abs(r - round(r)) <= 0.3 for r in raws)
    cands = set()
    for s in sp:
        b = pvp.SPECIES[s]["baseStats"]
        for lv in pvp.LEVELS:
            for a in range(max(0, ivs[0] - 1), min(15, ivs[0] + 1) + 1):
                for d in range(max(0, ivs[1] - 1), min(15, ivs[1] + 1) + 1):
                    for h in range(max(0, ivs[2] - 1), min(15, ivs[2] + 1) + 1):
                        if pvp.cp(b, (a, d, h), lv) == cp and pvp.hp(b, (a, d, h), lv) == hp:
                            cands.add((a, d, h))
    if crisp and tuple(ivs) in cands:
        return tuple(ivs)
    if len(cands) == 1:
        return next(iter(cands))
    raise Skip(f"IVs unsure: bars={ivs} raw={raws}, CP/HP fit {sorted(cands) or 'nothing'}")


def open_tag(name):
    """on the Tags tab, scroll down until the tag's row is clear of the bottom buttons, then open it.
    Down first: pulling down at the top of the Tags tab closes the whole Pokémon screen."""
    want = name.upper()
    for up in (False, True):  # the tab can be left scrolled past the tag: then back up. That stops once the tag
        prev = None           # shows, so it only pulls at the very top if the tag isn't there at all
        for _ in range(40):
            _, texts, _, bounds = wait_for("tag-tab")
            rows = [t for t in texts if ui.norm(t[4]) == want]
            if len(rows) == 1 and 0.15 < rows[0][1] < 0.78:
                go(name, "list")
                return
            seen = [t[4] for t in texts]
            if seen == prev:
                break  # list stopped moving: bottom (or top) reached
            prev = seen
            scroll(bounds, "drag", up=up)
    keep_capture("tag")
    raise Stop(f"couldn't find the {name} tag on the Tags tab (scrolled to the bottom)")


def to_tags_tab():
    """get to the Tags tab. The full Pokémon list (TAGS / POKÉMON / EGGS header showing) has a TAGS tab to tap.
    A tag-filtered list drops back to the Tags tab when pulled down past the top."""
    if wait_for("list", "tag-tab", "detail", "menu", "appraisal", "gym")[0] not in ("list", "tag-tab"):
        back_to_list()  # a run that was cut off left a Pokémon open
    for _ in range(150):  # a stop deep in a 700+ list needs 60+ pulls to get back up
        screen, texts, _, bounds = wait_for("list", "tag-tab")
        if screen == "tag-tab":
            return
        if search.leave_multiselect(texts, bounds):  # a run cut off mid-swipe can leave the list in multi-select
            continue
        words = {ui.norm(t[4]) for t in texts}
        if {"TAGS", "EGGS"} <= words:  # unfiltered list: pulling down here would close the Pokémon screen
            go("TAGS", "tag-tab")
            return
        scroll(bounds, "drag", up=True)
    raise Stop("never got back to the Tags tab")


def to_top(tag="PvpC"):
    """open the tag's list fresh from the Tags tab, so it starts at the top"""
    to_tags_tab()
    open_tag(tag)


def slots_of(sp, cp, hp, ivs):
    """{(league, form): rank} for exact IVs. sp: the forms it could be; CP and HP pick between them"""
    fit = [s for s in sp if s in pvp.PLAIN and any(pvp.cp(pvp.PLAIN[s]["baseStats"], ivs, lv) == cp and
                                pvp.hp(pvp.PLAIN[s]["baseStats"], ivs, lv) == hp for lv in pvp.LEVELS)]
    slots = {tuple(sorted(pvp.iv_slots(s, ivs, pvp.level_of(s, ivs, cp, hp)).items())) for s in fit}
    if len(slots) != 1:
        raise Skip(f"species unclear: {fit} rank differently")
    return dict(slots.pop()), fit[0]


import search, fallen, home, session  # down here: they `import base`, which has to be all there first


def start():
    """a run's first step: from wherever the phone is (Pokémon GO closed too) to the Pokémon screens"""
    home.start()


def scroll_for_new(ts, seen, bounds, how):
    """scroll the list down a screen -> (fresh, how). fresh: a tile with a CP not in seen showed up. At the bottom
    the list bounces back and OCR reads it a bit differently each time, so "did the tiles change" never settles:
    look for tiles we haven't seen instead. A scroll that doesn't move the list at all tries the other way of
    scrolling; how is the way that worked, for next time"""
    before = [t[:2] for t in ts]
    for way in ([how] + [h for h in ("wheel", "drag") if h != how]):
        scroll(bounds, way)
        _, texts, _, bounds = wait_for("list")
        now = ui.tiles(texts)
        if {t[1] for t in now} - seen:
            return True, way
        if [t[:2] for t in now] == before:
            continue  # didn't move at all: try the other way of scrolling
        break  # moved, but nothing new
    return False, how


