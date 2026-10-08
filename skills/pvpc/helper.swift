// pvpc screen helper. Build: swiftc -O helper.swift -o helper
//   helper win [owner [all]] -> "<id> <x> <y> <w> <h>" of the iPhone Mirroring (or owner's) window (points)
//   helper ocr <png>    -> one line per text: "<x> <y> <w> <h>\t<text>" (0-1 fractions, top-left origin)
//   helper mouse        -> "<x> <y>" cursor position in points (top-left origin)
//   helper front        -> name of the frontmost app
//   helper click <x> <y> <hold_ms>              glide the cursor there, press, hold, release (points)
//   helper scroll <x> <y> <dy> <steps>          scroll wheel at a spot; dy < 0 scrolls the list down
//   helper drag <x1> <y1> <x2> <y2> <ms>        press, move, release
//   helper key <name> [cmd]                     one key: a-z 0-9 space + delete return; "cmd" holds command
//   helper type <text> <min_ms> <max_ms>        type text (US layout), random gap between keys
import AppKit
import Vision

let args = CommandLine.arguments

func post(_ e: CGEvent?) { e?.post(tap: .cghidEventTap) }

func mouse(_ t: CGEventType, _ p: CGPoint) {
    post(CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left))
}

func nap(_ ms: Double) { usleep(useconds_t(max(ms, 0) * 1000)) }

// cursor slides to p in a few uneven steps instead of teleporting
func glide(to p: CGPoint, _ drag: Bool = false) {
    let a = CGEvent(source: nil)!.location
    let n = Int.random(in: 5...10)
    for i in 1...n {
        let f = Double(i) / Double(n), e = f * f * (3 - 2 * f)
        let q = CGPoint(x: a.x + (p.x - a.x) * e + (i < n ? Double.random(in: -1.5...1.5) : 0),
                        y: a.y + (p.y - a.y) * e + (i < n ? Double.random(in: -1.5...1.5) : 0))
        mouse(drag ? .leftMouseDragged : .mouseMoved, q)
        nap(Double.random(in: 6...15))
    }
}

let KEYS: [Character: (CGKeyCode, Bool)] = {
    var k: [Character: (CGKeyCode, Bool)] = [:]
    let plain: [(Character, CGKeyCode)] = [("a", 0), ("s", 1), ("d", 2), ("f", 3), ("h", 4), ("g", 5), ("z", 6), ("x", 7),
        ("c", 8), ("v", 9), ("b", 11), ("q", 12), ("w", 13), ("e", 14), ("r", 15), ("y", 16), ("t", 17), ("1", 18),
        ("2", 19), ("3", 20), ("4", 21), ("6", 22), ("5", 23), ("=", 24), ("9", 25), ("7", 26), ("-", 27), ("8", 28),
        ("0", 29), ("o", 31), ("u", 32), ("i", 34), ("p", 35), ("l", 37), ("j", 38), ("k", 40), ("n", 45), ("m", 46),
        (" ", 49)]
    for (c, code) in plain {
        k[c] = (code, false)
        if c.isLetter { k[Character(c.uppercased())] = (code, true) }
    }
    k["+"] = (24, true)
    k["/"] = (44, false)
    k["*"] = (28, true)
    k["^"] = (22, true)
    k["&"] = (26, true)
    k["!"] = (18, true)
    k["#"] = (20, true)
    k[","] = (43, false)
    k["."] = (47, false)
    return k
}()

func press(_ code: CGKeyCode, _ flags: CGEventFlags) {
    // hold real modifier keys: Mirroring ignores the flag alone (cmd+a came through as a plain "a")
    let mods: [(CGEventFlags, CGKeyCode)] = [(.maskCommand, 55), (.maskShift, 56)].filter { flags.contains($0.0) }
    var held: CGEventFlags = []
    for (f, m) in mods {
        held.insert(f)
        let e = CGEvent(keyboardEventSource: nil, virtualKey: m, keyDown: true)
        e?.flags = held
        post(e)
        nap(Double.random(in: 120...180))  // shorter and Mirroring sometimes drops the shift: "#" came out "3"
    }
    defer {
        for (f, m) in mods.reversed() {
            nap(Double.random(in: 120...180))  // shorter and Mirroring sometimes drops the shift: "#" came out "3"
            held.remove(f)
            let e = CGEvent(keyboardEventSource: nil, virtualKey: m, keyDown: false)
            e?.flags = held
            post(e)
        }
    }
    let d = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true)
    let u = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false)
    d?.flags = flags
    u?.flags = flags
    post(d)
    nap(Double.random(in: 40...90))
    post(u)
}

func pt(_ i: Int) -> CGPoint { CGPoint(x: Double(args[i])!, y: Double(args[i + 1])!) }
switch args.count > 1 ? args[1] : "" {
case "win":
    // optional: another app's window (scrcpy for an Android phone); "all" finds it behind other windows or Spaces too
    let owner = args.count > 2 ? args[2] : "iPhone Mirroring"
    let opts: CGWindowListOption = args.count > 3 && args[3] == "all" ? [.excludeDesktopElements] : [.optionOnScreenOnly, .excludeDesktopElements]
    let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as! [[String: Any]]
    for w in list where (w[kCGWindowOwnerName as String] as? String) == owner && (w[kCGWindowLayer as String] as? Int) == 0 {
        let b = w[kCGWindowBounds as String] as! [String: Any]
        if (b["Width"] as? Double ?? 0) < 100 || (b["Height"] as? Double ?? 0) < 100 { continue }  // scrcpy's helper windows and bars
        print(w[kCGWindowNumber as String]!, b["X"]!, b["Y"]!, b["Width"]!, b["Height"]!)
        exit(0)
    }
    exit(1)
case "ocr":
    let img = NSImage(contentsOf: URL(fileURLWithPath: args[2]))!
    var r = NSRect(origin: .zero, size: img.size)
    let cg = img.cgImage(forProposedRect: &r, context: nil, hints: nil)!
    func read(_ rev: Int?) -> [VNRecognizedTextObservation] {
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = false
        if let r = rev { req.revision = r }
        try! VNImageRequestHandler(cgImage: cg, orientation: .up).perform([req])
        return req.results ?? []
    }
    // the phone clock sits top-left on every screen. A page of same-looking names ("96 HA" x 12) can make the
    // newest reader think the image is upside down and read it all backwards; then the clock is gone.
    let clock = try! NSRegularExpression(pattern: "\\d:\\d\\d")
    func hasClock(_ os: [VNRecognizedTextObservation]) -> Bool {
        os.contains { o in
            let s = o.topCandidates(1).first?.string ?? ""
            return 1 - o.boundingBox.maxY < 0.1 && clock.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
        }
    }
    // the Android clock is white on a light screen and often unread: then count right-way-up 'CP 123's too
    func score(_ os: [VNRecognizedTextObservation]) -> Int {
        (hasClock(os) ? 100 : 0) + os.filter { o in
            let u = (o.topCandidates(1).first?.string ?? "").uppercased()
            return ["CP", "DONE", "SEARCH", "TRANSFER", "THIS TAG"].contains { u.contains($0) }
        }.count
    }
    var obs = read(nil)
    if !hasClock(obs) && score(obs) == 0 {  // a right-way-up read with a CP in it is fine: skip the 2nd read
        let old = read(VNRecognizeTextRequestRevision2)
        if score(old) > score(obs) { obs = old }
    }
    for o in obs {
        let b = o.boundingBox
        print(String(format: "%.4f %.4f %.4f %.4f\t", b.minX, 1 - b.maxY, b.width, b.height) + (o.topCandidates(1).first?.string ?? ""))
    }
case "mouse":
    let p = CGEvent(source: nil)!.location
    print(p.x, p.y)
case "front":
    print(NSWorkspace.shared.frontmostApplication?.localizedName ?? "")
case "click":
    let p = pt(2)
    glide(to: p)
    nap(Double.random(in: 20...60))
    mouse(.leftMouseDown, p)
    nap(Double(args[4])!)
    mouse(.leftMouseUp, p)
case "scroll":
    let p = pt(2)
    glide(to: p)
    nap(Double.random(in: 60...150))
    let dy = Double(args[4])!, n = Int(args[5])!
    for _ in 0..<n {
        let step = Int32((dy / Double(n)) * Double.random(in: 0.8...1.2))
        post(CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 1, wheel1: step, wheel2: 0, wheel3: 0))
        nap(Double.random(in: 12...30))
    }
case "drag":
    let a = pt(2), b = pt(4)
    glide(to: a)
    nap(Double.random(in: 40...100))
    mouse(.leftMouseDown, a)
    nap(Double.random(in: 20...40))  // short: a long press would start multi-select in the list
    let n = 20, ms = Double(args[6])!
    for i in 1...n {
        let f = Double(i) / Double(n), e = f * f * (3 - 2 * f)
        mouse(.leftMouseDragged, CGPoint(x: a.x + (b.x - a.x) * e, y: a.y + (b.y - a.y) * e))
        nap(ms / Double(n))
    }
    nap(Double.random(in: 60...120))  // settle before release so it doesn't fling
    mouse(.leftMouseUp, b)
case "key":
    let name = args[2]
    let flags: CGEventFlags = args.count > 3 && args[3] == "cmd" ? .maskCommand : []
    if name == "delete" {
        press(51, flags)
    } else if name == "return" {
        press(36, flags)
    } else if let (code, shift) = KEYS[Character(name)] {
        press(code, shift ? flags.union(.maskShift) : flags)
    } else {
        print("unknown key \(name)")
        exit(2)
    }
case "type":
    let lo = Double(args[3])!, hi = Double(args[4])!
    for c in args[2] where KEYS[c] == nil {
        print("can't type \(c)")
        exit(2)
    }
    for c in args[2] {
        let (code, shift) = KEYS[c]!
        press(code, shift ? .maskShift : [])
        nap(Double.random(in: lo...hi))
    }
default:
    print("usage: helper win | ocr <png> | mouse | front | click | scroll | drag | key | type")
    exit(2)
}
