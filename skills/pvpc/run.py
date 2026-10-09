#!/usr/bin/env python3
"""Unattended /pvpc: works through the PvpC-tagged list in iPhone Mirroring with no Claude.

  caffeinate -dimsu python3 run.py [--limit N] [--dry-run]       rename (or Nope) every PvpC Pokémon. At the end of
                                                                 the list it also runs `fallen` on this run
  caffeinate -dimsu python3 run.py fallen <run dir>              which older Pvp Pokémon the new names pushed out,
                                                                 and which to trim (reads only) -> <run dir>/fallen.txt
  caffeinate -dimsu python3 run.py act-fallen <run dir> [--limit N]  rename the trims to the leagues they're still
                                                                 best in, until nothing changes, then tag the fallen
                                                                 ones GuaranteedLucky / Old / Nope
  POGO_PHONE=android caffeinate -dimsu python3 run.py ...   (Android phone over USB, see android.py)

Start with Pokémon GO on the inventory, filtered to the PvpC tag. Anything the script isn't sure
about is skipped and written to runs/<time>/log.txt with a capture. Anything unexpected stops the run.
This file is also the shared tapper and screen code for /ivc and /ivcsort (they `import run`).
"""
import json, math, os, random, re, shutil, subprocess, sys, time
from collections import Counter

if __name__ == "__main__":  # search.py and fallen.py `import run`: let them share this copy (one RUN_DIR, one last_tap)
    sys.modules["run"] = sys.modules[__name__]
import ui, pvp
from ui import Refused, Moving

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S"))
MAX_SKIPS_IN_A_ROW = 5
END_AFTER_STALE = 3  # scrolls in a row that show no new tiles
ALWAYS_KEEP = 44  # IV sum of 98%: 98% and 100% (a shadow: once purified) never get Nope, traded or transferred
NAME_OK = re.compile(r"Pvp ?[LGU][A-Za-z0-9 +]*")


class Stop(Exception):
    """something unexpected: stop the whole run"""


class Skip(Exception):
    """not sure about this one: leave it for a human"""


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


def new_run_dir(runs, d=None):
    global RUN_DIR
    RUN_DIR = d or os.path.join(runs, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(RUN_DIR, exist_ok=True)
    return RUN_DIR


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
USER_IDLE = 20  # front() waits this long after the user's last key or click before taking the screen back


def tap_gap():
    """wait until a short random gap has passed since the last tap"""
    time.sleep(max(0.0, last_tap + random.uniform(0.1, 0.25) - time.time()))


def think():
    """on the appraisal: looks like working out the IVs and the stat product"""
    t = random.uniform(2.5, 5.5)
    if random.random() < 0.15:
        t += random.uniform(1.5, 4)
    time.sleep(t)


# ---------- screen ----------

def look():
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    ui.remember(path, texts, bounds)
    return ui.classify(texts), texts, path, bounds


def wait_for(*screens, timeout=10, capture=True):
    """poll until one of the screens shows up. Brief unknown screens (animations) are fine."""
    end, last, nudges = time.time() + timeout, "?", 0
    while time.time() < end:
        try:
            screen, texts, path, bounds = look()
        except Refused as e:  # window gone for a moment
            last = str(e)
        else:
            if screen in screens:
                return screen, texts, path, bounds
            last = screen
            words = {ui.norm(t[4]) for t in texts}
            if "detail" in screens and screen == "unknown" and "STARDUST" in words and \
                    words & {"WEIGHT", "HEIGHT", "POWER UP"} and nudges < 3:
                nudges += 1  # a detail page left scrolled down (the HP line is off the top): pull it back up
                scroll(bounds, "drag", up=True)
                end = max(end, time.time() + 3)
                continue
            if screen == "unknown":
                last += ": " + " | ".join(t[4] for t in texts)[:200]
        time.sleep(0.12)
    if capture:
        keep_capture("stuck")
    raise Stop(f"wanted {screens}, screen is {last}")


def idle_seconds():
    """seconds since the last real keyboard/mouse input on the Mac"""
    out = subprocess.run(["ioreg", "-c", "IOHIDSystem", "-d", "4"], capture_output=True, text=True).stdout
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    return int(m.group(1)) / 1e9 if m else 999


def front():
    """bring iPhone Mirroring forward. If the user switched to another app, wait until they've left the Mac
    alone for USER_IDLE seconds first, so their typing doesn't land on the phone.
    Android: adb never touches the Mac's mouse or keyboard, so just check the phone."""
    if ui.ANDROID:
        try:
            return ui.android.ready()
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
            raise Stop(f"tap {target}: {e}")
        px, py = to_points(fx, fy, bounds)
        if dry:
            log(f"DRY tap {target} on {screen} at {px:.0f},{py:.0f}")
            return
        global last_tap
        tap_gap()
        ui.sh(ui.HELPER, "click", f"{px:.1f}", f"{py:.1f}", str(random.randint(50, 100)))
        last_tap = time.time()
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
    time.sleep(random.uniform(0.6, 0.9) if not ui.ANDROID else random.uniform(0.35, 0.5))  # let the list settle before reading it (adb's drag pauses before lifting, so it glides less)


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


def decide(species, cp, hp, ivs, raws):
    out = ui.check_rows(species, cp, hp, ivs)
    verdict = next((l for l in out.splitlines() if l.startswith("VERDICT:")), "")
    m = re.match(r"VERDICT: (.+?) \((.*)\)$", verdict)
    if not m:
        raise Skip(f"no verdict: {out[-200:]}")
    name, why = m.groups()
    if name in ("NEED BARS", "NO MATCH"):
        raise Skip(f"{verdict} | bars={ivs} raw={raws}")
    if "confirm with user" in out:
        raise Skip(f"branching family, letter needs a human: {verdict}")
    if why.startswith("bar reading") and any(abs(r - round(r)) > 0.3 for r in raws):
        raise Skip(f"bar reading picks it but raw={raws} is borderline: {verdict}")
    if not (why.startswith("every candidate agrees") or why.startswith("bar reading")):
        raise Skip(f"odd verdict: {verdict}")
    if name != "NOPE" and not (NAME_OK.fullmatch(name) and len(name) <= 12):
        raise Skip(f"odd name {name!r}")
    return name


def decide_forms(sp, cp, hp, ivs, raws):
    """several forms left (Pumpkaboo sizes have different stats): keep the ones CP and HP fit.
    Go ahead only if they all give the same name."""
    if len(sp) == 1:
        return decide(sp[0], cp, hp, ivs, raws)
    names, why = {}, []
    for s in sp:
        try:
            names[s] = decide(s, cp, hp, ivs, raws)
        except Skip as e:
            if "NO MATCH" not in str(e):
                why.append(f"{s}: {e}")
    if len(set(names.values())) == 1 and not why:
        return next(iter(names.values()))
    raise Skip(f"species unclear: {names or sp} {'; '.join(why)}")


def back_to_list():
    """from appraisal, detail or menu to the list, by the known-safe path"""
    screen = wait_for("appraisal", "detail", "menu", "list")[0]
    if screen == "appraisal":
        screen = go("dialog", "detail")[0]
    if screen == "menu":
        screen = go("close", "detail")[0]
    if screen == "detail":
        go("close", "list")
    wait_for("list")


def settle(read, ok, timeout=3):
    """keep reading until ok(value) or timeout: taps land faster than the screen redraws"""
    end = time.time() + timeout
    while True:
        v = read()
        if ok(v) or time.time() > end:
            return v
        time.sleep(0.1)


def detail_tags():
    _, texts, _, _ = wait_for("detail")
    return [ui.norm(t) for t in ui.detail_info(texts)["tags"]]


def detail_name():
    _, texts, _, _ = wait_for("detail")
    return ui.detail_info(texts)["name"] or ""


def tick_tags():
    _, texts, path, _ = wait_for("tags")
    return {ui.norm(n): on for n, on in ui.ticked_tags(path, texts)}


def lift_tag_row(T):
    """Android: a tap on the last row showing (under the list's fade) doesn't take. Scroll it up a little first"""
    _, texts, _, _ = wait_for("tags")
    row = next((t for t in texts if ui.norm(t[4].lstrip("•· ")) == T), None)
    if row and row[1] > 0.7:
        ui.android.shell("input swipe 720 2000 720 1600 600")
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
    top = [min(15, max(v, math.floor(r + 0.7))) for v, r in zip(ivs, raws or ivs)]
    if shadow:
        top = [min(15, v + 2) for v in top]
    what = f"{'/'.join(map(str, ivs))}{' shadow' if shadow else ''}"
    return sum(top) >= ALWAYS_KEEP, ivs, raws, what


def set_tags(on=(), off=(), only=False, ivs=None, raws=None):
    """tick the on tags and untick the off ones, leave the rest. only: afterwards the detail must show just the on tags.
    Nope never goes on a 98%+ one: it's appraised first (unless ivs/raws are given) and skipped if so"""
    if "NOPE" in {t.upper() for t in on}:
        keep, _, _, what = high_iv(ivs, raws)
        if keep:
            raise Skip(f"{what} is 98%+ (or purifies to it): never Nope")
    go("menu", "menu")
    go("TAG", "tags")
    ticks = tick_tags()
    missing = [t for t in on if t.upper() not in ticks]
    if missing:  # this account may not have the tag: change nothing
        go("DONE", "detail")  # nothing ticked or unticked yet, so DONE changes nothing
        raise Skip(f"no {', '.join(missing)} tag on this account")
    names = {t.upper(): t for t in (*off, *on)}
    want = {**{t.upper(): False for t in off}, **{t.upper(): True for t in on}}  # unticks first
    for T, v in want.items():
        for _ in range(2):  # a tick only gets tapped again once a slow read has shown it didn't change
            if T in ticks and ticks[T] is not v:
                if ui.ANDROID:
                    lift_tag_row(T)
                tap(names[T])
                ticks = settle(tick_tags, lambda t: t.get(T) is v)
    if any(T in ticks and ticks[T] is not v for T, v in want.items()):
        keep_capture("tags")
        raise Stop(f"tags didn't end up right: {ticks}")
    go("DONE", "detail")
    ON, OFF = {t.upper() for t in on}, {t.upper() for t in off}
    good = lambda t: (sorted(t) == sorted(ON)) if only else (ON <= set(t) and not OFF & set(t))
    tags = settle(detail_tags, good)
    if not good(tags):
        keep_capture("tags")
        raise Stop(f"after DONE tags are {tags}, wanted {sorted(ON)} on{' only' if only else ''}, {sorted(OFF)} off")


def set_star(on):
    """favorite (on) or not. The star toggles, so it's only tapped when it's the other way"""
    _, texts, path, bounds = wait_for("detail")
    filled, spot = ui.star_filled(path, texts), ui.star_spot(texts)
    if filled is None and ui.ANDROID:  # the CP next to the star misread: look again at the phone's own screenshot
        path = ui.android.sharp()
        texts = ui.ocr(path)
        filled, spot = ui.star_filled(path, texts), ui.star_spot(texts)
    if filled is None:
        raise Skip("can't find the favorite star")
    if filled is not on:
        if spot:
            search.click(*spot, bounds)  # tap() would read the CP again, and a 2nd read can miss it
        else:
            tap("star")

        def read():
            _, texts, path, _ = wait_for("detail")
            f = ui.star_filled(path, texts)
            if f is None and ui.ANDROID:
                path = ui.android.sharp()
                f = ui.star_filled(path, ui.ocr(path))
            return f
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


def field_text():
    _, texts, _, _ = wait_for("rename")
    return ui.nickname_field(texts)[4].strip()


def leave_rename(button, name=None, same=same_name):
    """after typing, the first tap only ends editing: tap again until the dialog closes"""
    for _ in range(3):
        if name is not None and not same(field_text(), name):
            keep_capture("rename")
            raise Stop(f"nickname box changed to {field_text()!r} before {button}")
        tap(button)
        try:
            wait_for("detail", timeout=3, capture=False)
            return
        except Stop:
            pass
    raise Stop(f"{button} didn't close the nickname dialog")


def do_rename(name, same=same_name):
    """same(read, wanted): how loosely the OCR of the name may match (each skill's names misread their own way)"""
    go("pencil", "rename")
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
    """the screen slides in: wait for two reads that agree"""
    prev = None
    for _ in range(6):
        _, texts, path, _ = wait_for("detail")
        info = ui.detail_info(texts)
        now = (info["name"], info["cp"], info["hp"], tuple(info["tags"]))
        if now == prev:
            break
        prev = now
        time.sleep(0.15)
    return info, texts, path


def short(s):
    return re.sub(r"[.…]+$", "", (s or "").strip()).lower()


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
    for t in texts:
        words = ui.norm(t[4]).split()
        if hp[1] < t[1] < hp[1] + 0.2 and words and all(w in TYPES for w in words):
            return set(words)
    return set()


def dynamax(texts):
    hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    return any(ui.norm(t[4]) in ("DYNAMAX", "GIGANTAMAX") and hp[1] < t[1] < hp[1] + 0.3 for t in texts)


def drag(fx, fy, tx, ty, bounds):
    front()
    x1, y1 = to_points(fx, fy, bounds)
    x2, y2 = to_points(tx, ty, bounds)
    ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", str(random.randint(400, 600)))
    time.sleep(random.uniform(0.7, 0.9))


def open_tile(i):
    """tap the tile. Now and then the detail opens already scrolled down to the moves: drag it back to the top,
    starting on the weight (no button there)."""
    try:
        return go(f"tile {i}", "detail")
    except Stop:
        screen, texts, _, bounds = look()
        words = {ui.norm(t[4]) for t in texts}
        kg = [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
        if screen != "unknown" or not {"WEIGHT", "STARDUST"} <= words or len(kg) != 1 \
                or any(re.search(r"\d+\s*/\s*\d+\s*HP", t[4]) for t in texts):
            raise
    log("  detail opened scrolled down, dragging it back to the top")
    x, y = kg[0][0] + kg[0][2] / 2, kg[0][1] + kg[0][3] / 2
    drag(x, y, x, min(y + random.uniform(0.45, 0.5), 0.85), bounds)
    return wait_for("detail")


def open_appraisal():
    go("menu", "menu")
    go("APPRAISE", "appraise-intro", "appraisal")
    go("dialog", "appraisal")


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


# ---------- one Pokémon ----------

def new_slots(sp, cp, hp, ivs, raws, name):
    """[[league, form, rank]] for every top-100 slot, so the fallen-out step knows the ones its name has no room for.
    None if the exact IVs or the form are unsure (then its name is all the fallen-out step goes on)"""
    sp = [s for s in sp if s in pvp.PLAIN]
    if name == "NOPE" or not sp:
        return None
    try:
        slots, _ = slots_of(sp, cp, hp, exact_ivs(sp, cp, hp, ivs, raws))
        first = pvp.root(sp[0])
        if pvp.letters(first) is None or pvp.slots_name(first, slots) != name:
            return None
    except Exception as e:  # extra data: never let it stop a rename
        log(f"  no slots saved for {name!r}: {type(e).__name__}: {e}")
        return None
    return [[a, f, r] for (a, f), r in slots.items()]


def process(i, tile_name, tile_cp):
    open_tile(i)
    info, texts, _ = steady_detail()
    cp = info["cp"] or tile_cp
    if not opened_right(info, tile_name, tile_cp):
        raise Skip(f"opened {info['name']!r} but tile said {tile_name!r}")
    if not any(is_tag(t, "PvpC") for t in info["tags"]):
        raise Skip(f"no PvpC tag on detail: {info['tags']}")
    sp = ui.species_for(info["name"], info["texts"])
    if not sp:
        raise Skip("species unclear: ?")
    shadow = is_shadow(texts)
    open_appraisal()
    ivs, raws = appraise()
    name = decide_forms(sp, cp, info["hp"], ivs, raws)
    slots = new_slots(sp, cp, info["hp"], ivs, raws, name)
    think()
    go("dialog", "detail")
    if name == "NOPE" and high_iv(ivs, raws)[0]:  # bad for PvP but 98%+: /ivc names it instead
        set_tags(on=["IVC"], off=["PvpC"])
        name = "->IVC"
    elif name == "NOPE":
        do_nope(info["tags"], ivs, raws)
    else:
        do_rename(name)
        # for the fallen-out step at the end
        save("renamed.json", load("renamed.json", []) + [{"name": name, "cp": cp, "species": sp, "shadow": shadow,
                                                           "slots": slots}])
    log(f"DONE {tile_name} CP{cp} {'/'.join(map(str, ivs))}{' shadow' if shadow else ''} -> {name}")
    go("close", "list")
    return name


# ---------- the list ----------

def pick(ts, skipped):
    """first tile not already named Pvp..., passing over ones skipped earlier this run"""
    seen = Counter()
    for i, (n, c, _, _) in enumerate(ts, 1):
        # OCR misreads or drops the v in small tile text (Pyp G13, Pp+): Piplup and Pupitar still get picked
        if n.lower().startswith("pvp") or re.match(r"P\S{0,2}p(?=[ LGU+]|$)", n):
            continue
        seen[(n, c)] += 1
        if seen[(n, c)] > skipped[(n, c)]:
            return i, n, c
    return None


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
    if wait_for("list", "tag-tab", "detail", "menu", "appraisal")[0] not in ("list", "tag-tab"):
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


# ---------- fallen out and trims ----------
# New names can push older Pvp Pokémon out of the top. Per league and form only the best one owned keeps its place
# (ties keep). One that's still best somewhere gets renamed to show just those leagues: a trim. One that's best
# nowhere has fallen out, and fallen.py tags it GuaranteedLucky / Old / Nope (shared with /ivcsort).
# A trim can make room for a league the old name had to leave out, and that league can beat someone else. So
# act-fallen goes round until nothing changes. What a Pokémon really has comes from appraising it (truths.json);
# until then, from what its name shows. The pool: every Pvp name in the line, read off in-game searches by dex number.

MAX_ROUNDS = 8


def pools_of(renamed):
    """{key: [first stage, shadow, [searches]]} for every line a new name landed in"""
    out = {}
    for r in renamed:
        for first in dict.fromkeys(pvp.root(s) for s in r["species"] if s in pvp.PLAIN):
            if pvp.letters(first) is None:
                log(f"  {r['name']!r}: the {pvp.display(first)} line branches, its names can't be read back: skipped")
                continue
            key = first + ("+shadow" if r["shadow"] else "")
            out[key] = [first, r["shadow"], pvp.line_searches(pvp.tree(first), "shadow" if r["shadow"] else "plain")]
    return out


def to_slots(lst):
    return {(t, f): r for t, f, r in lst}


def load_truths():
    """{pool key: [{name, cp, slots}]}: what appraised Pokémon really have. Starts with this run's new names."""
    t = load("truths.json", {})
    if not t:
        for r in load("renamed.json", []):
            sp = [s for s in r["species"] if s in pvp.PLAIN]
            if r.get("slots") and sp:
                key = pvp.root(sp[0]) + ("+shadow" if r["shadow"] else "")
                t.setdefault(key, []).append({"name": r["name"], "cp": r["cp"], "slots": r["slots"]})
    return t


def add_truth(pool, n, c, slots):
    t = load_truths()
    lst = [x for x in t.get(pool, []) if not (x["cp"] == c and same_name(x["name"], n))]
    t[pool] = lst + [{"name": n, "cp": c, "slots": [[a, f, r] for (a, f), r in slots.items()]}]
    save("truths.json", t)


def members(results, qs, first, truths):
    """[(name, cp, search, slots, known)] for every clean Pvp name the pool's searches showed. Appraised ones come
    with their real slots. Appraised ones no search showed (a misread tile) still count, with no search."""
    left, out = list(truths), []
    for q in qs:
        for n, c in results.get(q, []):
            if not c:
                continue
            t = next((t for t in left if t["cp"] == c and same_name(n, t["name"])), None)
            if t:
                left.remove(t)
                out.append((n, c, q, to_slots(t["slots"]), True))
            else:
                sl = pvp.name_slots(n, first)
                if sl:
                    out.append((n, c, q, sl, False))
    return out + [(t["name"], t["cp"], None, to_slots(t["slots"]), True) for t in left]


def plan(pools, results, wants, truths, only=None):
    """what every member of every pool needs: [{name, cp, pool, q, act, new, why, all, ...}], keeps left out.
    act: check (appraise it), rename, fallen. all: a check whose name shows nothing still best (likely fallen)"""
    out = []
    for key, (first, shadow, qs) in pools.items():
        if only and key != only:
            continue
        over = [q for q in qs if wants.get(q) is not None and len(results.get(q, [])) > wants[q]]
        if over:  # extra tiles could be misread copies that look better than they are
            log(f"  {key}: read more tiles than the game counts in {over}: no fallen check for this line")
            continue
        ms = members(results, qs, first, truths.get(key, []))
        twins = lambda i, j: ms[i][1] == ms[j][1] and search.looks_same(ms[i][0], ms[j][0])
        acts = pvp.plan_pool([(n, sl, k) for n, _, _, sl, k in ms], first, same_name, twins)
        for (n, c, q, sl, k), a in zip(ms, acts):
            if a[0] != "keep":
                out.append({"name": n, "cp": c, "pool": key, "q": q, "shadow": shadow, "act": a[0],
                            "new": a[1] if a[0] == "rename" else None, "why": [] if a[0] == "rename" else a[1],
                            "all": a[0] == "fallen" or (a[0] == "check" and a[2]),
                            "dex": sorted({pvp.PLAIN[s]["dex"] for s in pvp.tree(first)}),
                            "what": f"{'shadow ' if shadow else ''}{pvp.display(first)} line"})
    return out


def state():
    pools = load("fallen-pools.json")
    results = {q: [tuple(x) for x in v] for q, v in load("pools.json", {}).items()}
    return pools, results, load("counts.json", {}), load_truths()


def plan_lines(todo):
    """the trims, for fallen.txt"""
    trims = [t for t in todo if not t["all"]]
    if not trims:
        return []
    return ["", f"TRIMS: {len(trims)} still best in some leagues, beaten in others. act-fallen appraises each one and "
            "renames it to just the leagues it's still best in. The final name comes after the appraisal: a league "
            "the old name had no room for can show up, and push out someone else (act-fallen goes round until nothing "
            "changes)."] + \
        [f"  {t['name']!r:16} CP{t['cp']:<5} {t['what']}: " + (f"-> {t['new']!r}" if t["new"] else "; ".join(t["why"]))
         for t in trims]


def fallen_step():
    """reads only: pool searches -> pools.json + counts.json, the fallen-out ones -> fallen.json, the plan (fallen
    and trims) -> fallen.txt, their groups -> fallen-groups.json. Stops and starts again where it left off."""
    renamed = load("renamed.json", [])
    pools = pools_of(renamed)
    save("fallen-pools.json", pools)
    results, wants = load("pools.json", {}), load("counts.json", {})
    qs = list(dict.fromkeys(q for _, _, qq in pools.values() for q in qq))
    log(f"fallen out: {len(renamed)} new names, {len(pools)} lines, {len(qs)} searches ({sum(q in results for q in qs)} done)")
    if qs:
        front()
        search.to_search_list()
    for q in qs:
        if q in results:
            continue
        got, want = search.run_search(q)
        results[q], wants[q] = got, want
        save("pools.json", results)
        save("counts.json", wants)
        log(f"  {q}: {len(got)} tiles (game says {want})")
    todo = plan(*state())
    found = [t for t in todo if t["all"]]
    save("fallen.json", found)
    grouped = fallen.groups(iv_only=False) if found else {}
    if not found:
        save("fallen-groups.json", grouped)
    lines = fallen.summary(found, grouped) + plan_lines(todo)
    with open(os.path.join(RUN_DIR, "fallen.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"{len(found)} fallen out, {len(todo) - len(found)} to trim, see {os.path.join(RUN_DIR, 'fallen.txt')}")
    return found


def slots_of(sp, cp, hp, ivs):
    """{(league, form): rank} for exact IVs. sp: the forms it could be; CP and HP pick between them"""
    fit = [s for s in sp if s in pvp.PLAIN and any(pvp.cp(pvp.PLAIN[s]["baseStats"], ivs, lv) == cp and
                                pvp.hp(pvp.PLAIN[s]["baseStats"], ivs, lv) == hp for lv in pvp.LEVELS)]
    slots = {tuple(sorted(pvp.iv_slots(s, ivs).items())) for s in fit}
    if len(slots) != 1:
        raise Skip(f"species unclear: {fit} rank differently")
    return dict(slots.pop()), fit[0]


def appraise_slots(pool, n, c, known=None):
    """on its detail screen: species, shadow or not, then every top-100 slot it really has (appraised, unless
    known). -> (slots or None if it's the other kind, what to log). Leaves the detail screen open."""
    first, shadow, _ = load("fallen-pools.json")[pool]
    info, texts, _ = steady_detail()
    if not opened_right(info, n, c):
        raise Skip(f"opened {info['name']!r} but tile said {n!r}")
    if is_shadow(texts) != shadow:
        return None, f"{'shadow' if is_shadow(texts) else 'not shadow'}, the pool was the other kind"
    if known:
        return known, "appraised earlier"
    got = candy(texts)  # a line with a baby takes the next one's candy (Azurill: MARILL CANDY)
    if ui.norm(got or "") not in {ui.norm(pvp.base_name(s)) for s in pvp.tree(first)}:
        raise Skip(f"candy reads {got!r}, not the {pvp.display(first)} line's")
    seen = type_line(texts)
    sp = [s for s in pvp.tree(first) if {t.upper() for t in pvp.PLAIN[s]["types"] if t != "none"} == seen]
    if not sp:
        raise Skip(f"no form in the {pvp.display(first)} line has types {sorted(seen)}")
    cp = info["cp"] or c
    open_appraisal()
    bars, raws = appraise()
    go("dialog", "detail")
    ivs = exact_ivs(sp, cp, info["hp"], bars, raws)
    slots, s = slots_of(sp, cp, info["hp"], ivs)
    add_truth(pool, n, c, slots)
    return slots, f"{pvp.display(s)} {'/'.join(map(str, ivs))}"


def renamed_to(pool, old, c, new):
    """the rename is done: the pool and the truths know it by its new name now"""
    results = load("pools.json", {})
    for q in load("fallen-pools.json")[pool][2]:
        i = next((i for i, (n, cc) in enumerate(results.get(q, [])) if cc == c and same_name(n, old)), None)
        if i is not None:
            results[q][i] = [new, c]
            break
    save("pools.json", results)
    t = load_truths()
    for x in t.get(pool, []):
        if x["cp"] == c and same_name(x["name"], old):
            x["name"] = new
    save("truths.json", t)


def settle_one(pool, n, c):
    """with all that's known now, what this one needs: (act, new name)"""
    for t in plan(*state(), only=pool):
        if t["cp"] == c and same_name(t["name"], n):
            return t["act"], t["new"]
    return "keep", None


def trim_here(pool, n, c, known, rename):
    """on its detail screen: appraise it if need be, then (rename) rename it if it needs that. -> (renamed?, what to log)"""
    slots, what = appraise_slots(pool, n, c, known)
    if slots is None:
        return False, what
    act, new = settle_one(pool, n, c)
    if act == "rename" and not rename:
        return False, f"{what}: to rename to {new!r} once the rest are appraised"
    if act == "rename":
        if not same_name(detail_name(), new):  # a run cut off after the rename already did it
            do_rename(new)
        renamed_to(pool, n, c, new)
        return True, f"{what}: renamed {n!r} -> {new!r}"
    return False, f"{what}: {'beaten everywhere, tagged later' if act == 'fallen' else 'name stays'}"


def trim_walk(q, todo, tried, limit):
    """walk one search's list, handle the to-do ones in it. -> how many got renamed"""
    pending, count = list(todo), [0]

    def visit(i, n, c):
        t = next((t for t in pending if t["cp"] == c and
                  (same_name(n, t["name"]) or (t["new"] and same_name(n, t["new"])))), None)
        if not t or count[0] >= limit:
            return False
        pending.remove(t)
        tried.add((t["pool"], t["name"], t["cp"], t["act"], t["new"]))
        open_tile(i)
        name = t["name"]
        if not same_name(n, name):  # a run cut off after this rename already did it
            renamed_to(t["pool"], name, c, n)
            name = n
        known = next((to_slots(x["slots"]) for x in load_truths().get(t["pool"], [])
                      if x["cp"] == c and same_name(x["name"], name)), None)
        done, what = trim_here(t["pool"], name, c, known, t["act"] == "rename")
        count[0] += done
        log(f"{'DONE trim' if done else '  checked'} {n!r} CP{c}: {what}")
        go("close", "list")
        return False

    search.start_search(q)
    search.walk_list(visit, stop=lambda n: not pending or count[0] >= limit)
    for t in pending:
        tried.add((t["pool"], t["name"], t["cp"], t["act"], t["new"]))
        if count[0] < limit:
            log(f"  {t['name']!r} CP{t['cp']}: not found in {q}, left as it is")
    return count[0]


def recheck_fallen(n, c):
    """on its detail screen: still fallen only if each of its real slots has someone better. If it turns out to be
    best somewhere after all, it gets renamed to show that. Leaves the detail screen open."""
    f = next(f for f in load("fallen.json") if (f["name"], f["cp"]) == (n, c))
    known = next((to_slots(x["slots"]) for x in load_truths().get(f["pool"], [])
                  if x["cp"] == c and same_name(x["name"], n)), None)
    slots, what = appraise_slots(f["pool"], n, c, known)
    if slots is None:
        return False, what
    act, new = settle_one(f["pool"], n, c)
    if act == "fallen":
        return True, f"{what}: {'; '.join(f['why'])}"
    if act == "rename":
        do_rename(new)
        renamed_to(f["pool"], n, c, new)
        return False, f"{what}: still best somewhere, renamed {new!r}"
    return False, f"{what}: still best somewhere"


def act_fallen(limit):
    """trims first, round after round until nothing changes, then tag whatever is beaten everywhere"""
    front()
    search.to_search_list()
    done, tried = 0, set()
    for rnd in range(1, MAX_ROUNDS + 1):
        todo = [t for t in plan(*state()) if t["act"] in ("check", "rename") and t["q"]
                and (t["pool"], t["name"], t["cp"], t["act"], t["new"]) not in tried]
        if not todo or done >= limit:
            break
        if any(t["act"] == "check" for t in todo):  # appraise them all first: a rename before that could be undone
            todo = [t for t in todo if t["act"] == "check"]
        log(f"round {rnd}: {len(todo)} to look at")
        for q in dict.fromkeys(t["q"] for t in todo):
            if done < limit:
                done += trim_walk(q, [t for t in todo if t["q"] == q], tried, limit - done)
    else:
        log(f"STILL CHANGING after {MAX_ROUNDS} rounds: stopped going round. Look at the log for names that keep flipping")
    found = [t for t in plan(*state()) if t["act"] == "fallen"]
    save("fallen.json", found)
    log(f"trims done: {done} renamed. {len(found)} beaten everywhere")
    if found and done < limit:
        fallen.groups(iv_only=False)
        done += sum(fallen.act(limit - done, recheck_fallen, off=("PvpC",)).values())
    return done


import search, fallen  # down here: they `import run`, which has to be all there first


def main(limit, dry):
    front()
    to_top()
    skipped, counts = Counter(), Counter()
    skips_in_a_row = 0
    scroll_how = "drag"  # Mirroring ignores the scroll wheel here
    seen = set()  # CPs of every tile read so far: a scroll that shows none we haven't seen got nowhere
    stale = 0
    log(f"start, log in {RUN_DIR}")
    while counts["done"] + counts["skip"] < limit:
        _, texts, _, bounds = wait_for("list")
        ts = ui.tiles(texts)
        seen.update(t[1] for t in ts)
        p = pick(ts, skipped)
        if not p:
            if dry:
                log("DRY nothing to do on this screen, would scroll")
                return counts
            # at the bottom the list bounces back and OCR reads it a bit differently each time,
            # so "did the tiles change" never settles: look for tiles we haven't seen instead
            before = [t[:2] for t in ts]
            fresh = False
            for how in ([scroll_how] + [h for h in ("wheel", "drag") if h != scroll_how]):
                scroll(bounds, how)
                _, texts, _, bounds = wait_for("list")
                now = ui.tiles(texts)
                if {t[1] for t in now} - seen:
                    scroll_how, fresh = how, True
                    break
                if [t[:2] for t in now] == before:
                    continue  # didn't move at all: try the other way of scrolling
                break  # moved, but nothing new
            stale = 0 if fresh else stale + 1
            if stale >= END_AFTER_STALE:
                log("no new Pokémon after scrolling: end of list")
                counts["end"] = 1
                break
            continue
        i, n, c = p
        if dry:
            log(f"DRY next is tile {i}: {n} CP{c}")
            tap(f"tile {i}", dry=True)
            return counts
        log(f"tile {i}: {n} CP{c}")
        try:
            result = process(i, n, c)
            counts["nope" if result == "NOPE" else "renamed"] += 1
            counts["done"] += 1
            skips_in_a_row = 0
            stale = 0
        except Skip as e:
            keep_capture(f"skip-{n}")
            log(f"SKIP {n} CP{c}: {e}")
            skipped[(n, c)] += 1
            counts["skip"] += 1
            skips_in_a_row += 1
            if skips_in_a_row >= MAX_SKIPS_IN_A_ROW:
                raise Stop(f"{skips_in_a_row} skips in a row, something's off")
            back_to_list()
    return counts


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    dry = "--dry-run" in a
    cmd = a[0] if a and a[0] in ("fallen", "act-fallen") else None
    if cmd:
        if len(a) < 2 or not os.path.isdir(a[1]):
            sys.exit(f"usage: run.py {cmd} <run dir>")
        new_run_dir(None, os.path.abspath(a[1]))
    code = 0
    try:
        if cmd == "fallen":
            fallen_step()
            at_end, counts = 0, {}
        elif cmd == "act-fallen":
            if not os.path.exists(os.path.join(RUN_DIR, "fallen-groups.json")):
                sys.exit("run fallen first, and read fallen.txt")
            log(f"finished: {act_fallen(limit)} renamed or tagged")
            at_end, counts = 0, {}
        else:
            counts = main(limit, dry)
            at_end = counts.pop("end", 0)
            log(f"finished: {dict(counts)}")
            if at_end and load("renamed.json", []):  # still on the phone: check what the new names pushed out
                try:
                    fallen_step()
                except (Stop, Skip) as e:
                    keep_capture("fallen")
                    log(f"fallen out step STOPPED: {e} (run `run.py fallen {RUN_DIR}` to go on)")
                    at_end = 0  # leave the phone where it is
        if at_end and ui.ANDROID and not ui.android.NO_WINDOW:
            log("closed the scrcpy window" if ui.android.close() else "couldn't close the scrcpy window")
        elif at_end:
            try:
                ok = subprocess.run(["osascript", "-e", 'quit app "iPhone Mirroring"'], timeout=10).returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
            if not ok:
                ok = subprocess.run(["pkill", "-x", "iPhone Mirroring"]).returncode == 0
            log("quit iPhone Mirroring" if ok else "couldn't quit iPhone Mirroring")
    except Stop as e:
        keep_capture("stop")
        log(f"STOPPED: {e}")
        code = 1
    except KeyboardInterrupt:
        log("interrupted")
        code = 130
    except Exception as e:
        keep_capture("crash")
        log(f"CRASHED: {type(e).__name__}: {e}")
        code = 2
    sys.exit(code)
