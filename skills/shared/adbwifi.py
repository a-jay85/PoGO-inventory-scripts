#!/usr/bin/env python3
"""The Pixel over Wi-Fi, so the scripts reach it unplugged. A launchd job runs `tick` every 30 s:
  - Pixel on USB: save its Wi-Fi address, and turn on adb over Wi-Fi (`adb tcpip 5555`) if it's off. A phone
    restart turns that off, so plug in once after each restart. The Wi-Fi link is dropped while USB is there:
    two links to one phone make every plain `adb` command fail with "more than one device".
  - Pixel unplugged: `adb connect <saved address>:5555` when the link is down.
  Both wait while a script holds the phone lock: `adb tcpip` restarts adb on the phone, and dropping the link
  a script is using stops it. android.py picks USB first, then Wi-Fi, and reconnects itself too.
The Mac and the Pixel must be on the same Wi-Fi. macOS must let adb use the local network (System Settings >
Privacy & Security > Local Network > adb on). Without it, adb started from launchd says "No route to host".

  python3 adbwifi.py install     write and start the launchd job (runs this file in the main checkout)
  python3 adbwifi.py uninstall   stop and remove it
  python3 adbwifi.py tick        one check (what the job runs); says what it did
  python3 adbwifi.py status      the links adb has, and the saved address
"""
import fcntl, os, re, subprocess, sys, time
from pathlib import Path

PORT = 5555
ADDR_FILE = Path.home() / ".config/pogo/android-wifi"  # "ip:port", written on each USB check
LOCK = "/tmp/pogo-android.lock"  # session.claim() holds it for a whole run
LABEL = "com.ajaynicolas.adbwifi"
PLIST = Path.home() / f"Library/LaunchAgents/{LABEL}.plist"
LOG = Path.home() / "claude-plans/_scripts/adbwifi.log"
MAIN = Path.home() / "PoGO-inventory-scripts/skills/shared/adbwifi.py"


def say(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def adb(*a, timeout=10):
    try:
        return subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return ""


def devices():
    """-> (usb serials, wifi serials) adb has as 'device' (not offline or unauthorized)"""
    rows = [line.split() for line in adb("devices").splitlines()[1:]]
    ok = [r[0] for r in rows if len(r) >= 2 and r[1] == "device"]
    return [s for s in ok if ":" not in s], [s for s in ok if ":" in s]


def saved():
    try:
        return ADDR_FILE.read_text().strip() or None
    except OSError:
        return None


def busy():
    """a script holds the phone lock (tried and let go at once)"""
    try:
        f = open(LOCK, "a+")
    except OSError:
        return False
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        f.close()


def connect():
    """the saved address connected -> its serial, or None. adb can say 'connected' to a dead address, so the
    answer is what `adb devices` lists afterwards"""
    addr = saved()
    if not addr:
        return None
    adb("connect", addr, timeout=8)
    return addr if addr in devices()[1] else None


def tick():
    usb, wifi = devices()
    if usb:
        s = usb[0]
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", adb("-s", s, "shell", "ip -f inet addr show wlan0"))
        if m:
            addr = f"{m[1]}:{PORT}"
            if addr != saved():
                ADDR_FILE.parent.mkdir(parents=True, exist_ok=True)
                ADDR_FILE.write_text(addr + "\n")
                say(f"saved the Pixel's Wi-Fi address {addr}")
        if busy():
            return
        if adb("-s", s, "shell", "getprop service.adb.tcp.port").strip() != str(PORT):
            adb("-s", s, "tcpip", str(PORT))
            say(f"turned on adb over Wi-Fi (port {PORT})")
            time.sleep(3)  # adb on the phone restarts
        for w in wifi:
            adb("disconnect", w)
            say(f"dropped the Wi-Fi link {w}: the Pixel is on USB")
    elif not wifi and not busy() and saved():
        say(f"connected over Wi-Fi to {saved()}" if connect() else f"no answer from {saved()} over Wi-Fi")


def install():
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{LABEL}</string>
<key>ProgramArguments</key><array><string>{sys.executable}</string><string>{MAIN}</string><string>tick</string></array>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
<key>StartInterval</key><integer>30</integer>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>{LOG}</string>
<key>StandardErrorPath</key><string>{LOG}</string>
</dict></plist>
""")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=True)
    print(f"installed {PLIST}: every 30 s, log in {LOG}")


def uninstall():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    PLIST.unlink(missing_ok=True)
    print("removed")


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["tick"]:
        tick()
    elif cmd == ["install"]:
        install()
    elif cmd == ["uninstall"]:
        uninstall()
    elif cmd == ["status"]:
        usb, wifi = devices()
        print(f"USB: {usb or 'none'}  Wi-Fi: {wifi or 'none'}  saved address: {saved() or 'none'}")
    else:
        sys.exit(__doc__)
